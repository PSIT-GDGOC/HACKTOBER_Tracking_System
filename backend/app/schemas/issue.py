from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.issue import IssueDifficulty, IssueStatus
from app.schemas.claim import ClaimResponse


class IssueBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    difficulty: IssueDifficulty = IssueDifficulty.EASY
    category: Optional[str] = Field(None, max_length=100)
    tech_tags: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    status: IssueStatus = IssueStatus.OPEN


class IssueCreate(IssueBase):
    repo_id: int
    github_issue_id: int


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    difficulty: Optional[IssueDifficulty] = None
    category: Optional[str] = None
    tech_tags: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    status: Optional[IssueStatus] = None


class RepositoryBrief(BaseModel):
    id: int
    name: str
    platform: str
    github_repo_url: str

    model_config = ConfigDict(from_attributes=True)


class IssueResponse(BaseModel):
    id: int
    repo_id: int
    github_issue_id: int
    title: str
    description: Optional[str] = None
    difficulty: IssueDifficulty
    category: Optional[str] = None
    tech_tags: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    status: IssueStatus
    created_at: datetime
    updated_at: datetime
    repository: Optional[RepositoryBrief] = None
    active_claim: Optional[ClaimResponse] = None

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[IssueResponse]


class IssueSyncResponse(BaseModel):
    message: str
    synced_count: int
    created_count: int
    updated_count: int
