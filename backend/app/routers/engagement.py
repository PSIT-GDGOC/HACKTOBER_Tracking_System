"""FastAPI Router for Module 8: Engagement Layer (Leaderboard, Notifications, Activity Feed)"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.dependencies import get_current_user
from app.schemas.engagement import (
    LeaderboardResponse,
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationReadAllResponse,
    ActivityFeedResponse,
)
from app.services import engagement_service

router = APIRouter(tags=["Engagement Layer"])


# ============================================================================
# Leaderboard
# ============================================================================

@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get participant leaderboard ranking",
    description="Calculates contributor leaderboard using indexed PostgreSQL queries with weighted points and merged PR counts. No external data store required."
)
def get_leaderboard(
    repo_id: Optional[int] = Query(None, description="Filter rankings by specific repository ID"),
    platform: Optional[str] = Query(None, description="Filter by repository platform ('web' or 'android')"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    return engagement_service.get_leaderboard(
        db=db,
        repo_id=repo_id,
        platform=platform,
        page=page,
        per_page=per_page,
    )


# ============================================================================
# Notifications
# ============================================================================

@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="Get notifications for current user",
    description="Returns paginated notifications for the authenticated user, prioritized with unread messages first."
)
def get_user_notifications(
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    limit: int = Query(20, ge=1, le=100, description="Max notifications to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return engagement_service.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=offset,
        limit=limit,
    )


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationMarkReadResponse,
    summary="Mark single notification as read",
    description="Marks a specific notification as read. Verifies that the notification belongs to the current user."
)
def mark_notification_read(
    notification_id: int = Path(..., description="The notification ID to mark read"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return engagement_service.mark_notification_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post(
    "/notifications/read-all",
    response_model=NotificationReadAllResponse,
    summary="Mark all user notifications as read",
    description="Marks all unread notifications for the authenticated user as read in a single batch operation."
)
@router.patch(
    "/notifications/read-all",
    response_model=NotificationReadAllResponse,
    include_in_schema=False,
)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return engagement_service.mark_all_notifications_read(
        db=db,
        user_id=current_user.id,
    )


# ============================================================================
# Activity Feed
# ============================================================================

@router.get(
    "/activity",
    response_model=ActivityFeedResponse,
    summary="Get global activity event stream",
    description="Returns a chronologically ordered real-time activity stream of claims, PR submissions, reviews, and merges across the platform."
)
def get_activity_feed(
    type: Optional[str] = Query(None, description="Filter by event type (e.g. 'claim_created', 'pr_opened', 'pr_merged', 'review_submitted')"),
    actor_id: Optional[int] = Query(None, description="Filter by user ID of the actor"),
    target_type: Optional[str] = Query(None, description="Filter by target type ('issue', 'pull_request', 'repository')"),
    limit: int = Query(20, ge=1, le=100, description="Max activities to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    return engagement_service.get_activity_feed(
        db=db,
        type_filter=type,
        actor_id=actor_id,
        target_type=target_type,
        skip=offset,
        limit=limit,
    )
