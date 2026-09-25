from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.user import UserRole, VerificationMethod
from app.schemas.contribution import ContributionResponse


class UserPublicProfileResponse(BaseModel):
    id: int
    name: str
    github_username: Optional[str] = None
    role: UserRole
    verified: bool
    created_at: datetime
    contributions_count: int
    merged_prs_count: int
    active_claims_count: int
    recent_contributions: List[ContributionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    psit_roll_no: str
    verified: bool
    verified_at: Optional[datetime] = None
    verification_method: Optional[VerificationMethod] = None
    github_username: Optional[str] = None
    github_id: Optional[str] = None
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    github_username: Optional[str] = Field(None, min_length=1, max_length=100)
