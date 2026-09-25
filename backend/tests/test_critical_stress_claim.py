"""Critical Check 1: Concurrency stress testing for issue claim locking.
Simulates simultaneous race conditions where multiple students try to claim the same issue.
Guarantees that database partial unique index 'uq_active_claim_per_issue' and atomic
commit handling prevent double-claiming under high concurrency.
"""
import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import (
    User, UserRole,
    Repository, PlatformType,
    Issue, IssueDifficulty, IssueStatus,
    Claim, ClaimStatus
)


@pytest.fixture
def stress_setup(tmp_path):
    db_file = tmp_path / "stress_concurrency.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"timeout": 30.0},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")

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

    # Seed 10 verified students
    students = []
    for i in range(1, 11):
        user = User(
            id=i,
            name=f"Student {i}",
            email=f"student{i}@psit.ac.in",
            psit_roll_no=f"220{i:02d}",
            erp_verified=True,
            verified=True,
            github_username=f"student-{i}",
            role=UserRole.STUDENT,
        )
        students.append(user)
    db.add_all(students)

    # Seed repository and target issue
    repo = Repository(
        id=1,
        name="hacktoberfest-web",
        github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web",
        platform=PlatformType.WEB,
    )
    issue = Issue(
        id=100,
        repo_id=1,
        github_issue_id=100,
        title="High Priority Contested Issue",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.OPEN,
    )
    db.add_all([repo, issue])
    db.commit()

    yield client, TestingSessionLocal

    app.dependency_overrides.clear()


def test_concurrent_claim_race_condition(stress_setup):
    """
    Stress test: 10 concurrent threads simultaneously attempt to claim the exact same issue.
    Must ensure:
      - Exactly 1 claim succeeds (HTTP 201 Created)
      - Exactly 9 claims fail (HTTP 409 Conflict)
      - Exactly 1 active claim exists in the database
      - The issue status is CLAIMED
    """
    client, session_factory = stress_setup

    def attempt_claim(student_id: int):
        # Each thread performs POST /issues/{issue_id}/claim with user_id header
        headers = {"X-User-Id": str(student_id)}
        response = client.post("/issues/100/claim", headers=headers)
        return student_id, response.status_code, response.json()

    # Execute 10 simultaneous requests across worker threads
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_claim, student_id) for student_id in range(1, 11)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[1] == 201]
    rejections = [r for r in results if r[1] in [400, 409]]

    # Exactly 1 student claims successfully and all other 9 are rejected
    assert len(successes) == 1, f"Expected exactly 1 claim success, got {len(successes)}: {results}"
    assert len(rejections) == 9, f"Expected exactly 9 rejections, got {len(rejections)}: {results}"

    winning_student_id = successes[0][0]
    winning_data = successes[0][2]
    assert winning_data["user"]["id"] == winning_student_id
    assert winning_data["status"] == "active"

    # Verify database state
    db = session_factory()
    try:
        active_claims = (
            db.query(Claim)
            .filter(Claim.issue_id == 100, Claim.status == ClaimStatus.ACTIVE)
            .all()
        )
        assert len(active_claims) == 1
        assert active_claims[0].user_id == winning_student_id

        issue = db.query(Issue).filter(Issue.id == 100).first()
        assert issue.status == IssueStatus.CLAIMED
    finally:
        db.close()


def test_unclaim_and_reclaim_lifecycle(stress_setup):
    """
    Verify that when an issue is unclaimed, the partial unique index allows
    a new active claim to be created without constraint collision.
    """
    client, session_factory = stress_setup

    # Student 1 claims issue 100
    res1 = client.post("/issues/100/claim", headers={"X-User-Id": "1"})
    assert res1.status_code == 201

    # Student 2 tries to claim while active -> rejected (400 or 409)
    res2 = client.post("/issues/100/claim", headers={"X-User-Id": "2"})
    assert res2.status_code in [400, 409]

    # Student 1 unclaims issue 100
    unclaim_res = client.post("/issues/100/unclaim", headers={"X-User-Id": "1"})
    assert unclaim_res.status_code == 200

    # Now Student 2 claims issue 100 -> succeeds!
    res3 = client.post("/issues/100/claim", headers={"X-User-Id": "2"})
    assert res3.status_code == 201
    assert res3.json()["user"]["id"] == 2

    # Verify in DB: 1 released claim, 1 active claim
    db = session_factory()
    try:
        claims = db.query(Claim).filter(Claim.issue_id == 100).all()
        assert len(claims) == 2
        active_claims = [c for c in claims if c.status == ClaimStatus.ACTIVE]
        released_claims = [c for c in claims if c.status == ClaimStatus.RELEASED]
        assert len(active_claims) == 1
        assert active_claims[0].user_id == 2
        assert len(released_claims) == 1
        assert released_claims[0].user_id == 1
    finally:
        db.close()
