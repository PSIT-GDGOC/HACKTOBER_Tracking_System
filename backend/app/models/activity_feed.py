from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db import Base


class ActivityFeed(Base):
    __tablename__ = "activity_feed"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(100), nullable=False, index=True)  # e.g. "claim_created", "pr_opened", "pr_merged"
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_type = Column(String(100), nullable=False)       # e.g. "issue", "pull_request", "repository"
    target_id = Column(Integer, nullable=False)             # ID of target entity
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    actor = relationship("User", back_populates="activities")

    __table_args__ = (
        Index("ix_activity_feed_type_created", "type", "created_at"),
    )
