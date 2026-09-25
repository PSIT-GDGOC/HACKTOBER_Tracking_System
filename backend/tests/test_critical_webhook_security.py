import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app


SECRET_KEY = "production-grade-hacktoberfest-secret-2026"


def _generate_hmac_sha256(data: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_client(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", SECRET_KEY)

    # Use in-memory SQLite so webhook_jobs insert doesn't need a real Postgres
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_reject_missing_signature_header(webhook_client):
    """Payloads without X-Hub-Signature-256 must be rejected immediately."""
    payload = json.dumps({"zen": "Security in depth"}).encode("utf-8")
    res = webhook_client.post(
        "/webhooks/github",
        data=payload,
        headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"}
    )
    assert res.status_code == 401
    assert "Invalid GitHub webhook signature" in res.json()["detail"]


def test_reject_malformed_signature_format(webhook_client):
    """Signatures that do not conform to sha256=<hex> format must be rejected."""
    payload = json.dumps({"zen": "Security in depth"}).encode("utf-8")
    malformed_signatures = [
        "md5=0123456789abcdef0123456789abcdef",
        "sha1=0123456789abcdef0123456789abcdef01234567",
        "random_token_without_prefix",
        "",
    ]
    for sig in malformed_signatures:
        res = webhook_client.post(
            "/webhooks/github",
            data=payload,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json"
            }
        )
        assert res.status_code == 401


def test_reject_tampered_payload_spoofing(webhook_client):
    """
    An attacker captures a valid signature for benign payload A,
    then attempts to send a malicious payload B (e.g. fake PR merged) with that signature.
    Must be rejected with 401.
    """
    benign_payload = json.dumps({"action": "ping"}).encode("utf-8")
    valid_sig_for_benign = _generate_hmac_sha256(benign_payload, SECRET_KEY)

    spoofed_payload = json.dumps({
        "action": "closed",
        "pull_request": {
            "id": 99999,
            "merged": True,
            "user": {"login": "attacker-student"}
        }
    }).encode("utf-8")

    res = webhook_client.post(
        "/webhooks/github",
        data=spoofed_payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": valid_sig_for_benign,
            "Content-Type": "application/json"
        }
    )
    assert res.status_code == 401
    assert "Invalid GitHub webhook signature" in res.json()["detail"]


def test_reject_wrong_secret_forgery(webhook_client):
    """An attacker attempts to sign a forged payload with their own secret."""
    payload = json.dumps({"action": "opened"}).encode("utf-8")
    forged_sig = _generate_hmac_sha256(payload, "attacker-guessed-secret")

    res = webhook_client.post(
        "/webhooks/github",
        data=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": forged_sig,
            "Content-Type": "application/json"
        }
    )
    assert res.status_code == 401


def test_reject_subtle_byte_tampering(webhook_client):
    """Even a single modified whitespace byte in payload must invalidate the signature."""
    original = b'{"action":"ping"}'
    valid_sig = _generate_hmac_sha256(original, SECRET_KEY)

    tampered = b'{"action":"ping"} '  # Notice trailing space
    res = webhook_client.post(
        "/webhooks/github",
        data=tampered,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": valid_sig,
            "Content-Type": "application/json"
        }
    )
    assert res.status_code == 401


def test_accept_legitimate_signed_payload(webhook_client):
    """A legitimate GitHub webhook signed with the correct secret must be accepted."""
    payload = json.dumps({"zen": "Mind your posture.", "action": "ping"}).encode("utf-8")
    valid_sig = _generate_hmac_sha256(payload, SECRET_KEY)

    res = webhook_client.post(
        "/webhooks/github",
        data=payload,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": valid_sig,
            "Content-Type": "application/json"
        }
    )
    assert res.status_code == 200
    assert "ping" in res.json()["event"]
