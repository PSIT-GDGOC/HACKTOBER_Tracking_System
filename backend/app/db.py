from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Engine setup — pool settings tuned for cloud-hosted PostgreSQL (Supabase)
# Supabase free tier allows ~50 connections; pool_size=5 is conservative and safe.
engine = create_engine(
    settings.db_url,      # Uses property that rewrites postgres:// -> postgresql://
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
