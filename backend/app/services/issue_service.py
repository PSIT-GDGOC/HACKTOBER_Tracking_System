from datetime import datetime, timezone
import re
from typing import List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, String, cast
from fastapi import HTTPException, status

from app.config import settings
from app.models import (
    Issue, IssueDifficulty, IssueStatus,
    Claim, ClaimStatus,
    User, UserRole,
    Repository,
    Contribution, ContributionStatus, ContributionValidation,
    ActivityFeed,
    Notification
)
from app.schemas.issue import IssueResponse, RepositoryBrief
from app.schemas.claim import ClaimResponse, ClaimUserBrief


def _extract_repo_owner_name(repo_url: str) -> Tuple[str, str]:
    """Parse owner and repo name from GitHub URL."""
    cleaned = repo_url.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    raise ValueError(f"Invalid GitHub repository URL format: {repo_url}")


def _infer_issue_metadata(labels: List[str]) -> Tuple[IssueDifficulty, Optional[str], List[str]]:
    """Infer difficulty, category, and tech tags from issue labels."""
    difficulty = IssueDifficulty.EASY
    category = None
    tech_tags = []

    label_lower_map = {l.lower(): l for l in labels}

    # Infer difficulty
    if any("hard" in l for l in label_lower_map):
        difficulty = IssueDifficulty.HARD
    elif any("medium" in l for l in label_lower_map):
        difficulty = IssueDifficulty.MEDIUM
    elif any(l in ["easy", "good first issue", "beginner-friendly"] for l in label_lower_map):
        difficulty = IssueDifficulty.EASY

    # Infer category
    category_keywords = ["frontend", "backend", "android", "ui/ux", "bug", "feature", "documentation", "devops"]
    for kw in category_keywords:
        if any(kw in l for l in label_lower_map):
            category = kw
            break

    # Infer tech tags
    common_tech = ["react", "vue", "angular", "typescript", "javascript", "python", "fastapi", "django",
                   "kotlin", "jetpack compose", "java", "postgresql", "docker", "tailwind", "css", "html"]
    for tech in common_tech:
        if any(tech in l for l in label_lower_map):
            tech_tags.append(label_lower_map[next(l for l in label_lower_map if tech in l)])

    return difficulty, category, list(set(tech_tags))


def sync_issues_from_github(db: Session, repo_id: Optional[int] = None) -> dict:
    """Sync issues from GitHub REST API for one or all registered repositories."""
    repos_query = db.query(Repository)
    if repo_id:
        repos_query = repos_query.filter(Repository.id == repo_id)
    repos = repos_query.all()

    if not repos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No repositories found to sync.")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GDGOC-Hacktoberfest-Platform",
    }
    if settings.GITHUB_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_ACCESS_TOKEN}"

    synced_total = 0
    created_total = 0
    updated_total = 0

    with httpx.Client(headers=headers, timeout=15.0) as client:
        for repo in repos:
            try:
                owner, repo_name = _extract_repo_owner_name(repo.github_repo_url)
            except ValueError:
                continue

            gh_url = f"https://api.github.com/repos/{owner}/{repo_name}/issues"
            params = {"state": "all", "per_page": 100}

            try:
                response = client.get(gh_url, params=params)
                if response.status_code != 200:
                    continue
                gh_issues = response.json()
            except Exception:
                continue

            for item in gh_issues:
                # GitHub issues endpoint includes pull requests; filter them out
                if "pull_request" in item:
                    continue

                gh_issue_id = item["id"]
                title = item.get("title", "Untitled")
                body = item.get("body", "")
                label_names = [lbl["name"] for lbl in item.get("labels", []) if isinstance(lbl, dict) and "name" in lbl]
                gh_state = item.get("state", "open")

                difficulty, category, tech_tags = _infer_issue_metadata(label_names)

                existing_issue = db.query(Issue).filter(Issue.github_issue_id == gh_issue_id).first()
                if existing_issue:
                    existing_issue.title = title
                    existing_issue.description = body
                    existing_issue.labels = label_names
                    existing_issue.tech_tags = tech_tags
                    if category:
                        existing_issue.category = category
                    if gh_state == "closed":
                        existing_issue.status = IssueStatus.CLOSED
                    updated_total += 1
                else:
                    new_issue = Issue(
                        repo_id=repo.id,
                        github_issue_id=gh_issue_id,
                        title=title,
                        description=body,
                        difficulty=difficulty,
                        category=category,
                        tech_tags=tech_tags,
                        labels=label_names,
                        status=IssueStatus.CLOSED if gh_state == "closed" else IssueStatus.OPEN,
                    )
                    db.add(new_issue)
                    created_total += 1
                synced_total += 1

    db.commit()
    return {
        "message": "GitHub issues sync completed successfully.",
        "synced_count": synced_total,
        "created_count": created_total,
        "updated_count": updated_total,
    }


def _enrich_issue_response(issue: Issue, active_claim: Optional[Claim] = None) -> IssueResponse:
    """Helper to convert Issue ORM model into IssueResponse schema with relations."""
    repo_brief = None
    if issue.repository:
        repo_brief = RepositoryBrief(
            id=issue.repository.id,
            name=issue.repository.name,
            platform=issue.repository.platform.value if hasattr(issue.repository.platform, 'value') else issue.repository.platform,
            github_repo_url=issue.repository.github_repo_url
        )

    claim_resp = None
    if active_claim:
        user_brief = None
        if active_claim.user:
            user_brief = ClaimUserBrief(
                id=active_claim.user.id,
                name=active_claim.user.name,
                psit_roll_no=active_claim.user.psit_roll_no,
                github_username=active_claim.user.github_username
            )
        claim_resp = ClaimResponse(
            id=active_claim.id,
            issue_id=active_claim.issue_id,
            user_id=active_claim.user_id,
            claimed_at=active_claim.claimed_at,
            status=active_claim.status,
            user=user_brief
        )

    return IssueResponse(
        id=issue.id,
        repo_id=issue.repo_id,
        github_issue_id=issue.github_issue_id,
        title=issue.title,
        description=issue.description,
        difficulty=issue.difficulty,
        category=issue.category,
        tech_tags=issue.tech_tags or [],
        labels=issue.labels or [],
        status=issue.status,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        repository=repo_brief,
        active_claim=claim_resp
    )


def get_issues(
    db: Session,
    repo_id: Optional[int] = None,
    difficulty: Optional[IssueDifficulty] = None,
    tech_tag: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[IssueStatus] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[IssueResponse], int]:
    """Retrieve filtered and paginated list of issues."""
    query = db.query(Issue)

    if repo_id is not None:
        query = query.filter(Issue.repo_id == repo_id)
    if difficulty is not None:
        query = query.filter(Issue.difficulty == difficulty)
    if category is not None:
        query = query.filter(Issue.category.ilike(f"%{category}%"))
    if status_filter is not None:
        query = query.filter(Issue.status == status_filter)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Issue.title.ilike(search_fmt),
                Issue.description.ilike(search_fmt),
            )
        )
    if tech_tag:
        # Cast JSON column to string for cross-dialect matching (Postgres/SQLite)
        query = query.filter(cast(Issue.tech_tags, String).ilike(f"%{tech_tag}%"))

    total = query.count()
    issues = query.order_by(Issue.created_at.desc()).offset(skip).limit(limit).all()

    # Pre-fetch active claims for any claimed issues in this batch
    issue_ids = [i.id for i in issues if i.status == IssueStatus.CLAIMED]
    active_claims = {}
    if issue_ids:
        claims = (
            db.query(Claim)
            .filter(Claim.issue_id.in_(issue_ids), Claim.status == ClaimStatus.ACTIVE)
            .all()
        )
        active_claims = {c.issue_id: c for c in claims}

    result = [_enrich_issue_response(i, active_claims.get(i.id)) for i in issues]
    return result, total


def get_issue_by_id(db: Session, issue_id: int) -> IssueResponse:
    """Retrieve single issue by its database ID."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found."
        )

    active_claim = (
        db.query(Claim)
        .filter(Claim.issue_id == issue.id, Claim.status == ClaimStatus.ACTIVE)
        .first()
    )
    return _enrich_issue_response(issue, active_claim)


def claim_issue(db: Session, issue_id: int, user_id: int) -> ClaimResponse:
    """
    Atomic operation to claim an open issue by a verified student.
    Enforces row locking and catches concurrency collisions via the DB unique constraint.
    """
    # 1. Row locking for concurrency safety if supported by database (e.g. Postgres)
    query = db.query(Issue).filter(Issue.id == issue_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        issue = query.with_for_update().first()
    else:
        issue = query.first()

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found."
        )

    # 2. Status verification
    if issue.status != IssueStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Issue is not available for claiming (current status: '{issue.status.value}')."
        )

    # 3. User verification
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    if not user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a verified PSIT student (ID card / QR verified) to claim issues."
        )

    # 4. Enforce max active claims limit per student
    active_claims_count = (
        db.query(Claim)
        .filter(Claim.user_id == user_id, Claim.status == ClaimStatus.ACTIVE)
        .count()
    )
    if active_claims_count >= settings.MAX_ACTIVE_CLAIMS_PER_STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Active claim limit reached ({settings.MAX_ACTIVE_CLAIMS_PER_STUDENT} max). "
                "Please submit a PR or unclaim an existing issue before claiming a new one."
            )
        )

    # 5. Check if another active claim already exists on this issue
    existing_claim = (
        db.query(Claim)
        .filter(Claim.issue_id == issue_id, Claim.status == ClaimStatus.ACTIVE)
        .first()
    )
    if existing_claim:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This issue is already actively claimed by another contributor."
        )

    # 6. Create active claim and update issue status atomically
    now = datetime.now(timezone.utc)
    new_claim = Claim(
        issue_id=issue.id,
        user_id=user.id,
        status=ClaimStatus.ACTIVE,
        claimed_at=now,
    )
    issue.status = IssueStatus.CLAIMED
    db.add(new_claim)

    # 7. Create or update contribution lifecycle record
    contribution = Contribution(
        user_id=user.id,
        issue_id=issue.id,
        status=ContributionStatus.CLAIMED,
        validation_status=ContributionValidation.PENDING,
        timeline_json=[
            {
                "status": "claimed",
                "timestamp": now.isoformat(),
                "detail": f"Claimed issue #{issue.github_issue_id}: '{issue.title}'"
            }
        ]
    )
    db.add(contribution)

    # 8. Record in activity feed
    activity = ActivityFeed(
        type="claim_created",
        actor_id=user.id,
        target_type="issue",
        target_id=issue.id,
        created_at=now,
    )
    db.add(activity)

    # 9. Send notification to user
    notif = Notification(
        user_id=user.id,
        type="claim_created",
        payload={
            "title": "📌 Issue Claimed",
            "message": f"You claimed issue #{issue.github_issue_id}: '{issue.title}'. Submit your PR within 7 days.",
            "issue_id": issue.id,
            "repo_id": issue.repo_id,
        },
        read=False,
        created_at=now,
    )
    db.add(notif)

    try:
        db.commit()
        db.refresh(new_claim)
    except IntegrityError:
        db.rollback()
        # Raised if another worker simultaneously committed an active claim for this issue
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrency collision: This issue was just claimed by another contributor. Please select another issue."
        )

    user_brief = ClaimUserBrief(
        id=user.id,
        name=user.name,
        psit_roll_no=user.psit_roll_no,
        github_username=user.github_username
    )

    return ClaimResponse(
        id=new_claim.id,
        issue_id=new_claim.issue_id,
        user_id=new_claim.user_id,
        claimed_at=new_claim.claimed_at,
        status=new_claim.status,
        user=user_brief
    )


def unclaim_issue(db: Session, issue_id: int, user_id: int, user_role: UserRole = UserRole.STUDENT) -> dict:
    """Release an active claim and return issue to OPEN status."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found."
        )

    active_claim = (
        db.query(Claim)
        .filter(Claim.issue_id == issue.id, Claim.status == ClaimStatus.ACTIVE)
        .first()
    )
    if not active_claim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This issue does not have an active claim to release."
        )

    # Only claim owner or maintainers/admins can unclaim
    if active_claim.user_id != user_id and user_role not in [UserRole.MAINTAINER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only release claims that you created."
        )

    now = datetime.now(timezone.utc)
    active_claim.status = ClaimStatus.RELEASED
    issue.status = IssueStatus.OPEN

    # Update contribution record
    contribution = (
        db.query(Contribution)
        .filter(Contribution.issue_id == issue.id, Contribution.user_id == active_claim.user_id)
        .order_by(Contribution.created_at.desc())
        .first()
    )
    if contribution:
        timeline = list(contribution.timeline_json or [])
        timeline.append({
            "status": "released",
            "timestamp": now.isoformat(),
            "detail": f"Claim released by user {user_id}"
        })
        contribution.timeline_json = timeline

    # Record in activity feed
    activity = ActivityFeed(
        type="claim_released",
        actor_id=user_id,
        target_type="issue",
        target_id=issue.id,
        created_at=now,
    )
    db.add(activity)

    # Notify student
    db.add(Notification(
        user_id=active_claim.user_id,
        type="claim_released",
        payload={
            "title": "Claim Released",
            "message": f"Your claim on issue #{issue.github_issue_id} '{issue.title}' was released.",
            "issue_id": issue.id,
        },
        read=False,
        created_at=now,
    ))

    db.commit()

    return {
        "message": "Issue claim released successfully. Issue is now available for other students.",
        "issue_id": issue.id,
        "claim_id": active_claim.id,
        "status": ClaimStatus.RELEASED.value
    }
