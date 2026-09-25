import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from app.db import Base


class PRStatus(str, enum.Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    DRAFT = "draft"


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_pr_id = Column(Integer, unique=True, index=True, nullable=False)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    status = Column(
        Enum(PRStatus, values_callable=lambda x: [e.value for e in x], name="prstatus"),
        default=PRStatus.OPEN,
        nullable=False,
        index=True
    )
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="pull_requests")
    issue = relationship("Issue", back_populates="pull_requests")
    user = relationship("User", foreign_keys=[user_id], back_populates="pull_requests")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    commits = relationship("Commit", back_populates="pull_request")
    reviews = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")
    contributions = relationship("Contribution", back_populates="pull_request")

    __table_args__ = (
        Index("ix_pr_repo_status", "repo_id", "status"),
    )
