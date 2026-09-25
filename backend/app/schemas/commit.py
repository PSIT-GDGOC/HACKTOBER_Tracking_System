from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.claim import ClaimUserBrief
from app.schemas.issue import RepositoryBrief


class CommitResponse(BaseModel):
    id: int
    repo_id: int
    github_commit_sha: str
    user_id: Optional[int] = None
    message: str
    issue_id: Optional[int] = None
    pr_id: Optional[int] = None
    committed_at: datetime
    user: Optional[ClaimUserBrief] = None
    repository: Optional[RepositoryBrief] = None

    model_config = ConfigDict(from_attributes=True)


class CommitListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[CommitResponse]
