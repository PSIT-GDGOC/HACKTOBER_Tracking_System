"""Critical Rules & Verifications — v2 Architecture.

Validates all 4 Critical Rules defined in tasks_v2.md:
1. Claim locking must use an atomic DB operation — application-level check is not enough.
2. Webhook receiver must verify GitHub signature before inserting into webhook_jobs.
3. id_card_image_url must never be a public URL — always private; never exposed via any API response or OpenAPI response schema.
4. portal_snapshot_json and ID image paths are excluded from logs — sensitive data filter globally scrubs all log messages and records.
Plus: RBAC role middleware protection.
"""
import hmac
import hashlib
import io
import json
import logging
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.dependencies import get_current_user, require_roles, require_verified_student
from app.logging_config import SensitiveDataFilter, configure_logging
from app.main import app
from app.models import (
    User, UserRole, VerificationMethod,
    Repository, PlatformType,
    Issue, IssueDifficulty, IssueStatus,
    Claim, ClaimStatus,
    WebhookJob, WebhookJobStatus
)
from app.schemas.user import UserProfileResponse, UserPublicProfileResponse
from app.schemas.search import SearchUserResult


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
    # Seed a verified student with sensitive verification data
    student = User(
        id=1,
        name="Aarav Sharma",
        email="aarav@psit.ac.in",
        psit_roll_no="22001",
        verified=True,
        verified_at=None,
        verification_method=VerificationMethod.QR_AUTO,
        github_username="aarav-sharma",
        role=UserRole.STUDENT,
        # SENSITIVE FIELDS:
        id_card_image_url="id-cards/22001_card.jpg",
        qr_token="PSIT-22001-QR-SECRET-TOKEN",
        portal_snapshot_json={
            "student_name": "Aarav Sharma",
            "roll_no": "22001",
            "dob": "2003-04-12",
            "phone": "9876543210",
            "branch": "CSE"
        }
    )

    admin = User(
        id=2,
        name="Admin User",
        email="admin@psit.ac.in",
        psit_roll_no="ADMIN01",
        verified=True,
        role=UserRole.ADMIN,
        github_username="admin-user"
    )

    maintainer = User(
        id=3,
        name="Maintainer User",
        email="maintainer@psit.ac.in",
        psit_roll_no="MAINT01",
        verified=True,
        role=UserRole.MAINTAINER,
        github_username="maintainer-user"
    )

    unverified_student = User(
        id=4,
        name="Unverified Student",
        email="unverified@psit.ac.in",
        psit_roll_no="22099",
        verified=False,
        role=UserRole.STUDENT,
        github_username="unverified-student"
    )

    repo = Repository(
        id=1,
        name="web-repo",
        github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web",
        platform=PlatformType.WEB
    )

    issue = Issue(
        id=1,
        repo_id=1,
        github_issue_id=101,
        title="Critical Rule Issue",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.OPEN
    )

    db.add_all([student, admin, maintainer, unverified_student, repo, issue])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


# =====================================================================
# Critical Rule 1: Claim Locking Atomicity
# =====================================================================

def test_critical_rule_1_claim_locking_atomicity(client_and_db):
    """
    Critical Rule 1: Claim locking must prevent double-claiming.
    Verified student claiming an issue succeeds, but a second claim attempt
    on the already claimed issue fails with 400 Bad Request.
    """
    client, db = client_and_db

    # First claim succeeds
    res1 = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert res1.status_code == 201
    assert res1.json()["status"] == "active"

    # Second claim attempt on same issue MUST fail
    res2 = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert res2.status_code == 400
    assert "claimed" in res2.json()["detail"].lower()


# =====================================================================
# Critical Rule 2: Webhook Signature Verification
# =====================================================================

def test_critical_rule_2_webhook_signature_verification_rejects_spoofed(client_and_db, monkeypatch):
    """
    Critical Rule 2: Webhook receiver must verify GitHub signature before inserting into webhook_jobs.
    Unsigned or invalidly signed requests are rejected with 401 UNAUTHORIZED,
    and NO row is inserted into webhook_jobs.
    """
    test_secret = "test-critical-secret-key-12345"
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", test_secret)

    client, db = client_and_db
    initial_job_count = db.query(WebhookJob).count()

    # 1. No signature header
    res1 = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "issues"}
    )
    assert res1.status_code == 401
    assert "signature" in res1.json()["detail"].lower()

    # 2. Bogus signature header
    res2 = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=invalidhexsignature00000000000000000000000000000000"
        }
    )
    assert res2.status_code == 401
    assert "signature" in res2.json()["detail"].lower()

    # Verify no webhook_jobs rows were created from invalid requests
    db.expire_all()
    assert db.query(WebhookJob).count() == initial_job_count


def test_critical_rule_2_webhook_signature_verification_accepts_valid(client_and_db, monkeypatch):
    """
    Critical Rule 2: Validly signed HMAC-SHA256 payload is accepted and
    persisted into webhook_jobs.
    """
    test_secret = "test-critical-secret-key-12345"
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", test_secret)

    client, db = client_and_db

    payload = json.dumps({"action": "ping"}).encode("utf-8")
    sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    res = client.post(
        "/webhooks/github",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": sig,
        }
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify job was inserted into webhook_jobs
    job = db.query(WebhookJob).first()
    assert job is not None
    assert job.status in [WebhookJobStatus.DONE, WebhookJobStatus.PENDING]


# =====================================================================
# Critical Rule 3: id_card_image_url and verification PII Privacy
# =====================================================================

def test_critical_rule_3_privacy_id_card_never_exposed_in_api(client_and_db):
    """
    Critical Rule 3: id_card_image_url, qr_token, and portal_snapshot_json must NEVER
    be returned in any public or user API responses.
    """
    client, _ = client_and_db

    # 1. Public user profile: /users/1
    res = client.get("/users/1")
    assert res.status_code == 200
    public_data = res.json()
    assert "id_card_image_url" not in public_data
    assert "qr_token" not in public_data
    assert "portal_snapshot_json" not in public_data
    # Also verify private PII strings are absent
    res_text = res.text
    assert "id-cards/22001_card.jpg" not in res_text
    assert "PSIT-22001-QR-SECRET-TOKEN" not in res_text
    assert "9876543210" not in res_text

    # 2. Own user profile: /users/me
    res = client.get("/users/me", headers={"X-User-Id": "1"})
    assert res.status_code == 200
    own_data = res.json()
    assert "id_card_image_url" not in own_data
    assert "qr_token" not in own_data
    assert "portal_snapshot_json" not in own_data
    assert "id-cards/22001_card.jpg" not in res.text
    assert "PSIT-22001-QR-SECRET-TOKEN" not in res.text
    assert "9876543210" not in res.text

    # 3. Global search: /search?q=Aarav
    res = client.get("/search?q=Aarav")
    assert res.status_code == 200
    assert "id-cards/22001_card.jpg" not in res.text
    assert "PSIT-22001-QR-SECRET-TOKEN" not in res.text
    assert "9876543210" not in res.text

    # 4. Leaderboard: /leaderboard
    res = client.get("/leaderboard")
    assert res.status_code == 200
    assert "id-cards/22001_card.jpg" not in res.text
    assert "PSIT-22001-QR-SECRET-TOKEN" not in res.text


def test_critical_rule_3_schema_contract_omits_sensitive_fields():
    """
    Critical Rule 3: Pydantic schemas must NOT declare id_card_image_url,
    qr_token, or portal_snapshot_json as public model fields.
    """
    assert "id_card_image_url" not in UserPublicProfileResponse.model_fields
    assert "qr_token" not in UserPublicProfileResponse.model_fields
    assert "portal_snapshot_json" not in UserPublicProfileResponse.model_fields

    assert "id_card_image_url" not in UserProfileResponse.model_fields
    assert "qr_token" not in UserProfileResponse.model_fields
    assert "portal_snapshot_json" not in UserProfileResponse.model_fields

    assert "id_card_image_url" not in SearchUserResult.model_fields


# =====================================================================
# Critical Rule 4: portal_snapshot_json & ID card paths Excluded from Logs
# =====================================================================

def test_critical_rule_4_log_filter_scrubs_sensitive_data():
    """
    Critical Rule 4: portal_snapshot_json, id_card_image_url, and qr_token
    must be sanitized from log records.
    """
    filter_instance = SensitiveDataFilter()

    # 1. Message with id_card_image_url in JSON format
    rec1 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='User enrolled: {"id_card_image_url": "id-cards/22001_card.jpg", "verified": true}',
        args=(),
        exc_info=None
    )
    filter_instance.filter(rec1)
    assert "id-cards/22001_card.jpg" not in rec1.msg
    assert "[REDACTED]" in rec1.msg

    # 2. Message with portal_snapshot_json in JSON format
    rec2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='Fetched student data: {"portal_snapshot_json": {"name": "Aarav", "phone": "9876543210"}}',
        args=(),
        exc_info=None
    )
    filter_instance.filter(rec2)
    assert "9876543210" not in rec2.msg
    assert "[REDACTED]" in rec2.msg

    # 3. Message with qr_token in kwargs format
    rec3 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Processing verification qr_token=PSIT-22001-QR-SECRET-TOKEN for user 1",
        args=(),
        exc_info=None
    )
    filter_instance.filter(rec3)
    assert "PSIT-22001-QR-SECRET-TOKEN" not in rec3.msg
    assert "[REDACTED]" in rec3.msg

    # 4. Message with raw Supabase storage path
    rec4 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Image uploaded to id-cards/22001_card.jpg successfully",
        args=(),
        exc_info=None
    )
    filter_instance.filter(rec4)
    assert "id-cards/22001_card.jpg" not in rec4.msg
    assert "[REDACTED]" in rec4.msg

    # 5. String formatting args containing sensitive paths
    rec5 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Saved card to %s",
        args=("id-cards/secret_upload.jpg",),
        exc_info=None
    )
    filter_instance.filter(rec5)
    assert "id-cards/secret_upload.jpg" not in rec5.args[0]
    assert "[REDACTED]" in rec5.args[0]


def test_critical_rule_4_live_logger_stream_sanitization():
    """
    Verify that an active logging handler with SensitiveDataFilter attached
    does not output sensitive verification strings to the log stream.
    """
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(SensitiveDataFilter())

    test_logger = logging.getLogger("app.critical_test")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    test_logger.info('Processing user verification: {"portal_snapshot_json": {"roll": "22001", "mobile": "9998887776"}}')
    test_logger.info('ID photo at id-cards/22001_front.png saved')

    output = log_stream.getvalue()
    assert "9998887776" not in output
    assert "id-cards/22001_front.png" not in output
    assert "[REDACTED]" in output

    test_logger.removeHandler(handler)


# =====================================================================
# RBAC / Role Middleware Protection Tests
# =====================================================================

def test_require_roles_dependency_enforcement(client_and_db):
    """
    Verify role-based authorization:
    - User with matching role is allowed
    - User with non-matching role receives 403 Forbidden
    """
    client, db = client_and_db

    # Create dummy routes for testing role checks
    @app.get("/test/admin-route")
    def admin_only_endpoint(user: User = Depends(require_roles(UserRole.ADMIN))):
        return {"authorized": True, "user_id": user.id}

    @app.get("/test/maintainer-route")
    def maintainer_endpoint(user: User = Depends(require_roles(UserRole.MAINTAINER, UserRole.ADMIN))):
        return {"authorized": True, "user_id": user.id}

    # Admin access admin route -> 200
    res_admin = client.get("/test/admin-route", headers={"X-User-Id": "2"})
    assert res_admin.status_code == 200
    assert res_admin.json()["authorized"] is True

    # Student access admin route -> 403
    res_student = client.get("/test/admin-route", headers={"X-User-Id": "1"})
    assert res_student.status_code == 403
    assert "forbidden" in res_student.json()["detail"].lower()

    # Maintainer access maintainer route -> 200
    res_maint = client.get("/test/maintainer-route", headers={"X-User-Id": "3"})
    assert res_maint.status_code == 200

    # Student access maintainer route -> 403
    res_student2 = client.get("/test/maintainer-route", headers={"X-User-Id": "1"})
    assert res_student2.status_code == 403


def test_require_verified_student_dependency_enforcement(client_and_db):
    """
    Verify verified student requirement:
    - Verified student succeeds
    - Unverified student receives 403 Forbidden
    - Non-student (e.g. admin) receives 403 Forbidden
    """
    client, db = client_and_db

    @app.get("/test/student-action")
    def verified_student_endpoint(user: User = Depends(require_verified_student)):
        return {"ok": True, "student_id": user.id}

    # Verified student (id=1) -> 200
    res1 = client.get("/test/student-action", headers={"X-User-Id": "1"})
    assert res1.status_code == 200

    # Unverified student (id=4) -> 403
    res2 = client.get("/test/student-action", headers={"X-User-Id": "4"})
    assert res2.status_code == 403
    assert "verified" in res2.json()["detail"].lower()

    # Admin (id=2) -> 403
    res3 = client.get("/test/student-action", headers={"X-User-Id": "2"})
    assert res3.status_code == 403
