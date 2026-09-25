from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.contribution import ContributionStatus, ContributionValidation
from app.schemas.claim import ClaimUserBrief
from app.schemas.pull_request import LinkedIssueBrief


class TimelineEvent(BaseModel):
    status: str
    timestamp: str
    detail: Optional[str] = None


class ContributionPRBrief(BaseModel):
    id: int
    github_pr_id: int
    title: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ContributionResponse(BaseModel):
    id: int
    user_id: int
    issue_id: int
    pr_id: Optional[int] = None
    status: ContributionStatus
    validation_status: ContributionValidation
    timeline_json: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    user: Optional[ClaimUserBrief] = None
    issue: Optional[LinkedIssueBrief] = None
    pull_request: Optional[ContributionPRBrief] = None

    model_config = ConfigDict(from_attributes=True)


class UserContributionTimelineResponse(BaseModel):
    user_id: int
    user: Optional[ClaimUserBrief] = None
    total_contributions: int
    valid_contributions_count: int
    merged_count: int
    in_progress_count: int
    items: List[ContributionResponse]


# Alias for frontend openapi generator
ContributionTimelineResponse = UserContributionTimelineResponse


class ContributionValidationUpdate(BaseModel):
    validation_status: ContributionValidation
    note: Optional[str] = None
