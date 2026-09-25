import enum
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, JSON, Index
from sqlalchemy.orm import relationship
from app.db import Base


class ContributionStatus(str, enum.Enum):
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    PR_SUBMITTED = "pr_submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    ACCEPTED = "accepted"
    MERGED = "merged"


class ContributionValidation(str, enum.Enum):
    VALID = "valid"
    PENDING = "pending"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(
        Enum(ContributionStatus, values_callable=lambda x: [e.value for e in x], name="contributionstatus"),
        default=ContributionStatus.CLAIMED,
        nullable=False,
        index=True
    )
    validation_status = Column(
        Enum(ContributionValidation, values_callable=lambda x: [e.value for e in x], name="contributionvalidation"),
        default=ContributionValidation.PENDING,
        nullable=False,
        index=True
    )
    timeline_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="contributions")
    issue = relationship("Issue", back_populates="contributions")
    pull_request = relationship("PullRequest", back_populates="contributions")

    __table_args__ = (
        Index("ix_contributions_user_status", "user_id", "status"),
    )
