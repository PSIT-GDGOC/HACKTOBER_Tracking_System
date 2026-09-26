import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, JSON, Index, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from app.db import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    MAINTAINER = "maintainer"
    ADMIN = "admin"


class VerificationMethod(str, enum.Enum):
    QR_AUTO = "qr_auto"
    MANUAL = "manual"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_verified_psit_roll_no",
            "psit_roll_no",
            unique=True,
            postgresql_where=text("verified = TRUE"),
            sqlite_where=text("verified = 1"),
        ),
        Index(
            "ix_users_verified_qr_token",
            "qr_token",
            unique=True,
            postgresql_where=text("verified = TRUE AND qr_token IS NOT NULL"),
            sqlite_where=text("verified = 1 AND qr_token IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), index=True, nullable=False)
    psit_roll_no = Column(String(50), index=True, nullable=False)
    
    # v2 ID Card & QR Verification fields
    id_card_image_url = Column(String(500), nullable=True)
    qr_token = Column(String(500), nullable=True)
    portal_snapshot_json = Column(JSON, nullable=True)
    verification_method = Column(
        Enum(VerificationMethod, values_callable=lambda x: [e.value for e in x], name="verification_method"),
        nullable=True
    )
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)

    github_username = Column(String(100), unique=True, index=True, nullable=True)
    github_id = Column(String(100), unique=True, nullable=True)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x], name="userrole"),
        default=UserRole.STUDENT,
        nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @hybrid_property
    def erp_verified(self):
        """Deprecated v1 alias for backwards compatibility during migration."""
        return self.verified

    @erp_verified.setter
    def erp_verified(self, value: bool):
        self.verified = bool(value)

    # Relationships
    claims = relationship("Claim", back_populates="user", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", foreign_keys="PullRequest.user_id", back_populates="user")
    reviews_given = relationship("Review", foreign_keys="Review.reviewer_id", back_populates="reviewer")
    commits = relationship("Commit", back_populates="user")
    contributions = relationship("Contribution", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("ActivityFeed", back_populates="actor")
