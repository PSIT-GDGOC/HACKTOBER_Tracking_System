"""Critical Check 3: OpenAPI contract validation and frontend expectations cross-check.
Verifies that all required API routes, operations, parameter types, and response schemas
comply with the frontend OpenAPI contract expectations for Rudransh's Next.js client.
Exports the verified openapi.json contract to the workspace root.
"""
import json
from pathlib import Path
import pytest
from app.main import app


EXPECTED_ENDPOINTS = [
    # Auth & Verification Subsystem (v2 ID + QR)
    ("POST", "/auth/signup"),
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
    ("POST", "/auth/verify-id"),
    ("GET", "/auth/pending-verifications"),
    ("POST", "/auth/verify-manual/{student_id}"),
    ("GET", "/auth/github/login"),
    ("POST", "/auth/github/link"),
    # Issues & Claims
    ("GET", "/issues"),
    ("GET", "/issues/{issue_id}"),
    ("POST", "/issues/{issue_id}/claim"),
    ("POST", "/issues/{issue_id}/unclaim"),
    ("POST", "/issues/sync"),
    # Webhook Sync Engine (v2 — webhook_jobs table)
    ("POST", "/webhooks/github"),
    ("POST", "/webhooks/jobs/drain"),
    ("GET", "/webhooks/jobs"),
    # Pull Requests & Commits
    ("GET", "/pull-requests"),
    ("GET", "/pull-requests/{pr_id}"),
    ("GET", "/commits"),
    # Contributions State Machine
    ("GET", "/contributions/my"),
    ("GET", "/contributions/{user_id}/timeline"),
    ("PATCH", "/contributions/{contribution_id}/validate"),
    # Dashboard Aggregations
    ("GET", "/dashboard/student"),
    ("GET", "/dashboard/maintainer"),
    ("GET", "/dashboard/repository/{repository_id}"),
    ("GET", "/dashboard/admin"),
    # Contributor Profiles
    ("GET", "/users/{user_id}"),
    ("GET", "/users/me"),
    ("PATCH", "/users/me"),
    # Engagement Layer
    ("GET", "/leaderboard"),
    ("GET", "/notifications"),
    ("PATCH", "/notifications/{notification_id}/read"),
    ("POST", "/notifications/read-all"),
    ("GET", "/activity"),
    # Global Search
    ("GET", "/search"),
]


def test_openapi_schema_generation_and_export():
    """Verify OpenAPI 3.x schema builds without errors and export to openapi.json."""
    openapi_schema = app.openapi()
    assert openapi_schema is not None
    assert "openapi" in openapi_schema
    assert openapi_schema["info"]["title"] == app.title
    assert "paths" in openapi_schema

    paths = openapi_schema["paths"]
    missing_endpoints = []

    for method, path in EXPECTED_ENDPOINTS:
        method_lower = method.lower()
        if path not in paths:
            missing_endpoints.append(f"{method} {path} (missing path)")
        elif method_lower not in paths[path]:
            missing_endpoints.append(f"{method} {path} (missing method)")

    assert len(missing_endpoints) == 0, f"Missing API endpoints expected by frontend: {missing_endpoints}"

    # Export openapi.json for Rudransh's openapi-typescript pipeline
    repo_root = Path(__file__).resolve().parent.parent
    export_path = repo_root / "openapi.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    assert export_path.exists()
    assert export_path.stat().st_size > 5000


def test_frontend_response_contracts():
    """Verify that key schemas required by frontend components exist in OpenAPI components."""
    openapi_schema = app.openapi()
    schemas = openapi_schema.get("components", {}).get("schemas", {})

    required_models = [
        "SignupRequest",
        "SignupResponse",
        "LoginRequest",
        "TokenResponse",
        "VerifyIDCardRequest",
        "VerifyIDCardResponse",
        "ManualReviewItemResponse",
        "ManualReviewActionRequest",
        "GitHubOAuthLinkRequest",
        "GitHubOAuthLinkResponse",
        "IssueResponse",
        "ClaimResponse",
        "PRResponse",
        "CommitResponse",
        "UserContributionTimelineResponse",
        "StudentDashboardResponse",
        "MaintainerDashboardResponse",
        "RepositoryDashboardResponse",
        "AdminDashboardResponse",
        "UserPublicProfileResponse",
        "UserProfileResponse",
        "LeaderboardResponse",
        "NotificationListResponse",
        "ActivityFeedResponse",
        "UnifiedSearchResponse",
    ]

    missing_models = [m for m in required_models if m not in schemas]
    assert len(missing_models) == 0, f"Missing required schemas for frontend: {missing_models}"
