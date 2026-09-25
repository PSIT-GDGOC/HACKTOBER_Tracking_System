from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.claim import ClaimStatus


class ClaimBase(BaseModel):
    issue_id: int
    user_id: int
    status: ClaimStatus = ClaimStatus.ACTIVE


class ClaimCreate(BaseModel):
    pass  # issue_id taken from path, user_id taken from authenticated session


class ClaimUserBrief(BaseModel):
    id: int
    name: str
    psit_roll_no: str
    github_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: int
    issue_id: int
    user_id: int
    claimed_at: datetime
    status: ClaimStatus
    user: Optional[ClaimUserBrief] = None

    model_config = ConfigDict(from_attributes=True)


class ClaimReleaseResponse(BaseModel):
    message: str
    issue_id: int
    claim_id: int
    status: ClaimStatus
