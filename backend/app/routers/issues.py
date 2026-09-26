from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User, IssueDifficulty, IssueStatus, Repository
from app.schemas.issue import IssueResponse, IssueListResponse, IssueSyncResponse, RepositoryBrief
from app.schemas.claim import ClaimResponse, ClaimReleaseResponse
from app.services.issue_service import (
    sync_issues_from_github,
    get_issues,
    get_issue_by_id,
    claim_issue,
    unclaim_issue,
)

router = APIRouter(prefix="/issues", tags=["Issues"])


@router.get("/repositories", response_model=List[RepositoryBrief], summary="List registered repositories")
def list_repositories(db: Session = Depends(get_db)):
    """Return all registered official repositories."""
    return db.query(Repository).all()


@router.post("/sync", response_model=IssueSyncResponse, summary="Sync issues from GitHub")
def sync_issues(
    repo_id: Optional[int] = Query(None, description="Optional Repository ID to sync. If omitted, all repos sync."),
    db: Session = Depends(get_db),
):
    """
    Backfill / sync issues from GitHub REST API for registered official repositories.
    Parses labels to automatically classify difficulty, category, and tech tags.
    """
    result = sync_issues_from_github(db=db, repo_id=repo_id)
    return result


@router.get("", response_model=IssueListResponse, summary="List issues with filters")
def list_issues(
    repo_id: Optional[int] = Query(None, description="Filter by repository ID"),
    platform: Optional[str] = Query(None, description="Filter by platform: web or android/phone"),
    difficulty: Optional[IssueDifficulty] = Query(None, description="Filter by difficulty (easy, medium, hard)"),
    tech_tag: Optional[str] = Query(None, description="Filter by technology tag (e.g. React, Kotlin)"),
    category: Optional[str] = Query(None, description="Filter by category (frontend, backend, ui/ux, etc.)"),
    status: Optional[IssueStatus] = Query(None, description="Filter by status (open, claimed, in_progress, closed)"),
    search: Optional[str] = Query(None, description="Search in issue title or description"),
    skip: int = Query(0, ge=0, description="Offset pagination skip"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """
    Explore issues with multi-attribute filtering (repo, platform, difficulty, category, tech tag, status, keyword search).
    """
    items, total = get_issues(
        db=db,
        repo_id=repo_id,
        platform=platform,
        difficulty=difficulty,
        tech_tag=tech_tag,
        category=category,
        status_filter=status,
        search=search,
        skip=skip,
        limit=limit,
    )
    return IssueListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


@router.get("/{issue_id}", response_model=IssueResponse, summary="Get issue details")
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetch comprehensive details for a single issue, including repository info and active claim details if claimed.
    """
    return get_issue_by_id(db=db, issue_id=issue_id)


@router.post("/{issue_id}/claim", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED, summary="Claim an open issue")
def claim(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Atomically claim an open issue.
    - Locks issue row and catches race conditions via database unique constraint.
    - Enforces maximum active claim limit per student.
    - Transitions issue status to 'claimed' and creates contribution record.
    """
    return claim_issue(db=db, issue_id=issue_id, user_id=current_user.id)


@router.post("/{issue_id}/unclaim", response_model=ClaimReleaseResponse, summary="Release an active claim")
def unclaim(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Release a claimed issue back to 'open' status.
    Can only be performed by the claim owner, a maintainer, or an admin.
    """
    result = unclaim_issue(
        db=db,
        issue_id=issue_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )
    return ClaimReleaseResponse(**result)
