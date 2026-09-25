import enum
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from app.db import Base


class ReviewStatus(str, enum.Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"
    DISMISSED = "dismissed"


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum(ReviewStatus, values_callable=lambda x: [e.value for e in x], name="reviewstatus"),
        nullable=False,
        index=True
    )
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_given")

    __table_args__ = (
        Index("ix_reviews_pr_status", "pr_id", "status"),
    )
