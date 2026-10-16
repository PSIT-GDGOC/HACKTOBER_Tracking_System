"""Provider acceptance, redaction and shared atomic request reservations."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_rate_limit import EmailRateLimit
from app.services import email_service as emails
from app.services import email_rate_limit as limits


@pytest.fixture(autouse=True)
def email_config(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")


def dispatch():
    return emails.send_password_reset_email("private@example.com", "Student", "secret-token", "654321")


def test_no_provider_is_failure_without_secret_logging(caplog):
    assert dispatch() is False
    assert "not accepted" in caplog.text
    for secret in ("654321", "secret-token", "private@example.com"):
        assert secret not in caplog.text


@pytest.mark.parametrize("result,accepted", [
    ({"id": "mail-123"}, True), (None, False), ({}, False),
    ({"id": ""}, False), ({"id": 1}, False),
    ({"error": "rejected"}, False), ({"id": "mail-123", "error": "rejected"}, False),
    ({"id": "mail-123", "statusCode": 403}, False),
])
def test_resend_requires_acceptance_id(monkeypatch, result, accepted):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")
    send = MagicMock(return_value=result)
    monkeypatch.setattr(emails.resend.Emails, "send", send)
    assert dispatch() is accepted
    payload = send.call_args.args[0]
    assert "/#/reset-password?token=secret-token" in payload["html"]
    assert "654321" in payload["text"]


def test_resend_exception_is_failure_and_redacted(monkeypatch, caplog):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(emails.resend.Emails, "send", MagicMock(side_effect=RuntimeError("secret-token 654321")))
    assert dispatch() is False
    assert "RuntimeError" in caplog.text
    assert "654321" not in caplog.text
    assert "secret-token" not in caplog.text


@pytest.mark.parametrize("ssl_result,tls_result,resend_result,expected", [
    ({}, {}, None, True),
    (None, None, None, False),
    (OSError("SSL unavailable"), {}, None, True),
    ({"private@example.com": (550, b"refused")}, {"private@example.com": (550, b"refused")}, None, False),
    (OSError("down"), OSError("down"), {"id": "fallback"}, True),
    (OSError("down"), OSError("down"), {}, False),
])
def test_smtp_acceptance_and_fallback(monkeypatch, ssl_result, tls_result, resend_result, expected):
    monkeypatch.setattr(settings, "SMTP_USER", "test-user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "test-password")
    for transport, result in (("SMTP_SSL", ssl_result), ("SMTP", tls_result)):
        mock = MagicMock()
        send = mock.return_value.__enter__.return_value.send_message
        if isinstance(result, Exception):
            send.side_effect = result
        else:
            send.return_value = result
        monkeypatch.setattr(emails.smtplib, transport, mock)
    if resend_result is not None:
        monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")
    resend_send = MagicMock(return_value=resend_result)
    monkeypatch.setattr(emails.resend.Emails, "send", resend_send)
    assert dispatch() is expected
    if ssl_result == {}:
        emails.smtplib.SMTP.assert_not_called()
        resend_send.assert_not_called()


@pytest.fixture
def limit_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'limits.db'}", connect_args={"timeout": 15})
    EmailRateLimit.__table__.create(engine)
    yield engine
    engine.dispose()


def test_sliding_window_normalization_and_expiry(limit_engine, monkeypatch):
    clock = [10000.0]
    monkeypatch.setattr(limits.time, "time", lambda: clock[0])
    with Session(limit_engine) as db:
        limits.check_email_rate_limit(" FORGOT@psit.ac.in ", db)
        with pytest.raises(HTTPException) as denied:
            limits.check_email_rate_limit("forgot@psit.ac.in", db)
        assert denied.value.headers == {"Retry-After": "60"}
        for _ in range(4):
            clock[0] += 60
            limits.check_email_rate_limit("forgot@psit.ac.in", db)
        clock[0] += 60
        with pytest.raises(HTTPException) as denied:
            limits.check_email_rate_limit("forgot@psit.ac.in", db)
        assert denied.value.headers == {"Retry-After": "3300"}
        clock[0] = 13600
        limits.check_email_rate_limit("forgot@psit.ac.in", db)
        clock[0] = 17200
        limits.check_email_rate_limit("another@example.com", db)
        buckets = db.scalars(select(EmailRateLimit)).all()
        assert len(buckets) == 1
        assert "@" not in buckets[0].key


def test_concurrent_sessions_reserve_only_once(limit_engine):
    def reserve(_):
        with Session(limit_engine) as db:
            try:
                limits.check_email_rate_limit("parallel@example.com", db)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reserve, range(16)))
    assert outcomes.count(200) == 1
    assert outcomes.count(429) == 15
    # A fresh engine (like another worker/restart) sees the persisted reservation.
    fresh_engine = create_engine(limit_engine.url)
    try:
        with Session(fresh_engine) as db, pytest.raises(HTTPException):
            limits.check_email_rate_limit("parallel@example.com", db)
    finally:
        fresh_engine.dispose()


def test_rate_limit_migration_upgrade_and_downgrade():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    path = Path(__file__).parents[1] / "alembic/versions/0007_email_rate_limits.py"
    spec = importlib.util.spec_from_file_location("rate_limit_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert "email_rate_limits" in inspect(connection).get_table_names()
                assert inspect(connection).get_pk_constraint("email_rate_limits")["constrained_columns"] == ["key"]
                migration.downgrade()
                assert "email_rate_limits" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()
