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
from fastapi import HTTPException
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


def test_password_setup_and_login_enforcement(client_and_db):
    """
    Once a student sets a password, login strictly enforces the password.
    Wrong or missing password yields 401; correct password returns JWT.
    """
    client, db = client_and_db

    # Register student
    reg_res = client.post("/auth/signup", json={
        "name": "Secured Student",
        "email": "secured@psit.ac.in",
        "psit_roll_no": "2200330100099",
    })
    assert reg_res.status_code == 201

    # Log in initially before password is set to get onboarding session
    login_init = client.post("/auth/login", json={"identifier": "2200330100099"})
    assert login_init.status_code == 200
    token = login_init.json()["access_token"]

    # 1. Attempt setting a weak password (too short)
    weak_res = client.post(
        "/auth/set-password",
        json={"password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert weak_res.status_code in [400, 422]

    # 2. Set a strong password
    strong_pwd = "P@ssword2026!Strong"
    set_res = client.post(
        "/auth/set-password",
        json={"password": strong_pwd},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert set_res.status_code == 200
    assert set_res.json()["success"] is True

    # 3. Logging in WITHOUT password must now be REJECTED with 401
    no_pwd_res = client.post("/auth/login", json={"identifier": "2200330100099"})
    assert no_pwd_res.status_code == 401
    assert "Invalid roll number or password" in no_pwd_res.json()["detail"]

    # 4. Logging in with WRONG password must be REJECTED with 401
    wrong_pwd_res = client.post("/auth/login", json={
        "identifier": "2200330100099",
        "password": "WrongPassword123!",
    })
    assert wrong_pwd_res.status_code == 401
    assert "Invalid roll number or password" in wrong_pwd_res.json()["detail"]

    # 5. Logging in with CORRECT password must SUCCEED with 200
    correct_pwd_res = client.post("/auth/login", json={
        "identifier": "2200330100099",
        "password": strong_pwd,
    })
    assert correct_pwd_res.status_code == 200
    assert "access_token" in correct_pwd_res.json()
    assert correct_pwd_res.json()["user"]["has_password"] is True


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


def test_github_link_validates_existence(client_and_db):
    """Attempting to link a non-existent GitHub account returns 400."""
    from unittest.mock import AsyncMock, MagicMock, patch
    client, db = client_and_db

    student = User(
        id=35,
        name="Existence Tester",
        email="exists@psit.ac.in",
        psit_roll_no="2200330100099",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(student)
    db.commit()

    # Case 1: GitHub returns 404 -> Rejected
    with patch(
        "app.services.auth_service.validate_github_username",
        side_effect=HTTPException(
            status_code=400,
            detail="GitHub account '@fake-nonexistent-user-12345' was not found on GitHub. Please check the spelling."
        )
    ):
        res_404 = client.post(
            "/auth/github/link",
            json={"github_username": "fake-nonexistent-user-12345"},
            headers={"X-User-Id": "35"},
        )
    assert res_404.status_code == 400
    assert "was not found on GitHub" in res_404.json()["detail"]

    # Case 2: GitHub returns 200 -> Accepted and github_id populated
    with patch(
        "app.services.auth_service.validate_github_username",
        return_value=("real-dev", "54321")
    ):
        res_200 = client.post(
            "/auth/github/link",
            json={"github_username": "real-dev"},
            headers={"X-User-Id": "35"},
        )
    assert res_200.status_code == 200
    assert res_200.json()["success"] is True
    assert res_200.json()["github_username"] == "real-dev"
    assert res_200.json()["github_id"] == "54321"


def test_stale_token_after_db_wipe_does_not_leak_other_user(client_and_db):
    """
    Regression test:
    When the database is cleared/wiped, an existing client may still hold a valid JWT.
    Verify that:
    1. A token referencing a non-existent user_id returns 401 (never falls back to default user).
    2. A token with an ID collision (same integer ID 1, but different roll number from wiped DB)
       returns 401 rather than returning the newly registered user.
    """
    client, db = client_and_db

    # User B exists in the current database
    user_b = User(
        name="User B (New)",
        email="user_b@psit.ac.in",
        psit_roll_no="2300970100099",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)

    # 1. Stale token for User A with ID that doesn't exist anymore (e.g., 9999)
    stale_token_deleted_user = create_access_token({
        "sub": "9999",
        "roll_no": "2200970100001",
        "role": "student",
        "verified": True,
    })
    res1 = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_token_deleted_user}"})
    assert res1.status_code == 401, f"Expected 401 for deleted user, got {res1.status_code}: {res1.text}"

    # 2. Stale token for User A with ID collision (sub: user_b.id, but roll_no from old User A)
    stale_token_id_collision = create_access_token({
        "sub": str(user_b.id),
        "roll_no": "2200970100001",  # User A's old roll number
        "role": "student",
        "verified": True,
    })
    res2 = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_token_id_collision}"})
    assert res2.status_code == 401, f"Expected 401 for colliding ID with mismatched roll_no, got {res2.status_code}: {res2.text}"


def test_id_card_image_persistence_and_admin_endpoint(client_and_db, tmp_path, monkeypatch):
    """
    BUG-08 regression test: Verify uploaded ID card image bytes are persisted
    and accessible to administrators via GET /auth/id-card-image/{student_id}.
    """
    client, db = client_and_db
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    # Create admin and student
    admin = User(
        name="Admin Reviewer",
        email="admin_reviewer@psit.ac.in",
        psit_roll_no="2100ADMIN00001",
        role=UserRole.ADMIN,
        verified=True,
    )
    student = User(
        name="Test Upload Student",
        email="test_student@psit.ac.in",
        psit_roll_no="2200320100999",
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add_all([admin, student])
    db.commit()
    db.refresh(admin)
    db.refresh(student)

    admin_token = create_access_token({"sub": str(admin.id), "roll_no": admin.psit_roll_no, "role": "admin"})
    student_token = create_access_token({"sub": str(student.id), "roll_no": student.psit_roll_no, "role": "student"})

    # Student uploads an ID card image
    image_b64 = _create_dummy_image_b64()
    with patch("app.services.auth_service.decode_qr_from_image", return_value="abcdef1234567890abcdef1234567890"):
        res = client.post(
            "/auth/verify-id",
            json={
                "psit_roll_no": student.psit_roll_no,
                "id_card_image_base64": image_b64,
            },
            headers={"Authorization": f"Bearer {student_token}"},
        )
    assert res.status_code == 200

    # Verify student has id_card_image_url set and file exists on disk
    db.expire_all()
    updated_student = db.query(User).filter(User.id == student.id).first()
    assert updated_student.id_card_image_url is not None
    saved_file = tmp_path / updated_student.id_card_image_url
    assert saved_file.is_file()

    # Non-admin request to view ID card image is blocked (403)
    res_student = client.get(
        f"/auth/id-card-image/{student.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student.status_code == 403

    # Admin request to view ID card image succeeds with image/jpeg media
    res_admin = client.get(
        f"/auth/id-card-image/{student.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.headers["content-type"] == "image/jpeg"
    assert len(res_admin.content) > 0


# =====================================================================
# 6. Forgot Password & OTP Reset Tests
# =====================================================================

def test_forgot_password_and_otp_reset(client_and_db):
    """
    User requests a password reset code via email, receives OTP,
    and resets password. DB is updated with new password hash.
    """
    client, db = client_and_db

    # Create a user with password set
    user = User(
        name="Forgot Tester",
        email="forgot@psit.ac.in",
        psit_roll_no="2200330100777",
        role=UserRole.STUDENT,
        verified=True,
        github_username="forgot-dev",
    )
    db.add(user)
    db.commit()

    # Set initial password
    from app.services.auth_service import set_user_password, verify_password
    set_user_password(db, user, "OldPassword123!")

    # 1. Request forgot password OTP
    res_forgot = client.post("/auth/forgot-password", json={"identifier": "2200330100777"})
    assert res_forgot.status_code == 200
    assert res_forgot.json()["success"] is True
    assert "Verification code has been sent" in res_forgot.json()["message"]

    # Retrieve stored OTP hash from DB to simulate user receiving the OTP code
    db.expire_all()
    user_db = db.query(User).filter(User.id == user.id).first()
    assert user_db.reset_otp_hash is not None
    assert user_db.reset_otp_expires is not None

    # Find matching 6-digit code by trying or extracting
    # Since we can patch request_password_reset_otp or check hash:
    # Let's test with wrong OTP first:
    res_wrong = client.post("/auth/reset-password", json={
        "identifier": "2200330100777",
        "otp": "000000",
        "new_password": "NewBrandPassword123!",
    })
    assert res_wrong.status_code == 400
    assert "Invalid verification code" in res_wrong.json()["detail"]

    # Now let's test request with mocked OTP
    with patch("secrets.randbelow", return_value=543210):
        client.post("/auth/forgot-password", json={"identifier": "2200330100777"})

    # OTP is 543210 + 100000 = 643210
    res_reset = client.post("/auth/reset-password", json={
        "identifier": "2200330100777",
        "otp": "643210",
        "new_password": "NewBrandPassword123!",
    })
    assert res_reset.status_code == 200
    assert res_reset.json()["success"] is True

    # Verify DB has new password hash and OTP cleared
    db.expire_all()
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.reset_otp_hash is None
    assert updated.reset_otp_expires is None
    assert verify_password("NewBrandPassword123!", updated.password_hash) is True

    # Test login with new password succeeds
    res_login = client.post("/auth/login", json={
        "identifier": "2200330100777",
        "password": "NewBrandPassword123!",
    })
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()


def test_forgot_password_nonexistent_user_returns_404(client_and_db):
    """Requesting password reset for unregistered roll or email returns 404."""
    client, _ = client_and_db
    res = client.post("/auth/forgot-password", json={"identifier": "9999999999999"})
    assert res.status_code == 404
    assert "No registered account found" in res.json()["detail"]


def test_reset_password_expired_otp_returns_400(client_and_db):
    """Submitting an expired OTP returns 400."""
    from datetime import datetime, timezone, timedelta
    from app.services.auth_service import hash_password

    client, db = client_and_db
    user = User(
        name="Expired OTP User",
        email="expired@psit.ac.in",
        psit_roll_no="2200330100888",
        role=UserRole.STUDENT,
        verified=True,
        reset_otp_hash=hash_password("112233"),
        reset_otp_expires=datetime.now(timezone.utc) - timedelta(minutes=5),  # expired 5 min ago
    )
    db.add(user)
    db.commit()

    res = client.post("/auth/reset-password", json={
        "identifier": "2200330100888",
        "otp": "112233",
        "new_password": "NewValidPassword123!",
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"]


def test_reset_password_single_use_replay_fails(client_and_db):
    """Using an OTP a second time fails with 400."""
    client, db = client_and_db
    user = User(
        name="Replay Tester",
        email="replay@psit.ac.in",
        psit_roll_no="2200330100999",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(user)
    db.commit()

    with patch("secrets.randbelow", return_value=123456):
        client.post("/auth/forgot-password", json={"identifier": "2200330100999"})

    # First reset succeeds
    res1 = client.post("/auth/reset-password", json={
        "identifier": "2200330100999",
        "otp": "223456",
        "new_password": "StrongPassword123!",
    })
    assert res1.status_code == 200

    # Second reset with the same OTP fails
    res2 = client.post("/auth/reset-password", json={
        "identifier": "2200330100999",
        "otp": "223456",
        "new_password": "AnotherStrongPassword123!",
    })
    assert res2.status_code == 400
    assert "No password reset request found" in res2.json()["detail"]


def test_reset_password_weak_password_rejected(client_and_db):
    """New password must meet complexity rules during reset."""
    client, db = client_and_db
    user = User(
        name="Complexity Tester",
        email="complex@psit.ac.in",
        psit_roll_no="2200330100666",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(user)
    db.commit()

    with patch("secrets.randbelow", return_value=111111):
        client.post("/auth/forgot-password", json={"identifier": "2200330100666"})

    # Too short
    res_short = client.post("/auth/reset-password", json={
        "identifier": "2200330100666",
        "otp": "211111",
        "new_password": "short",
    })
    assert res_short.status_code in [400, 422]


def test_github_oauth_login_url_generation(client_and_db):
    """GET /auth/github/login returns authorization URL and client_id."""
    client, _ = client_and_db
    res = client.get("/auth/github/login")
    assert res.status_code == 200
    data = res.json()
    assert "oauth_url" in data
    assert "client_id" in data
    assert "github.com/login/oauth/authorize" in data["oauth_url"]


def test_github_oauth_callback_flow(client_and_db):
    """POST /auth/github/callback exchanges code and links student identity."""
    client, db = client_and_db

    student = User(
        id=88,
        name="OAuth Student",
        email="oauth@psit.ac.in",
        psit_roll_no="2200330100088",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(student)
    db.commit()

    token = create_access_token({"sub": "88", "roll_no": "2200330100088", "role": "student"})

    fake_gh_profile = {
        "github_username": "oauth-contributor",
        "github_id": "778899",
    }

    with patch("app.routers.auth.exchange_github_oauth_code", new=AsyncMock(return_value=fake_gh_profile)):
        res = client.post(
            "/auth/github/callback",
            json={"code": "valid-oauth-code-123"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["github_username"] == "oauth-contributor"
    assert data["github_id"] == "778899"

    # Verify DB updated
    db.expire_all()
    updated = db.query(User).filter(User.id == 88).first()
    assert updated.github_username == "oauth-contributor"
    assert updated.github_id == "778899"




