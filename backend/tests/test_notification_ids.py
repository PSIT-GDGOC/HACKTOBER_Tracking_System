"""Targeted Verification: Structured Notification Identifiers.

Covers:
- NotificationResponse extracts repo_id, issue_id, pr_id from payload when
  the notification object itself does not carry top-level columns for them.
- Both dict-based and ORM-based (from_attributes) construction paths work.
"""
from datetime import datetime, timezone
from app.schemas.engagement import NotificationResponse


def test_notification_extracts_ids_from_dict_payload():
    """When constructed from a dict, structured IDs are extracted from payload."""
    data = {
        "id": 1,
        "user_id": 10,
        "type": "pr_merged",
        "payload": {
            "title": "PR Merged!",
            "repo_id": 5,
            "issue_id": 42,
            "pr_id": 100,
        },
        "read": False,
        "created_at": datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
    }
    notif = NotificationResponse.model_validate(data)

    assert notif.repo_id == 5
    assert notif.issue_id == 42
    assert notif.pr_id == 100


def test_notification_ids_none_when_missing_from_payload():
    """When payload has no IDs, the fields default to None."""
    data = {
        "id": 2,
        "user_id": 10,
        "type": "generic",
        "payload": {"title": "Hello"},
        "read": True,
        "created_at": datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc),
    }
    notif = NotificationResponse.model_validate(data)

    assert notif.repo_id is None
    assert notif.issue_id is None
    assert notif.pr_id is None


def test_notification_partial_ids_in_payload():
    """When payload only has some IDs, only those are extracted."""
    data = {
        "id": 3,
        "user_id": 10,
        "type": "claim_created",
        "payload": {
            "title": "Issue Claimed",
            "repo_id": 7,
            "issue_id": 55,
            # no pr_id
        },
        "read": False,
        "created_at": datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc),
    }
    notif = NotificationResponse.model_validate(data)

    assert notif.repo_id == 7
    assert notif.issue_id == 55
    assert notif.pr_id is None


def test_notification_explicit_ids_override_payload():
    """When top-level IDs are explicitly set, they take precedence over payload."""
    data = {
        "id": 4,
        "user_id": 10,
        "type": "pr_review",
        "payload": {
            "title": "Review Requested",
            "repo_id": 99,
            "issue_id": 88,
            "pr_id": 77,
        },
        "read": False,
        "created_at": datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc),
        "repo_id": 1,
        "issue_id": 2,
        "pr_id": 3,
    }
    notif = NotificationResponse.model_validate(data)

    # Explicit top-level values should win
    assert notif.repo_id == 1
    assert notif.issue_id == 2
    assert notif.pr_id == 3
