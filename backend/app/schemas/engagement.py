"""Pydantic schemas for Module 8: Engagement Layer (Leaderboard, Notifications, Activity Feed)"""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


# ============================================================================
# Leaderboard Schemas
# ============================================================================

class LeaderboardEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    user_id: int
    name: str
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    total_points: int
    merged_prs: int
    valid_contributions: int
    claimed_issues: int


class LeaderboardResponse(BaseModel):
    total: int
    page: int
    per_page: int
    entries: List[LeaderboardEntry]


# ============================================================================
# Notification Schemas
# ============================================================================

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    payload: Dict[str, Any]
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    items: List[NotificationResponse]


class NotificationMarkReadResponse(BaseModel):
    id: int
    read: bool
    message: str


class NotificationReadAllResponse(BaseModel):
    updated_count: int
    message: str


# ============================================================================
# Activity Feed Schemas
# ============================================================================

class ActivityActorBrief(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None


class ActivityTargetBrief(BaseModel):
    type: str
    id: int
    title: Optional[str] = None
    url: Optional[str] = None


class ActivityItemResponse(BaseModel):
    id: int
    type: str
    description: Optional[str] = None  # Computed by service (no DB column)
    created_at: datetime
    actor: Optional[ActivityActorBrief] = None
    target: Optional[ActivityTargetBrief] = None


class ActivityFeedResponse(BaseModel):
    total: int
    items: List[ActivityItemResponse]
