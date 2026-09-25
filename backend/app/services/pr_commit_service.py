from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import PullRequest, PRStatus, Commit, User, Repository, Issue, Review
from app.schemas.pull_request import PRResponse, ReviewDetail, LinkedIssueBrief
from app.schemas.commit import CommitResponse
from app.schemas.claim import ClaimUserBrief
from app.schemas.issue import RepositoryBrief


def _build_user_brief(user: Optional[User]) -> Optional[ClaimUserBrief]:
    if not user:
        return None
    return ClaimUserBrief(
        id=user.id,
        name=user.name,
        psit_roll_no=user.psit_roll_no,
        github_username=user.github_username
    )


def _build_repo_brief(repo: Optional[Repository]) -> Optional[RepositoryBrief]:
    if not repo:
        return None
    return RepositoryBrief(
        id=repo.id,
        name=repo.name,
        platform=repo.platform.value if hasattr(repo.platform, "value") else str(repo.platform),
        github_repo_url=repo.github_repo_url
    )


def _build_linked_issue_brief(issue: Optional[Issue]) -> Optional[LinkedIssueBrief]:
    if not issue:
        return None
    return LinkedIssueBrief(
        id=issue.id,
        github_issue_id=issue.github_issue_id,
        title=issue.title,
        difficulty=issue.difficulty.value if hasattr(issue.difficulty, "value") else str(issue.difficulty),
        status=issue.status.value if hasattr(issue.status, "value") else str(issue.status)
    )


def _enrich_pr_response(pr: PullRequest) -> PRResponse:
    reviews_list = []
    for r in pr.reviews:
        reviewer_name = r.reviewer.name if r.reviewer else None
        reviews_list.append(ReviewDetail(
            id=r.id,
            pr_id=r.pr_id,
            reviewer_id=r.reviewer_id,
            reviewer_name=reviewer_name,
            status=r.status,
            comment=r.comment,
            reviewed_at=r.reviewed_at
        ))

    return PRResponse(
        id=pr.id,
        repo_id=pr.repo_id,
        github_pr_id=pr.github_pr_id,
        issue_id=pr.issue_id,
        user_id=pr.user_id,
        title=pr.title,
        status=pr.status,
        reviewer_id=pr.reviewer_id,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
        user=_build_user_brief(pr.user),
        reviewer=_build_user_brief(pr.reviewer),
        repository=_build_repo_brief(pr.repository),
        linked_issue=_build_linked_issue_brief(pr.issue),
        reviews=reviews_list
    )


def _enrich_commit_response(c: Commit) -> CommitResponse:
    return CommitResponse(
        id=c.id,
        repo_id=c.repo_id,
        github_commit_sha=c.github_commit_sha,
        user_id=c.user_id,
        message=c.message,
        issue_id=c.issue_id,
        pr_id=c.pr_id,
        committed_at=c.committed_at,
        user=_build_user_brief(c.user),
        repository=_build_repo_brief(c.repository)
    )


def get_pull_requests(
    db: Session,
    repo_id: Optional[int] = None,
    user_id: Optional[int] = None,
    github_username: Optional[str] = None,
    status_filter: Optional[PRStatus] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[PRResponse], int]:
    """List pull requests with filters for repo, contributor, and PR status."""
    query = db.query(PullRequest)

    if repo_id is not None:
        query = query.filter(PullRequest.repo_id == repo_id)
    if user_id is not None:
        query = query.filter(PullRequest.user_id == user_id)
    if github_username:
        query = query.join(PullRequest.user).filter(User.github_username.ilike(github_username))
    if status_filter is not None:
        query = query.filter(PullRequest.status == status_filter)

    total = query.count()
    prs = query.order_by(PullRequest.created_at.desc()).offset(skip).limit(limit).all()

    return [_enrich_pr_response(pr) for pr in prs], total


def get_pull_request_by_id(db: Session, pr_id: int) -> PRResponse:
    """Retrieve full details of a single pull request by ID."""
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request with ID {pr_id} not found."
        )
    return _enrich_pr_response(pr)


def get_commits(
    db: Session,
    repo_id: Optional[int] = None,
    user_id: Optional[int] = None,
    github_username: Optional[str] = None,
    pr_id: Optional[int] = None,
    issue_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 30,
) -> Tuple[List[CommitResponse], int]:
    """List commits per repository, per contributor, or linked to PRs and issues."""
    query = db.query(Commit)

    if repo_id is not None:
        query = query.filter(Commit.repo_id == repo_id)
    if user_id is not None:
        query = query.filter(Commit.user_id == user_id)
    if github_username:
        query = query.join(Commit.user).filter(User.github_username.ilike(github_username))
    if pr_id is not None:
        query = query.filter(Commit.pr_id == pr_id)
    if issue_id is not None:
        query = query.filter(Commit.issue_id == issue_id)

    total = query.count()
    commits = query.order_by(Commit.committed_at.desc()).offset(skip).limit(limit).all()

    return [_enrich_commit_response(c) for c in commits], total
