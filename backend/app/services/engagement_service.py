"""Business logic for Module 8: Engagement Layer (Leaderboard, Notifications, Activity Feed)"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import func, case, distinct, or_
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.repository import Repository, PlatformType
from app.models.issue import Issue, IssueDifficulty
from app.models.claim import Claim, ClaimStatus
from app.models.pull_request import PullRequest, PRStatus
from app.models.contribution import Contribution, ContributionStatus, ContributionValidation
from app.models.notification import Notification
from app.models.activity_feed import ActivityFeed
from app.schemas.engagement import (
    LeaderboardEntry,
    LeaderboardResponse,
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationReadAllResponse,
    ActivityActorBrief,
    ActivityTargetBrief,
    ActivityItemResponse,
    ActivityFeedResponse,
)


# ============================================================================
# Leaderboard Service
# ============================================================================

def get_leaderboard(
    db: Session,
    repo_id: Optional[int] = None,
    platform: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> LeaderboardResponse:
    """
    Computes participant rankings using plain PostgreSQL aggregation with zero external datastore.
    Ranks students based on:
      1. Total points accrued from accepted / merged contributions (weighted by issue difficulty)
      2. Count of merged pull requests
      3. Total valid contributions
    Supports optional repository and platform filters.
    """
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20
    offset = (page - 1) * per_page

    # Point weight expression based on issue difficulty
    points_expr = case(
        (Issue.difficulty == IssueDifficulty.HARD, 80),
        (Issue.difficulty == IssueDifficulty.MEDIUM, 40),
        (Issue.difficulty == IssueDifficulty.EASY, 20),
        else_=20
    )

    # 1. Points and valid contributions subquery
    points_query = (
        db.query(
            Contribution.user_id.label("user_id"),
            func.coalesce(func.sum(points_expr), 0).label("total_points"),
            func.count(distinct(Contribution.id)).label("valid_contributions")
        )
        .join(Issue, Contribution.issue_id == Issue.id)
        .filter(
            or_(
                Contribution.validation_status == ContributionValidation.VALID,
                Contribution.status.in_([ContributionStatus.MERGED, ContributionStatus.ACCEPTED])
            )
        )
    )
    if repo_id is not None:
        points_query = points_query.filter(Issue.repo_id == repo_id)
    if platform:
        points_query = points_query.join(Repository, Repository.id == Issue.repo_id).filter(
            func.lower(Repository.platform) == platform.lower()
        )
    user_points_subq = points_query.group_by(Contribution.user_id).subquery()

    # 2. Merged PRs subquery
    prs_query = (
        db.query(
            PullRequest.user_id.label("user_id"),
            func.count(distinct(PullRequest.id)).label("merged_prs")
        )
        .filter(PullRequest.status == PRStatus.MERGED)
    )
    if repo_id is not None:
        prs_query = prs_query.filter(PullRequest.repo_id == repo_id)
    if platform:
        prs_query = prs_query.join(Repository, Repository.id == PullRequest.repo_id).filter(
            func.lower(Repository.platform) == platform.lower()
        )
    user_prs_subq = prs_query.group_by(PullRequest.user_id).subquery()

    # 3. Active claims subquery
    claims_query = (
        db.query(
            Claim.user_id.label("user_id"),
            func.count(distinct(Claim.id)).label("claimed_issues")
        )
        .filter(Claim.status == ClaimStatus.ACTIVE)
    )
    if repo_id is not None:
        claims_query = claims_query.join(Issue, Issue.id == Claim.issue_id).filter(Issue.repo_id == repo_id)
    if platform:
        claims_query = claims_query.join(Issue, Issue.id == Claim.issue_id).join(Repository, Repository.id == Issue.repo_id).filter(
            func.lower(Repository.platform) == platform.lower()
        )
    user_claims_subq = claims_query.group_by(Claim.user_id).subquery()

    # 4. Main student query
    query = (
        db.query(
            User.id.label("user_id"),
            User.name.label("name"),
            User.github_username.label("github_username"),
            User.role.label("role"),
            func.coalesce(user_points_subq.c.total_points, 0).label("total_points"),
            func.coalesce(user_prs_subq.c.merged_prs, 0).label("merged_prs"),
            func.coalesce(user_points_subq.c.valid_contributions, 0).label("valid_contributions"),
            func.coalesce(user_claims_subq.c.claimed_issues, 0).label("claimed_issues"),
        )
        .outerjoin(user_points_subq, user_points_subq.c.user_id == User.id)
        .outerjoin(user_prs_subq, user_prs_subq.c.user_id == User.id)
        .outerjoin(user_claims_subq, user_claims_subq.c.user_id == User.id)
        .filter(User.role == UserRole.STUDENT)
    )

    total_students = query.count()

    ordered_query = query.order_by(
        func.coalesce(user_points_subq.c.total_points, 0).desc(),
        func.coalesce(user_prs_subq.c.merged_prs, 0).desc(),
        func.coalesce(user_points_subq.c.valid_contributions, 0).desc(),
        User.id.asc()
    )

    rows = ordered_query.offset(offset).limit(per_page).all()

    entries: List[LeaderboardEntry] = []
    for idx, row in enumerate(rows):
        rank = offset + idx + 1
        avatar = (
            f"https://github.com/{row.github_username}.png"
            if row.github_username
            else None
        )
        role_str = row.role.value if hasattr(row.role, "value") else str(row.role)
        entries.append(
            LeaderboardEntry(
                rank=rank,
                user_id=row.user_id,
                name=row.name,
                github_username=row.github_username,
                avatar_url=avatar,
                role=role_str,
                total_points=int(row.total_points),
                merged_prs=int(row.merged_prs),
                valid_contributions=int(row.valid_contributions),
                claimed_issues=int(row.claimed_issues),
            )
        )

    return LeaderboardResponse(
        total=total_students,
        page=page,
        per_page=per_page,
        entries=entries,
    )


# ============================================================================
# Notification Service
# ============================================================================

def create_notification(
    db: Session,
    user_id: int,
    type: str,
    payload: Dict[str, Any],
) -> Notification:
    """Create a persistent notification record for a specific user."""
    notif = Notification(
        user_id=user_id,
        type=type,
        payload=payload,
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 20,
) -> NotificationListResponse:
    """
    Retrieve paginated notifications for the logged-in user.
    Always orders unread notifications first, then sorted newest to oldest.
    """
    query = db.query(Notification).filter(Notification.user_id == user_id)

    total = query.count()
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.read == False)
        .scalar()
        or 0
    )

    if unread_only:
        query = query.filter(Notification.read == False)

    # Order: unread first, then by created_at DESC
    items = (
        query.order_by(Notification.read.asc(), Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        items=items,
    )


def mark_notification_read(
    db: Session,
    notification_id: int,
    user_id: int,
) -> NotificationMarkReadResponse:
    """Mark a single notification as read, enforcing user ownership."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with ID {notification_id} not found."
        )

    if notif.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own notifications."
        )

    notif.read = True
    db.commit()
    return NotificationMarkReadResponse(
        id=notif.id,
        read=True,
        message="Notification marked as read."
    )


def mark_all_notifications_read(
    db: Session,
    user_id: int,
) -> NotificationReadAllResponse:
    """Mark all unread notifications for a user as read in a single query."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read == False)
        .update({"read": True}, synchronize_session=False)
    )
    db.commit()
    return NotificationReadAllResponse(
        updated_count=count,
        message=f"Marked {count} notification(s) as read."
    )


# ============================================================================
# Activity Feed Service
# ============================================================================

def record_activity(
    db: Session,
    type: str,
    actor_id: Optional[int],
    target_type: str,
    target_id: int,
) -> ActivityFeed:
    """Log an event into the global activity stream."""
    activity = ActivityFeed(
        type=type,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def get_activity_feed(
    db: Session,
    type_filter: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> ActivityFeedResponse:
    """
    Retrieve global activity feed with enriched actor and target descriptions.
    Enriched batch lookups avoid N+1 queries.
    """
    query = db.query(ActivityFeed)

    if type_filter:
        query = query.filter(ActivityFeed.type == type_filter)
    if actor_id is not None:
        query = query.filter(ActivityFeed.actor_id == actor_id)
    if target_type:
        query = query.filter(ActivityFeed.target_type == target_type)

    total = query.count()
    activities = (
        query.order_by(ActivityFeed.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    if not activities:
        return ActivityFeedResponse(total=total, items=[])

    # 1. Collect all target IDs for batch enrichment
    issue_ids = {a.target_id for a in activities if a.target_type == "issue"}
    pr_ids = {a.target_id for a in activities if a.target_type in ["pull_request", "pr"]}
    repo_ids = {a.target_id for a in activities if a.target_type == "repository"}

    issues_map = {}
    if issue_ids:
        issues = db.query(Issue).filter(Issue.id.in_(issue_ids)).all()
        issues_map = {i.id: i for i in issues}

    prs_map = {}
    if pr_ids:
        prs = db.query(PullRequest).filter(PullRequest.id.in_(pr_ids)).all()
        prs_map = {p.id: p for p in prs}

    repos_map = {}
    if repo_ids:
        repos = db.query(Repository).filter(Repository.id.in_(repo_ids)).all()
        repos_map = {r.id: r for r in repos}

    # 2. Build enriched response items
    items: List[ActivityItemResponse] = []
    for a in activities:
        actor_brief = None
        actor_name = "A contributor"
        if a.actor:
            role_str = a.actor.role.value if hasattr(a.actor.role, "value") else str(a.actor.role)
            actor_name = f"@{a.actor.github_username}" if a.actor.github_username else a.actor.name
            actor_avatar = (
                f"https://github.com/{a.actor.github_username}.png"
                if a.actor.github_username
                else None
            )
            actor_brief = ActivityActorBrief(
                id=a.actor.id,
                name=a.actor.name,
                github_username=a.actor.github_username,
                avatar_url=actor_avatar,
                role=role_str,
            )

        # Target metadata & description generator
        target_brief = None
        description = f"{actor_name} performed action '{a.type}' on {a.target_type} #{a.target_id}"

        if a.target_type == "issue" and a.target_id in issues_map:
            iss = issues_map[a.target_id]
            target_brief = ActivityTargetBrief(
                type="issue",
                id=iss.id,
                title=iss.title,
                url=f"/issues/{iss.id}"
            )
            if a.type == "claim_created":
                description = f"{actor_name} claimed issue #{iss.github_issue_id}: '{iss.title}'"
            elif a.type == "claim_released":
                description = f"{actor_name} released claim on issue #{iss.github_issue_id}: '{iss.title}'"
            elif a.type == "issue_opened":
                description = f"New issue #{iss.github_issue_id} opened: '{iss.title}'"

        elif a.target_type in ["pull_request", "pr"] and a.target_id in prs_map:
            pr = prs_map[a.target_id]
            target_brief = ActivityTargetBrief(
                type="pull_request",
                id=pr.id,
                title=pr.title,
                url=f"/pull-requests/{pr.id}"
            )
            if a.type == "pr_opened":
                description = f"{actor_name} submitted PR #{pr.id}: '{pr.title}'"
            elif a.type == "pr_merged":
                description = f"PR #{pr.id} '{pr.title}' was merged into main!"
            elif a.type == "review_submitted":
                description = f"{actor_name} submitted a review on PR #{pr.id}: '{pr.title}'"

        elif a.target_type == "repository" and a.target_id in repos_map:
            repo = repos_map[a.target_id]
            target_brief = ActivityTargetBrief(
                type="repository",
                id=repo.id,
                title=repo.name,
                url=repo.github_repo_url
            )
            description = f"Activity in repository '{repo.name}'"
        else:
            target_brief = ActivityTargetBrief(
                type=a.target_type,
                id=a.target_id
            )

        items.append(
            ActivityItemResponse(
                id=a.id,
                type=a.type,
                description=description,
                created_at=a.created_at,
                actor=actor_brief,
                target=target_brief,
            )
        )

    return ActivityFeedResponse(
        total=total,
        items=items,
    )
