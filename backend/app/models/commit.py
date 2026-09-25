from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db import Base


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_commit_sha = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(Text, nullable=False)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    committed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="commits")
    user = relationship("User", back_populates="commits")
    issue = relationship("Issue", back_populates="commits")
    pull_request = relationship("PullRequest", back_populates="commits")

    __table_args__ = (
        Index("ix_commits_repo_user", "repo_id", "user_id"),
    )
