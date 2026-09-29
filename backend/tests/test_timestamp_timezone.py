"""Test that API responses return timestamps with ISO-8601 UTC 'Z' timezone suffix."""
import pytest
from app.models import User
from app.dependencies import get_current_user
from app.main import app


def test_api_timestamps_have_utc_z_suffix(client):
    """Verify that dates returned by API endpoints end with 'Z'."""
    # 1. Test issues endpoint
    res = client.get("/issues")
    assert res.status_code == 200
    data = res.json()
    if data["items"]:
        item = data["items"][0]
        assert "created_at" in item
        assert item["created_at"].endswith("Z"), f"Expected trailing Z, got {item['created_at']}"
        assert item["updated_at"].endswith("Z"), f"Expected trailing Z, got {item['updated_at']}"

    # 2. Test user profile endpoint
    user1 = client.app.dependency_overrides.get(get_current_user)
    # Get user 1 profile
    res = client.get("/users/1")
    if res.status_code == 200:
        user_data = res.json()
        assert user_data["created_at"].endswith("Z")
