from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.pull_request import PRStatus
from app.models.review import ReviewStatus
from app.schemas.claim import ClaimUserBrief
from app.schemas.issue import RepositoryBrief


class ReviewDetail(BaseModel):
    id: int
    pr_id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None
    status: ReviewStatus
    comment: Optional[str] = None
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LinkedIssueBrief(BaseModel):
    id: int
    github_issue_id: int
    title: str
    difficulty: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class PRResponse(BaseModel):
    id: int
    repo_id: int
    github_pr_id: int
    issue_id: Optional[int] = None
    user_id: int
    title: str
    status: PRStatus
    reviewer_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[ClaimUserBrief] = None
    reviewer: Optional[ClaimUserBrief] = None
    repository: Optional[RepositoryBrief] = None
    linked_issue: Optional[LinkedIssueBrief] = None
    reviews: List[ReviewDetail] = []

    model_config = ConfigDict(from_attributes=True)


class PRListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[PRResponse]


# Aliases for frontend openapi generator
PullRequestResponse = PRResponse
PullRequestListResponse = PRListResponse
