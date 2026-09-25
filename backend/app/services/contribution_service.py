from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    Contribution, ContributionStatus, ContributionValidation,
    User, Issue, PullRequest, ActivityFeed
)
from app.schemas.contribution import (
    ContributionResponse,
    UserContributionTimelineResponse,
    ContributionPRBrief
)
from app.schemas.claim import ClaimUserBrief
from app.schemas.pull_request import LinkedIssueBrief

# Formal state machine transition graph:
# claimed → in_progress → pr_submitted → under_review → changes_requested → accepted → merged
ALLOWED_TRANSITIONS: Dict[ContributionStatus, Set[ContributionStatus]] = {
    ContributionStatus.CLAIMED: {
        ContributionStatus.IN_PROGRESS,
        ContributionStatus.PR_SUBMITTED,
    },
    ContributionStatus.IN_PROGRESS: {
        ContributionStatus.PR_SUBMITTED,
    },
    ContributionStatus.PR_SUBMITTED: {
        ContributionStatus.UNDER_REVIEW,
        ContributionStatus.ACCEPTED,
        ContributionStatus.MERGED,
    },
    ContributionStatus.UNDER_REVIEW: {
        ContributionStatus.CHANGES_REQUESTED,
        ContributionStatus.ACCEPTED,
        ContributionStatus.MERGED,
    },
    ContributionStatus.CHANGES_REQUESTED: {
        ContributionStatus.IN_PROGRESS,
        ContributionStatus.PR_SUBMITTED,
        ContributionStatus.UNDER_REVIEW,
    },
    ContributionStatus.ACCEPTED: {
        ContributionStatus.MERGED,
    },
    ContributionStatus.MERGED: set(),  # Terminal state
}


def validate_state_transition(current: ContributionStatus, target: ContributionStatus) -> bool:
    """Validate whether state transition conforms to contribution lifecycle."""
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def _build_contribution_response(contrib: Contribution) -> ContributionResponse:
    user_brief = None
    if contrib.user:
        user_brief = ClaimUserBrief(
            id=contrib.user.id,
            name=contrib.user.name,
            psit_roll_no=contrib.user.psit_roll_no,
            github_username=contrib.user.github_username
        )

    issue_brief = None
    if contrib.issue:
        issue_brief = LinkedIssueBrief(
            id=contrib.issue.id,
            github_issue_id=contrib.issue.github_issue_id,
            title=contrib.issue.title,
            difficulty=contrib.issue.difficulty.value if hasattr(contrib.issue.difficulty, "value") else str(contrib.issue.difficulty),
            status=contrib.issue.status.value if hasattr(contrib.issue.status, "value") else str(contrib.issue.status)
        )

    pr_brief = None
    if contrib.pull_request:
        pr_brief = ContributionPRBrief(
            id=contrib.pull_request.id,
            github_pr_id=contrib.pull_request.github_pr_id,
            title=contrib.pull_request.title,
            status=contrib.pull_request.status.value if hasattr(contrib.pull_request.status, "value") else str(contrib.pull_request.status)
        )

    return ContributionResponse(
        id=contrib.id,
        user_id=contrib.user_id,
        issue_id=contrib.issue_id,
        pr_id=contrib.pr_id,
        status=contrib.status,
        validation_status=contrib.validation_status,
        timeline_json=list(contrib.timeline_json or []),
        created_at=contrib.created_at,
        updated_at=contrib.updated_at,
        user=user_brief,
        issue=issue_brief,
        pull_request=pr_brief
    )


def transition_contribution_status(
    db: Session,
    contribution_id: int,
    new_status: ContributionStatus,
    detail: Optional[str] = None
) -> ContributionResponse:
    """Transition contribution status using state machine rules and append to timeline."""
    contrib = db.query(Contribution).filter(Contribution.id == contribution_id).first()
    if not contrib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contribution with ID {contribution_id} not found."
        )

    if not validate_state_transition(contrib.status, new_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: Cannot transition from '{contrib.status.value}' to '{new_status.value}'."
        )

    now = datetime.now(timezone.utc)
    contrib.status = new_status
    if new_status == ContributionStatus.MERGED:
        contrib.validation_status = ContributionValidation.VALID

    # Append to timeline
    timeline = list(contrib.timeline_json or [])
    timeline.append({
        "status": new_status.value,
        "timestamp": now.isoformat(),
        "detail": detail or f"Transitioned to {new_status.value}"
    })
    contrib.timeline_json = timeline

    db.commit()
    db.refresh(contrib)
    return _build_contribution_response(contrib)


def update_validation_status(
    db: Session,
    contribution_id: int,
    new_validation: ContributionValidation,
    note: Optional[str] = None,
    actor_id: Optional[int] = None
) -> ContributionResponse:
    """
    Moderation / maintainer action to update contribution validation status
    (valid, pending, rejected, duplicate, invalid).
    """
    contrib = db.query(Contribution).filter(Contribution.id == contribution_id).first()
    if not contrib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contribution with ID {contribution_id} not found."
        )

    now = datetime.now(timezone.utc)
    old_validation = contrib.validation_status
    contrib.validation_status = new_validation

    # Append audit trail to timeline
    timeline = list(contrib.timeline_json or [])
    timeline.append({
        "status": contrib.status.value,
        "validation_change": f"{old_validation.value} -> {new_validation.value}",
        "timestamp": now.isoformat(),
        "detail": note or f"Validation status set to '{new_validation.value}' by moderator."
    })
    contrib.timeline_json = timeline

    # Log in activity feed
    activity = ActivityFeed(
        type="contribution_moderated",
        actor_id=actor_id,
        target_type="contribution",
        target_id=contrib.id,
        created_at=now
    )
    db.add(activity)

    db.commit()
    db.refresh(contrib)
    return _build_contribution_response(contrib)


def get_user_contribution_timeline(db: Session, user_id: int) -> UserContributionTimelineResponse:
    """Retrieve all contributions and comprehensive chronological timeline for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    contributions = (
        db.query(Contribution)
        .filter(Contribution.user_id == user_id)
        .order_by(Contribution.created_at.desc())
        .all()
    )

    items = [_build_contribution_response(c) for c in contributions]
    total = len(items)
    valid_count = sum(1 for c in items if c.validation_status == ContributionValidation.VALID)
    merged_count = sum(1 for c in items if c.status == ContributionStatus.MERGED)
    in_prog_count = sum(1 for c in items if c.status not in [ContributionStatus.MERGED])

    user_brief = ClaimUserBrief(
        id=user.id,
        name=user.name,
        psit_roll_no=user.psit_roll_no,
        github_username=user.github_username
    )

    return UserContributionTimelineResponse(
        user_id=user.id,
        user=user_brief,
        total_contributions=total,
        valid_contributions_count=valid_count,
        merged_count=merged_count,
        in_progress_count=in_prog_count,
        items=items
    )


def list_contributions(
    db: Session,
    status_filter: Optional[ContributionStatus] = None,
    validation_filter: Optional[ContributionValidation] = None,
    skip: int = 0,
    limit: int = 30
) -> Tuple[List[ContributionResponse], int]:
    """List contributions with moderation filters."""
    query = db.query(Contribution)

    if status_filter is not None:
        query = query.filter(Contribution.status == status_filter)
    if validation_filter is not None:
        query = query.filter(Contribution.validation_status == validation_filter)

    total = query.count()
    contribs = query.order_by(Contribution.updated_at.desc()).offset(skip).limit(limit).all()

    return [_build_contribution_response(c) for c in contribs], total
