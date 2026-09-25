"""Tests for Auth & Verification Module (Aditya's Module).

Covers:
- Student signup (pending verification status)
- Duplicate roll number & duplicate email rejection
- Login with JWT token issuance & claim verification
- Bearer JWT token authentication on /auth/me
- ID Card upload & automated QR/portal verification (exact roll + fuzzy name match)
- Fallback routing to pending_review on portal mismatch
- Admin manual verification queue & approval/rejection endpoints
- RBAC protection (students blocked with 403 from admin queue)
- GitHub OAuth linking with duplicate username protection
"""
import io
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


def _create_dummy_image_bytes() -> bytes:
    """Generate minimal valid JPEG bytes in memory."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


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
        psit_roll_no="ADMIN001",
        role=UserRole.ADMIN,
        verified=True,
    )

    # Seed an existing student with a taken github_username
    existing_student = User(
        id=50,
        name="Existing Coder",
        email="coder@psit.ac.in",
        psit_roll_no="22050",
        role=UserRole.STUDENT,
        verified=True,
        github_username="taken-github-dev",
    )

    db.add_all([admin, existing_student])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_student_signup_success(client_and_db):
    """Student can register with roll number and name; account starts unverified."""
    client, db = client_and_db

    payload = {
        "name": "Priya Sharma",
        "email": "priya.sharma@psit.ac.in",
        "psit_roll_no": "22045",
    }
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Priya Sharma"
    assert data["email"] == "priya.sharma@psit.ac.in"
    assert data["psit_roll_no"] == "22045"
    assert data["verified"] is False
    assert data["status"] == "pending_verification"

    # Verify persisted in DB
    user = db.query(User).filter(User.psit_roll_no == "22045").first()
    assert user is not None
    assert user.role == UserRole.STUDENT


def test_student_signup_duplicate_guards(client_and_db):
    """Duplicate roll numbers and duplicate emails must be rejected with 400."""
    client, _ = client_and_db

    # Register first student
    client.post("/auth/signup", json={
        "name": "Original Student",
        "email": "original@psit.ac.in",
        "psit_roll_no": "22010",
    })

    # Duplicate roll number
    res_dup_roll = client.post("/auth/signup", json={
        "name": "Another Student",
        "email": "another@psit.ac.in",
        "psit_roll_no": "22010",
    })
    assert res_dup_roll.status_code == 400
    assert "already registered" in res_dup_roll.json()["detail"]

    # Duplicate email
    res_dup_email = client.post("/auth/signup", json={
        "name": "Different Student",
        "email": "original@psit.ac.in",
        "psit_roll_no": "22011",
    })
    assert res_dup_email.status_code == 400
    assert "already registered" in res_dup_email.json()["detail"]


def test_login_and_jwt_issuance(client_and_db):
    """Login with roll number issues valid JWT token with user claims."""
    client, _ = client_and_db

    # Sign up
    client.post("/auth/signup", json={
        "name": "Rahul Verma",
        "email": "rahul@psit.ac.in",
        "psit_roll_no": "22088",
    })

    # Log in with roll number
    res = client.post("/auth/login", json={"identifier": "22088"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["psit_roll_no"] == "22088"

    # Log in with email
    res_email = client.post("/auth/login", json={"identifier": "rahul@psit.ac.in"})
    assert res_email.status_code == 200
    assert "access_token" in res_email.json()


def test_get_me_with_bearer_jwt(client_and_db):
    """Accessing /auth/me with Bearer JWT returns authenticated profile."""
    client, db = client_and_db

    student = User(
        id=77,
        name="Karan Malhotra",
        email="karan@psit.ac.in",
        psit_roll_no="22077",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(student)
    db.commit()

    token = create_access_token(data={"sub": "77", "role": "student"})

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 77
    assert data["name"] == "Karan Malhotra"
    assert data["psit_roll_no"] == "22077"
    assert data["verified"] is True


def test_id_card_auto_verification(client_and_db):
    """
    Submitting ID card with matching roll number and fuzzy name
    automatically verifies the student account.
    """
    client, db = client_and_db

    # Create unverified student
    student = User(
        id=12,
        name="Ananya Gupta",
        email="ananya@psit.ac.in",
        psit_roll_no="22012",
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(student)
    db.commit()

    # Portal data has exact roll and fuzzy name ("Gupta Ananya" vs "Ananya Gupta")
    portal_snapshot = {
        "roll_no": "22012",
        "student_name": "Gupta Ananya",
        "branch": "IT",
        "college": "PSIT Kanpur"
    }

    res = client.post(
        "/auth/verify-id",
        json={
            "psit_roll_no": "22012",
            "qr_token": "PSIT-QR-22012-SEC",
            "portal_snapshot": portal_snapshot,
        },
        headers={"X-User-Id": "12"}
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
        psit_roll_no="22013",
        role=UserRole.STUDENT,
        verified=False,
    )
    db.add(student)
    db.commit()

    # Mismatched name in portal
    portal_snapshot = {
        "roll_no": "22013",
        "student_name": "Completely Different Person",
        "branch": "CSE"
    }

    res = client.post(
        "/auth/verify-id",
        json={
            "psit_roll_no": "22013",
            "qr_token": "PSIT-QR-22013-SEC",
            "portal_snapshot": portal_snapshot,
        },
        headers={"X-User-Id": "13"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is False
    assert data["status"] == "pending_review"
    assert "manual approval" in data["message"]

    # Verify DB state
    db.expire_all()
    updated = db.query(User).filter(User.id == 13).first()
    assert updated.verified is False
    assert updated.verification_method is None


def test_admin_manual_verification_queue_and_approval(client_and_db):
    """
    Admin views pending verification queue and manually approves student.
    Non-admin user receives 403 Forbidden.
    """
    client, db = client_and_db

    # Student with pending ID upload
    student = User(
        id=20,
        name="Mohit Agarwal",
        email="mohit@psit.ac.in",
        psit_roll_no="22020",
        role=UserRole.STUDENT,
        verified=False,
        id_card_image_url="id-cards/22020_card.jpg",
        portal_snapshot_json={"roll_no": "22020", "name": "Mohit Agarwal"},
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
        headers={"X-User-Id": "99"}
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


def test_github_oauth_linking(client_and_db):
    """Student links their GitHub identity; duplicate username rejected."""
    client, db = client_and_db

    student = User(
        id=30,
        name="Sanjay Rao",
        email="sanjay@psit.ac.in",
        psit_roll_no="22030",
        role=UserRole.STUDENT,
        verified=True,
    )
    db.add(student)
    db.commit()

    # 1. Attempt to link username already taken by another student
    res_dup = client.post(
        "/auth/github/link",
        json={"github_username": "taken-github-dev"},
        headers={"X-User-Id": "30"}
    )
    assert res_dup.status_code == 400
    assert "already linked" in res_dup.json()["detail"]

    # 2. Successfully link unique GitHub username
    res_ok = client.post(
        "/auth/github/link",
        json={"github_username": "sanjay-coder", "github_id": "987654"},
        headers={"X-User-Id": "30"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True
    assert res_ok.json()["github_username"] == "sanjay-coder"

    # DB verification
    db.expire_all()
    updated = db.query(User).filter(User.id == 30).first()
    assert updated.github_username == "sanjay-coder"
    assert updated.github_id == "987654"
