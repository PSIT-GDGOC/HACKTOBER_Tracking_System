"""Tests for Auth & Verification Module.

Covers:
- Student signup (pending verification status; enforces 13-char roll number)
- 13-char roll number validation (rejects shorter or longer roll numbers with 422)
- Duplicate roll number & duplicate email rejection (400)
- Login with JWT token issuance & claim verification
- Bearer JWT token authentication on /auth/me
- ID Card upload & automated QR/portal verification (exact roll + fuzzy name match)
- Fallback routing to pending_review on portal mismatch or portal unavailable
- Admin manual verification queue & approval/rejection endpoints
- RBAC protection (students blocked with 403 from admin queue)
- GitHub OAuth linking with duplicate username protection
"""
import base64
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import User, UserRole, VerificationMethod
from app.services.auth_service import create_access_token


def _create_dummy_image_b64() -> str:
    """Generate minimal valid JPEG bytes in memory as base64 string."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# Valid 13-character test roll numbers
ROLL_ADMIN = "ADMIN00000001"
ROLL_CODER = "2200330100050"
ROLL_PRIYA = "2200330100045"
ROLL_DUP_1 = "2200330100010"
ROLL_DUP_2 = "2200330100011"
ROLL_RAHUL = "2200330100088"
ROLL_ANANYA = "2200330100012"
ROLL_DEEPAK = "2200330100013"
ROLL_MOHIT = "2200330100020"
ROLL_SANJAY = "2200330100030"


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
    client = TestClient(app)

    db = TestingSessionLocal()

    # Seed an admin
    admin = User(
        id=99,
        name="Admin Lead",
        email="admin@psit.ac.in",
        psit_roll_no=ROLL_ADMIN,
        role=UserRole.ADMIN,
        verified=True,
    )

    # Seed an existing student with a taken github_username
    existing_student = User(
        id=50,
        name="Existing Coder",
        email="coder@psit.ac.in",
        psit_roll_no=ROLL_CODER,
        role=UserRole.STUDENT,
        verified=True,
        github_username="taken-github-dev",
    )

    db.add_all([admin, existing_student])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


# =====================================================================
# 1. Signup Tests
# =====================================================================

def test_student_signup_success(client_and_db):
    """Student can register with a valid 13-char roll number; account starts unverified."""
    client, db = client_and_db

    payload = {
        "name": "Priya Sharma",
        "email": "priya.sharma@psit.ac.in",
        "psit_roll_no": ROLL_PRIYA,
    }
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Priya Sharma"
    assert data["email"] == "priya.sharma@psit.ac.in"
    assert data["psit_roll_no"] == ROLL_PRIYA
    assert data["verified"] is False
    assert data["status"] == "pending_verification"

    # Verify persisted in DB
    user = db.query(User).filter(User.psit_roll_no == ROLL_PRIYA).first()
    assert user is not None
    assert user.role == UserRole.STUDENT


def test_student_signup_roll_number_length_validation(client_and_db):
    """Roll numbers that are NOT exactly 13 characters must be rejected with 422."""
    client, _ = client_and_db

    # Too short (5 chars)
    res_short = client.post("/auth/signup", json={
        "name": "Short Roll",
        "email": "short@psit.ac.in",
        "psit_roll_no": "22045",
    })
    assert res_short.status_code == 422

    # Too long (14 chars)
    res_long = client.post("/auth/signup", json={
        "name": "Long Roll",
        "email": "long@psit.ac.in",
        "psit_roll_no": "22003301000045X",
    })
    assert res_long.status_code == 422


def test_student_signup_duplicate_guards(client_and_db):
    """Duplicate roll numbers and duplicate emails of verified accounts must be rejected with 400.
    Unverified accounts never block retrying signup."""
    client, db = client_and_db

    # Register first student
    res1 = client.post("/auth/signup", json={
        "name": "Original Student",
        "email": "original@psit.ac.in",
        "psit_roll_no": ROLL_DUP_1,
    })
    assert res1.status_code == 201

    # Before verification: an unverified pending account should NOT block retrying signup!
    res_retry = client.post("/auth/signup", json={
        "name": "Original Student Updated",
        "email": "original@psit.ac.in",
        "psit_roll_no": ROLL_DUP_1,
    })
    assert res_retry.status_code == 201
    assert res_retry.json()["name"] == "Original Student Updated"

    # Now mark the first student as verified in DB
    user = db.query(User).filter(User.psit_roll_no == ROLL_DUP_1).first()
    user.verified = True
    db.commit()

    # Once verified: duplicate roll number must be rejected with 400
    res_dup_roll = client.post("/auth/signup", json={
        "name": "Another Student",
        "email": "another@psit.ac.in",
        "psit_roll_no": ROLL_DUP_1,
    })
    assert res_dup_roll.status_code == 400
    assert "already registered" in res_dup_roll.json()["detail"]

    # Once verified: duplicate email must be rejected with 400
    res_dup_email = client.post("/auth/signup", json={
        "name": "Different Student",
        "email": "original@psit.ac.in",
        "psit_roll_no": ROLL_DUP_2,
    })
    assert res_dup_email.status_code == 400
    assert "already registered" in res_dup_email.json()["detail"]


# =====================================================================
# 2. Login & JWT Tests
# =====================================================================

def test_login_and_jwt_issuance(client_and_db):
    """Login with roll number issues valid JWT token with user claims."""
    client, _ = client_and_db

    # Sign up
    client.post("/auth/signup", json={
        "name": "Rahul Verma",
        "email": "rahul@psit.ac.in",
        "psit_roll_no": ROLL_RAHUL,
    })

    # Log in with roll number
    res = client.post("/auth/login", json={"identifier": ROLL_RAHUL})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["psit_roll_no"] == ROLL_RAHUL

    # Log in with email
    res_email = client.post("/auth/login", json={"identifier": "rahul@psit.ac.in"})
    assert res_email.status_code == 200
    assert "access_token" in res_email.json()


def test_auth_me_protected_endpoint(client_and_db):
    """GET /auth/me returns user profile when Bearer JWT is supplied."""
    client, _ = client_and_db

    token = create_access_token(data={"sub": "50", "role": "student", "verified": True})
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["psit_roll_no"] == ROLL_CODER


# =====================================================================
# 3. ID Card & QR Verification Tests (server-side pipeline)
# =====================================================================

def test_id_card_auto_verification(client_and_db):
    """
    Submitting valid ID card photo where QR decodes and portal name/roll match
    automatically verifies the student account.
    """
    client, db = client_and_db

    student = User(
        id=12,
        name="Ananya Gupta",
        email="ananya@psit.ac.in",
        psit_roll_no=ROLL_ANANYA,
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(student)
    db.commit()

    token_hex = "91f519897e6be8e16d371027a234a90f"
    fake_portal_data = {
        "roll_no": ROLL_ANANYA,
        "student_name": "Gupta Ananya",  # fuzzy match with "Ananya Gupta"
        "_raw": {"rollno": ROLL_ANANYA, "name": "Gupta Ananya"},
    }

    with patch("app.services.auth_service.decode_qr_from_image", return_value=token_hex):
        with patch("app.services.auth_service.fetch_psit_student_data", new=AsyncMock(return_value=fake_portal_data)):
            res = client.post(
                "/auth/verify-id",
                json={
                    "psit_roll_no": ROLL_ANANYA,
                    "id_card_image_base64": _create_dummy_image_b64(),
                },
                headers={"X-User-Id": "12"},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert data["status"] == "auto_verified"
    assert data["verification_method"] == "qr_auto"

    # Verify DB state
    db.expire_all()
    updated = db.query(User).filter(User.id == 12).first()
    assert updated.verified is True
    assert updated.verification_method == VerificationMethod.QR_AUTO
    assert updated.verified_at is not None


def test_id_card_pending_review_on_portal_mismatch(client_and_db):
    """
    Submitting ID card where portal name does not match student name
    leaves account unverified and routes to pending manual review.
    """
    client, db = client_and_db

    student = User(
        id=13,
        name="Deepak Joshi",
        email="deepak@psit.ac.in",
        psit_roll_no=ROLL_DEEPAK,
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(student)
    db.commit()

    token_hex = "1bb4d8f10de22856757f48f15f45b8bf"
    mismatched_portal_data = {
        "roll_no": ROLL_DEEPAK,
        "student_name": "Completely Different Person",
        "_raw": {"rollno": ROLL_DEEPAK, "name": "Completely Different Person"},
    }

    with patch("app.services.auth_service.decode_qr_from_image", return_value=token_hex):
        with patch("app.services.auth_service.fetch_psit_student_data", new=AsyncMock(return_value=mismatched_portal_data)):
            res = client.post(
                "/auth/verify-id",
                json={
                    "psit_roll_no": ROLL_DEEPAK,
                    "id_card_image_base64": _create_dummy_image_b64(),
                },
                headers={"X-User-Id": "13"},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is False
    assert data["status"] == "pending_review"

    # Verify DB state
    db.expire_all()
    updated = db.query(User).filter(User.id == 13).first()
    assert updated.verified is False
    assert updated.verification_method is None


def test_id_card_duplicate_qr_code_rejected(client_and_db):
    """
    Prevent one PSIT ID card from verifying multiple student accounts.
    If the same QR token is scanned for a second account, it must be rejected.
    """
    client, db = client_and_db

    shared_token_hex = "abcdef1234567890abcdef1234567890"

    # User 1: already verified with this ID card QR token
    user1 = User(
        id=70,
        name="Original Student",
        email="original@psit.ac.in",
        psit_roll_no="2200320100070",
        role=UserRole.STUDENT,
        qr_token=shared_token_hex,
        verified=True,
    )
    # User 2: tries to verify using the exact same ID card QR token
    user2 = User(
        id=71,
        name="Second Account",
        email="second@psit.ac.in",
        psit_roll_no="2200320100071",
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(user1)
    db.add(user2)
    db.commit()

    with patch("app.services.auth_service.decode_qr_from_image", return_value=shared_token_hex):
        res = client.post(
            "/auth/verify-id",
            json={
                "psit_roll_no": "2200320100071",
                "id_card_image_base64": _create_dummy_image_b64(),
            },
            headers={"X-User-Id": "71"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is False
    assert data["status"] == "duplicate_verified_card"
    assert "already been verified" in data["message"]

    # Verify User 2 was NOT verified in the database
    db.expire_all()
    updated_user2 = db.query(User).filter(User.id == 71).first()
    assert updated_user2.verified is False


def test_id_card_qr_unreadable_fallback(client_and_db):
    """
    When QR code cannot be decoded from the photo, student is routed
    to manual review rather than blocked.
    """
    client, db = client_and_db

    student = User(
        id=14,
        name="Kavita Singh",
        email="kavita@psit.ac.in",
        psit_roll_no="2200330100014",
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(student)
    db.commit()

    with patch("app.services.auth_service.decode_qr_from_image", return_value=None):
        res = client.post(
            "/auth/verify-id",
            json={
                "psit_roll_no": "2200330100014",
                "id_card_image_base64": _create_dummy_image_b64(),
            },
            headers={"X-User-Id": "14"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is False
    assert data["status"] == "qr_unreadable"


# =====================================================================
# 4. Admin Manual Verification Queue & Approval
# =====================================================================

def test_admin_manual_verification_queue_and_approval(client_and_db):
    """
    Admin views pending verification queue and manually approves student.
    Non-admin user receives 403 Forbidden.
    """
    client, db = client_and_db

    student = User(
        id=20,
        name="Mohit Agarwal",
        email="mohit@psit.ac.in",
        psit_roll_no=ROLL_MOHIT,
        role=UserRole.STUDENT,
        verified=False,
        id_card_image_url="id-cards/mohit_card.jpg",
    )
    db.add(student)
    db.commit()

    # 1. Non-admin student attempts to view queue -> 403 Forbidden
    res_forbidden = client.get("/auth/pending-verifications", headers={"X-User-Id": "20"})
    assert res_forbidden.status_code == 403

    # 2. Admin views queue -> 200 OK
    res_admin = client.get("/auth/pending-verifications", headers={"X-User-Id": "99"})
    assert res_admin.status_code == 200
    queue = res_admin.json()
    assert any(item["id"] == 20 for item in queue)

    # 3. Admin approves student -> verified = True with method 'manual'
    res_approve = client.post(
        "/auth/verify-manual/20",
        json={"action": "approve", "reason": "ID card photo verified by organizer"},
        headers={"X-User-Id": "99"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["verified"] is True
    assert res_approve.json()["verification_method"] == "manual"

    # DB verification
    db.expire_all()
    updated = db.query(User).filter(User.id == 20).first()
    assert updated.verified is True
    assert updated.verification_method == VerificationMethod.MANUAL
    assert updated.verified_at is not None


# =====================================================================
# 5. GitHub Identity Linking Tests
# =====================================================================

def test_github_oauth_linking(client_and_db):
    """Student links their GitHub identity; duplicate username rejected."""
    client, db = client_and_db

    student = User(
        id=30,
        name="Sanjay Rao",
        email="sanjay@psit.ac.in",
        psit_roll_no=ROLL_SANJAY,
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(student)
    db.commit()

    # 1. Attempt to link username already taken by another student
    res_dup = client.post(
        "/auth/github/link",
        json={"github_username": "taken-github-dev"},
        headers={"X-User-Id": "30"},
    )
    assert res_dup.status_code == 400
    assert "already linked" in res_dup.json()["detail"]

    # 2. Successfully link unique GitHub username
    res_ok = client.post(
        "/auth/github/link",
        json={"github_username": "sanjay-coder", "github_id": "987654"},
        headers={"X-User-Id": "30"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True
    assert res_ok.json()["github_username"] == "sanjay-coder"

    # DB verification
    db.expire_all()
    updated = db.query(User).filter(User.id == 30).first()
    assert updated.github_username == "sanjay-coder"
    assert updated.github_id == "987654"
