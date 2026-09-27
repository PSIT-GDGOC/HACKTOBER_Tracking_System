from typing import Any, Dict, List
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    User, UserRole,
    Repository,
    Issue, IssueStatus,
    Claim, ClaimStatus,
    PullRequest, PRStatus,
    Commit,
    Contribution, ContributionValidation,
    Review, ReviewStatus,
    ActivityFeed
)
from app.schemas.dashboard import (
    StudentDashboardResponse,
    MaintainerDashboardResponse,
    RepositoryDashboardResponse,
    AdminDashboardResponse,
    ActiveClaimSummary,
    ReviewQueueItem
)
from app.schemas.issue import RepositoryBrief
from app.services.pr_commit_service import _enrich_pr_response


def get_student_dashboard(db: Session, student: User) -> StudentDashboardResponse:
    """Aggregate dashboard metrics, active claims, and recent PRs for a student."""
    # Active claims query
    active_claims_query = (
        db.query(Claim, Issue, Repository)
        .join(Issue, Claim.issue_id == Issue.id)
        .join(Repository, Issue.repo_id == Repository.id)
        .filter(Claim.user_id == student.id, Claim.status == ClaimStatus.ACTIVE)
        .all()
    )

    active_claims_list = [
        ActiveClaimSummary(
            claim_id=claim.id,
            issue_id=issue.id,
            issue_title=issue.title,
            difficulty=issue.difficulty.value if hasattr(issue.difficulty, "value") else str(issue.difficulty),
            repo_name=repo.name,
            platform=repo.platform.value if hasattr(repo.platform, "value") else str(repo.platform),
            claimed_at=claim.claimed_at
        )
        for claim, issue, repo in active_claims_query
    ]

    prs_submitted_count = db.query(PullRequest).filter(PullRequest.user_id == student.id).count()
    prs_merged_count = (
        db.query(PullRequest)
        .filter(PullRequest.user_id == student.id, PullRequest.status == PRStatus.MERGED)
        .count()
    )
    valid_contribs_count = (
        db.query(Contribution)
        .filter(Contribution.user_id == student.id, Contribution.validation_status == ContributionValidation.VALID)
        .count()
    )

    recent_prs = (
        db.query(PullRequest)
        .filter(PullRequest.user_id == student.id)
        .order_by(PullRequest.created_at.desc())
        .limit(5)
        .all()
    )

    return StudentDashboardResponse(
        user_id=student.id,
        name=student.name,
        psit_roll_no=student.psit_roll_no,
        github_username=student.github_username,
        verified=student.verified,
        active_claims_count=len(active_claims_list),
        prs_submitted_count=prs_submitted_count,
        prs_merged_count=prs_merged_count,
        valid_contributions_count=valid_contribs_count,
        active_claims=active_claims_list,
        recent_prs=[_enrich_pr_response(pr) for pr in recent_prs]
    )


def get_maintainer_dashboard(db: Session, maintainer: User) -> MaintainerDashboardResponse:
    """Aggregate review queue and review history for maintainers."""
    open_prs = (
        db.query(PullRequest, Repository, User)
        .join(Repository, PullRequest.repo_id == Repository.id)
        .join(User, PullRequest.user_id == User.id)
        .filter(PullRequest.status == PRStatus.OPEN)
        .order_by(PullRequest.created_at.asc())
        .all()
    )

    review_queue: List[ReviewQueueItem] = []
    pending_count = 0
    approved_count = 0
    changes_req_count = 0

    for pr, repo, author in open_prs:
        # Check latest review on this PR
        latest_rev = (
            db.query(Review)
            .filter(Review.pr_id == pr.id)
            .order_by(Review.reviewed_at.desc())
            .first()
        )
        rev_status_str = latest_rev.status.value if latest_rev else "pending_review"

        if not latest_rev or latest_rev.status == ReviewStatus.COMMENTED:
            pending_count += 1
        elif latest_rev.status == ReviewStatus.APPROVED:
            approved_count += 1
        elif latest_rev.status == ReviewStatus.CHANGES_REQUESTED:
            changes_req_count += 1

        review_queue.append(ReviewQueueItem(
            pr_id=pr.id,
            github_pr_id=pr.github_pr_id,
            title=pr.title,
            repo_name=repo.name,
            contributor_name=author.name,
            contributor_roll_no=author.psit_roll_no,
            github_username=author.github_username,
            created_at=pr.created_at,
            status=pr.status.value,
            review_status=rev_status_str
        ))

    # Reviews submitted by this maintainer
    recent_reviews = (
        db.query(Review, PullRequest)
        .join(PullRequest, Review.pr_id == PullRequest.id)
        .filter(Review.reviewer_id == maintainer.id)
        .order_by(Review.reviewed_at.desc())
        .limit(10)
        .all()
    )

    reviewed_list = [
        {
            "review_id": r.id,
            "pr_id": pr.id,
            "pr_title": pr.title,
            "status": r.status.value,
            "comment": r.comment,
            "reviewed_at": r.reviewed_at.isoformat()
        }
        for r, pr in recent_reviews
    ]

    return MaintainerDashboardResponse(
        maintainer_id=maintainer.id,
        pending_reviews_count=pending_count,
        approved_prs_count=approved_count,
        changes_requested_count=changes_req_count,
        review_queue=review_queue,
        recently_reviewed=reviewed_list
    )


def get_repository_dashboard(db: Session, repo_id: int) -> RepositoryDashboardResponse:
    """Compute repository-level metrics, health stats, and activity."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found."
        )

    total_issues = db.query(Issue).filter(Issue.repo_id == repo_id).count()
    open_issues = db.query(Issue).filter(Issue.repo_id == repo_id, Issue.status == IssueStatus.OPEN).count()
    claimed_issues = db.query(Issue).filter(
        Issue.repo_id == repo_id,
        Issue.status.in_([IssueStatus.CLAIMED, IssueStatus.IN_PROGRESS])
    ).count()
    closed_issues = db.query(Issue).filter(Issue.repo_id == repo_id, Issue.status == IssueStatus.CLOSED).count()

    total_prs = db.query(PullRequest).filter(PullRequest.repo_id == repo_id).count()
    open_prs = db.query(PullRequest).filter(PullRequest.repo_id == repo_id, PullRequest.status == PRStatus.OPEN).count()
    merged_prs = db.query(PullRequest).filter(PullRequest.repo_id == repo_id, PullRequest.status == PRStatus.MERGED).count()

    total_commits = db.query(Commit).filter(Commit.repo_id == repo_id).count()

    unique_contributors_count = (
        db.query(func.count(distinct(Commit.user_id)))
        .filter(Commit.repo_id == repo_id, Commit.user_id.isnot(None))
        .scalar()
    ) or 0

    repo_brief = RepositoryBrief(
        id=repo.id,
        name=repo.name,
        platform=repo.platform.value if hasattr(repo.platform, "value") else str(repo.platform),
        github_repo_url=repo.github_repo_url
    )

    return RepositoryDashboardResponse(
        repository=repo_brief,
        total_issues=total_issues,
        open_issues=open_issues,
        claimed_issues=claimed_issues,
        closed_issues=closed_issues,
        total_prs=total_prs,
        open_prs=open_prs,
        merged_prs=merged_prs,
        total_commits=total_commits,
        unique_contributors_count=unique_contributors_count,
        recent_activity=[]
    )


def get_admin_dashboard(db: Session) -> AdminDashboardResponse:
    """Compute event-wide overview of participants, issues, PRs, and repositories."""
    total_students = db.query(User).filter(User.role == UserRole.STUDENT).count()
    verified_count = db.query(User).filter(User.verified == True).count()
    pending_manual_review_count = (
        db.query(User)
        .filter(User.verified == False, User.psit_roll_no != None)
        .count()
    )

    total_issues = db.query(Issue).count()
    open_issues = db.query(Issue).filter(Issue.status == IssueStatus.OPEN).count()
    active_claims = db.query(Claim).filter(Claim.status == ClaimStatus.ACTIVE).count()

    total_prs = db.query(PullRequest).count()
    merged_prs = db.query(PullRequest).filter(PullRequest.status == PRStatus.MERGED).count()
    total_commits = db.query(Commit).count()

    pending_validations = (
        db.query(Contribution)
        .filter(Contribution.validation_status == ContributionValidation.PENDING)
        .count()
    )

    repos = db.query(Repository).all()
    repos_overview = [
        {
            "id": r.id,
            "name": r.name,
            "platform": r.platform.value if hasattr(r.platform, "value") else str(r.platform),
            "issues_count": db.query(Issue).filter(Issue.repo_id == r.id).count(),
            "prs_count": db.query(PullRequest).filter(PullRequest.repo_id == r.id).count(),
            "commits_count": db.query(Commit).filter(Commit.repo_id == r.id).count()
        }
        for r in repos
    ]

    return AdminDashboardResponse(
        total_registered_students=total_students,
        verified_students=verified_count,
        pending_manual_review_students=pending_manual_review_count,
        total_issues=total_issues,
        open_issues=open_issues,
        active_claims=active_claims,
        total_prs_submitted=total_prs,
        total_prs_merged=merged_prs,
        total_commits=total_commits,
        pending_validations_count=pending_validations,
        repositories_overview=repos_overview
    )
