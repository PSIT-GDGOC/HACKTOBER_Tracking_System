from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Engine setup — supports SQLite for local testing and PostgreSQL for production
if settings.db_url.startswith("sqlite"):
    engine = create_engine(
        settings.db_url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    # SQLAlchemy 2.x defaults to psycopg (v3) for postgresql:// URLs.
    # We use psycopg2-binary, so explicitly set the dialect to postgresql+psycopg2://.
    _pg_url = settings.db_url.replace("postgresql://", "postgresql+psycopg2://", 1) \
                              .replace("postgres://", "postgresql+psycopg2://", 1)
    engine = create_engine(
        _pg_url,
        echo=settings.DEBUG,  # Only logs SQL in local dev when DEBUG=True
        pool_pre_ping=True,   # Validates connections before use (handles Supabase idle timeouts)
        pool_size=5,          # Persistent connections in pool
        max_overflow=10,      # Extra connections allowed under high load
        pool_recycle=300,     # Recycle connections every 5 min (prevents stale connections)
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
