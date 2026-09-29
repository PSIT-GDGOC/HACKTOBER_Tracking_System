from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.issue import IssueDifficulty, IssueStatus
from app.schemas.claim import ClaimResponse
from app.schemas.base import AppBaseModel


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


class RepositoryCreate(BaseModel):
    name: str = Field(..., max_length=255)
    github_repo_url: str = Field(..., max_length=500)
    platform: str = Field("web", max_length=50)


class IssueResponse(AppBaseModel):
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
    repos_discovered_count: Optional[int] = 0
