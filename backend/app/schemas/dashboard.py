from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.claim import ClaimUserBrief
from app.schemas.issue import RepositoryBrief
from app.schemas.pull_request import PRResponse


class ActiveClaimSummary(BaseModel):
    claim_id: int
    issue_id: int
    issue_title: str
    difficulty: str
    repo_name: str
    platform: str
    claimed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentDashboardResponse(BaseModel):
    user_id: int
    name: str
    psit_roll_no: str
    github_username: Optional[str] = None
    verified: bool
    active_claims_count: int
    prs_submitted_count: int
    prs_merged_count: int
    valid_contributions_count: int
    active_claims: List[ActiveClaimSummary] = []
    recent_prs: List[PRResponse] = []


class ReviewQueueItem(BaseModel):
    pr_id: int
    github_pr_id: int
    title: str
    repo_name: str
    contributor_name: str
    contributor_roll_no: str
    github_username: Optional[str] = None
    created_at: datetime
    status: str
    review_status: Optional[str] = None


class MaintainerDashboardResponse(BaseModel):
    maintainer_id: int
    pending_reviews_count: int
    approved_prs_count: int
    changes_requested_count: int
    review_queue: List[ReviewQueueItem] = []
    recently_reviewed: List[Dict[str, Any]] = []


class RepositoryDashboardResponse(BaseModel):
    repository: RepositoryBrief
    total_issues: int
    open_issues: int
    claimed_issues: int
    closed_issues: int
    total_prs: int
    open_prs: int
    merged_prs: int
    total_commits: int
    unique_contributors_count: int
    recent_activity: List[Dict[str, Any]] = []


class AdminDashboardResponse(BaseModel):
    total_registered_students: int
    verified_students: int
    pending_manual_review_students: int
    total_issues: int
    open_issues: int
    active_claims: int
    total_prs_submitted: int
    total_prs_merged: int
    total_commits: int
    pending_validations_count: int
    repositories_overview: List[Dict[str, Any]] = []
