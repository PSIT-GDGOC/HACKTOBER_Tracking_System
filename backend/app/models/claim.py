import enum
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, Index, text
from sqlalchemy.orm import relationship
from app.db import Base


class ClaimStatus(str, enum.Enum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    COMPLETED = "completed"


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    claimed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(
        Enum(ClaimStatus, values_callable=lambda x: [e.value for e in x], name="claimstatus"),
        default=ClaimStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Relationships
    issue = relationship("Issue", back_populates="claims")
    user = relationship("User", back_populates="claims")

    __table_args__ = (
        # Partial unique index ensuring only ONE active claim per issue at any time
        Index(
            "uq_active_claim_per_issue",
            "issue_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'")
        ),
    )
