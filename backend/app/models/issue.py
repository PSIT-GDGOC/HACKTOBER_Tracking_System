import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Index
from sqlalchemy.orm import relationship
from app.db import Base


class IssueDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_issue_id = Column(Integer, unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(
        Enum(IssueDifficulty, values_callable=lambda x: [e.value for e in x], name="issuedifficulty"),
        default=IssueDifficulty.EASY,
        nullable=False
    )
    category = Column(String(100), nullable=True)
    tech_tags = Column(JSON, default=list, nullable=False)
    labels = Column(JSON, default=list, nullable=False)
    status = Column(
        Enum(IssueStatus, values_callable=lambda x: [e.value for e in x], name="issuestatus"),
        default=IssueStatus.OPEN,
        nullable=False,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="issues")
    claims = relationship("Claim", back_populates="issue", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="issue")
    commits = relationship("Commit", back_populates="issue")
    contributions = relationship("Contribution", back_populates="issue")

    __table_args__ = (
        Index("ix_issues_repo_status", "repo_id", "status"),
    )
