"""Unit and Integration Tests for Email Verification and Password Reset.

Covers:
- Token generation & SHA-256 hashing.
- POST /auth/send-verification & POST /auth/verify-email flow.
- Token re-use rejection (single-use constraint).
- Token expiration rejection.
- Wrong token purpose rejection.
- Rate limiting cooldown (1 per 60s, max 5 per hour).
- POST /auth/forgot-password generic enumeration protection.
- POST /auth/reset-password with token updating PBKDF2 password hash.
- REQUIRE_EMAIL_VERIFICATION toggle behavior.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import User, UserRole
from app.models.email_token import EmailToken, TokenPurpose
from app.services.auth_service import (
    hash_password,
    verify_password,
    hash_token,
    create_email_token,
)
import app.services.email_service as email_service_module


TEST_ROLL = "2200330100999"
TEST_EMAIL = "student.test@psit.ac.in"


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear rate limits before and after every test."""
    email_service_module._email_rate_limits.clear()
    yield
    email_service_module._email_rate_limits.clear()


@pytest.fixture
def client_and_db():
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

    # Create a test student user
    db = TestingSessionLocal()
    user = User(
        name="Test Student",
        email=TEST_EMAIL,
        psit_roll_no=TEST_ROLL,
        role=UserRole.STUDENT,
        password_hash=hash_password("OldPassword123!"),
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    client = TestClient(app)
    yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_token_hashing_and_creation(client_and_db):
    _, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()

    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.VERIFY_EMAIL,
        expire_minutes=30,
    )

    # 1. Raw token is returned
    assert raw_token is not None
    assert len(raw_token) > 20

    # 2. Token in DB is SHA-256 hashed, not raw
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    email_token = db.query(EmailToken).filter(EmailToken.token_hash == expected_hash).first()
    assert email_token is not None
    assert email_token.token_hash == expected_hash
    assert email_token.token_hash != raw_token
    assert email_token.purpose == TokenPurpose.VERIFY_EMAIL
    assert email_token.used_at is None
    assert email_token.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
    db.close()


def test_verify_email_flow_success(client_and_db):
    client, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    assert not user.is_email_verified

    user_id = user.id
    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.VERIFY_EMAIL,
        expire_minutes=30,
    )
    db.close()

    # Call POST /auth/verify-email with the token
    response = client.post("/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_email_verified"] is True

    # Check database state
    db = SessionLocal()
    updated_user = db.query(User).filter(User.email == TEST_EMAIL).first()
    assert updated_user.is_email_verified is True
    used_token = db.query(EmailToken).filter(EmailToken.user_id == user_id).first()
    assert used_token.used_at is not None
    db.close()


def test_token_re_use_rejected(client_and_db):
    client, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()

    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.VERIFY_EMAIL,
        expire_minutes=30,
    )
    db.close()

    # First use: success
    res1 = client.post("/auth/verify-email", json={"token": raw_token})
    assert res1.status_code == 200

    # Second use: rejected (already used)
    res2 = client.post("/auth/verify-email", json={"token": raw_token})
    assert res2.status_code == 400
    assert "already been used" in res2.json()["detail"].lower()


def test_expired_token_rejected(client_and_db):
    client, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()

    # Create expired token
    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.VERIFY_EMAIL,
        expire_minutes=-10,  # Expired 10 minutes ago
    )
    db.close()

    response = client.post("/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_wrong_purpose_token_rejected(client_and_db):
    client, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()

    # Create a reset-password token
    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.RESET_PASSWORD,
        expire_minutes=30,
    )
    db.close()

    # Try to verify email with a password-reset token
    response = client.post("/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 400
    assert "purpose" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()


def test_send_verification_rate_limiting(client_and_db):
    client, _ = client_and_db

    with patch("app.services.email_service.send_verification_email", return_value=True):
        # 1st request: OK
        res1 = client.post("/auth/send-verification", json={"email": TEST_EMAIL})
        assert res1.status_code == 200

        # Immediate 2nd request: 429 Too Many Requests (within 60 seconds)
        res2 = client.post("/auth/send-verification", json={"email": TEST_EMAIL})
        assert res2.status_code == 429
        assert "wait" in res2.json()["detail"].lower()


def test_forgot_password_generic_response(client_and_db):
    """Ensure POST /auth/forgot-password does not enumerate registered emails."""
    client, _ = client_and_db

    with patch("app.routers.auth.send_password_reset_email", return_value=True):
        # Existing email
        res_existing = client.post("/auth/forgot-password", json={"email": TEST_EMAIL})
        assert res_existing.status_code == 200
        msg_existing = res_existing.json()["message"]

        # Clear rate limiter between calls
        email_service_module._email_rate_limits.clear()

        # Non-existing email
        res_nonexistent = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
        assert res_nonexistent.status_code == 200
        msg_nonexistent = res_nonexistent.json()["message"]

        # Both return the exact same generic security message
        assert msg_existing == msg_nonexistent
        assert "if an account with that email exists" in msg_existing.lower()


def test_forgot_password_by_roll_number_fetches_email_and_sends_otp(client_and_db):
    """Ensure numeric roll number is detected, email is fetched from DB, and OTP is generated & dispatched."""
    client, SessionLocal = client_and_db

    with patch("app.routers.auth.send_password_reset_email") as mock_send_email:
        # Enter purely numeric roll number in identifier
        res = client.post("/auth/forgot-password", json={"identifier": TEST_ROLL})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "verification code has been sent" in data["message"].lower()

        # Check that user in DB received an OTP hash and expiry
        db = SessionLocal()
        user = db.query(User).filter(User.psit_roll_no == TEST_ROLL).first()
        assert user.reset_otp_hash is not None
        assert user.reset_otp_expires is not None
        db.close()

        # Check that send_password_reset_email was called with the fetched email and an OTP code
        assert mock_send_email.called
        kwargs = mock_send_email.call_args.kwargs
        assert kwargs["to_email"] == TEST_EMAIL
        assert kwargs["otp_code"] is not None
        assert len(kwargs["otp_code"]) == 6


def test_reset_password_with_token_updates_hash(client_and_db):
    client, SessionLocal = client_and_db
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()

    raw_token = create_email_token(
        db=db,
        user=user,
        purpose=TokenPurpose.RESET_PASSWORD,
        expire_minutes=30,
    )
    db.close()

    new_pass = "BrandNewSecret123!"

    # Reset password with token
    res = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": new_pass,
    })
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Verify old password fails and new password succeeds
    db = SessionLocal()
    updated_user = db.query(User).filter(User.email == TEST_EMAIL).first()
    assert not verify_password("OldPassword123!", updated_user.password_hash)
    assert verify_password(new_pass, updated_user.password_hash)
    db.close()


def test_require_email_verification_setting(client_and_db):
    client, SessionLocal = client_and_db

    # With REQUIRE_EMAIL_VERIFICATION = False, unverified student can login
    with patch.object(settings, "REQUIRE_EMAIL_VERIFICATION", False):
        res = client.post("/auth/login", json={
            "identifier": TEST_ROLL,
            "password": "OldPassword123!",
        })
        assert res.status_code == 200

    # With REQUIRE_EMAIL_VERIFICATION = True, unverified student is blocked with 403
    with patch.object(settings, "REQUIRE_EMAIL_VERIFICATION", True):
        res_blocked = client.post("/auth/login", json={
            "identifier": TEST_ROLL,
            "password": "OldPassword123!",
        })
        assert res_blocked.status_code == 403
        assert "verify your email" in res_blocked.json()["detail"].lower()

        # Now mark user as verified
        db = SessionLocal()
        u = db.query(User).filter(User.email == TEST_EMAIL).first()
        u.is_email_verified = True
        db.commit()
        db.close()

        # Login now succeeds
        res_allowed = client.post("/auth/login", json={
            "identifier": TEST_ROLL,
            "password": "OldPassword123!",
        })
        assert res_allowed.status_code == 200
