"""Shared request reservations, containing only keyed hashes of identifiers."""
from sqlalchemy import Column, String, Float, JSON

from app.db import Base


class EmailRateLimit(Base):
    __tablename__ = "email_rate_limits"

    key = Column(String(64), primary_key=True)
    timestamps = Column(JSON, nullable=False)
    expires_at = Column(Float, nullable=False, index=True)
