import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from app.db import Base


class PlatformType(str, enum.Enum):
    WEB = "web"
    ANDROID = "android"


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    github_repo_url = Column(String(500), unique=True, nullable=False)
    platform = Column(
        Enum(PlatformType, values_callable=lambda x: [e.value for e in x], name="platformtype"),
        nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    issues = relationship("Issue", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
