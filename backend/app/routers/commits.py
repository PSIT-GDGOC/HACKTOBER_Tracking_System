from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.commit import CommitListResponse
from app.services.pr_commit_service import get_commits

router = APIRouter(prefix="/commits", tags=["Commits"])


@router.get("", response_model=CommitListResponse, summary="List commits")
def list_commits(
    repo_id: Optional[int] = Query(None, description="Filter commits by repository ID"),
    user_id: Optional[int] = Query(None, description="Filter commits by contributor user ID"),
    github_username: Optional[str] = Query(None, description="Filter commits by contributor GitHub username"),
    pr_id: Optional[int] = Query(None, description="Filter commits by pull request ID"),
    issue_id: Optional[int] = Query(None, description="Filter commits by linked issue ID"),
    skip: int = Query(0, ge=0, description="Offset pagination skip"),
    limit: int = Query(30, ge=1, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """
    List commits across repositories and contributors.
    """
    items, total = get_commits(
        db=db,
        repo_id=repo_id,
        user_id=user_id,
        github_username=github_username,
        pr_id=pr_id,
        issue_id=issue_id,
        skip=skip,
        limit=limit,
    )
    return CommitListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )
