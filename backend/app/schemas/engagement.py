"""Pydantic schemas for Module 8: Engagement Layer (Leaderboard, Notifications, Activity Feed)"""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, model_validator
from app.schemas.base import AppBaseModel


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

class NotificationResponse(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    payload: Dict[str, Any]
    read: bool
    created_at: datetime
    repo_id: Optional[int] = None
    issue_id: Optional[int] = None
    pr_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def extract_structured_ids(cls, data: Any) -> Any:
        if isinstance(data, dict):
            payload = data.get("payload") or {}
            data = dict(data)
            if data.get("repo_id") is None:
                data["repo_id"] = payload.get("repo_id")
            if data.get("issue_id") is None:
                data["issue_id"] = payload.get("issue_id")
            if data.get("pr_id") is None:
                data["pr_id"] = payload.get("pr_id")
            return data

        if hasattr(data, "payload") and isinstance(data.payload, dict):
            payload = data.payload
            return {
                "id": getattr(data, "id", None),
                "user_id": getattr(data, "user_id", None),
                "type": getattr(data, "type", None),
                "payload": payload,
                "read": getattr(data, "read", None),
                "created_at": getattr(data, "created_at", None),
                "repo_id": getattr(data, "repo_id", None) or payload.get("repo_id"),
                "issue_id": getattr(data, "issue_id", None) or payload.get("issue_id"),
                "pr_id": getattr(data, "pr_id", None) or payload.get("pr_id"),
            }
        return data


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


class ActivityItemResponse(AppBaseModel):
    id: int
    type: str
    description: Optional[str] = None  # Computed by service (no DB column)
    created_at: datetime
    actor: Optional[ActivityActorBrief] = None
    target: Optional[ActivityTargetBrief] = None


class ActivityFeedResponse(BaseModel):
    total: int
    items: List[ActivityItemResponse]
