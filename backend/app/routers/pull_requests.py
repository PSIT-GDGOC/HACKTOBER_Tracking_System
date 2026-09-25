from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.pull_request import PRStatus
from app.schemas.pull_request import PRResponse, PRListResponse
from app.services.pr_commit_service import get_pull_requests, get_pull_request_by_id

router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])


@router.get("", response_model=PRListResponse, summary="List pull requests with filters")
def list_prs(
    repo_id: Optional[int] = Query(None, description="Filter by repository ID"),
    user_id: Optional[int] = Query(None, description="Filter by contributor user ID"),
    github_username: Optional[str] = Query(None, description="Filter by contributor GitHub username"),
    status: Optional[PRStatus] = Query(None, description="Filter by status (open, merged, closed, draft)"),
    skip: int = Query(0, ge=0, description="Offset pagination skip"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """
    List pull requests across repositories with filtering by repo, contributor, and status.
    """
    items, total = get_pull_requests(
        db=db,
        repo_id=repo_id,
        user_id=user_id,
        github_username=github_username,
        status_filter=status,
        skip=skip,
        limit=limit,
    )
    return PRListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


@router.get("/{pr_id}", response_model=PRResponse, summary="Get single pull request details")
def get_pr(
    pr_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve full details for a pull request, including linked issue, reviews, author, and reviewer.
    """
    return get_pull_request_by_id(db=db, pr_id=pr_id)
