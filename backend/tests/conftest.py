"""Shared pytest fixtures for the entire test suite.

All tests run fully in-process using FastAPI's TestClient backed by an
in-memory SQLite database.  No network calls.  No port binding.  Safe for CI.

Design
------
- ``engine`` / ``db_session`` / ``client`` are session-scoped so the DB is
  created once per pytest session, not once per test.  Individual tests that
  need isolation should use transactions or create their own fixture.
- ``get_db`` is overridden via FastAPI's dependency injection so the app
  uses the test DB instead of whatever DATABASE_URL is set in the environment.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

# ─── Database ─────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create a single in-memory SQLite engine for the whole test session."""
    _engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="session")
def SessionLocal(engine):  # noqa: N802
    """Session factory bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── FastAPI TestClient ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client(SessionLocal):  # noqa: N803
    """
    FastAPI TestClient that talks to the app in-process.

    ``get_db`` is overridden so the app uses the shared in-memory SQLite DB
    instead of the real database configured in .env.
    """
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
