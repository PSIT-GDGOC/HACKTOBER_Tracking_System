"""GitHub Organization Repository Sync Service.

Automatically syncs all public repositories from the PSIT-GDGOC GitHub
organization into the platform's `repositories` table.

Flow:
    GitHub API GET /orgs/PSIT-GDGOC/repos
        → filter out skip-listed repos (.github, HACKTOBER_Tracking_System)
        → auto-detect platform (web/android) from repo name
        → upsert each repo into DB (update if exists, insert if new)

Called:
    - On app startup (one-time full sync)
    - By the background periodic sync (every 5 minutes)
    - Via POST /admin/sync-org-repos (manual admin trigger)
    - When a "repository created" org webhook fires
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repository import Repository, PlatformType

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

GITHUB_ORG = "PSIT-GDGOC"

# Repos that belong to the org but should NOT appear in the hub
SKIP_REPOS = {
    "HACKTOBER_Tracking_System",  # this app itself
    ".github",                     # org profile repo
}

GITHUB_API_BASE = "https://api.github.com"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _get_org() -> str:
    """Return the configured GitHub org name (from GITHUB_ORG env var)."""
    return settings.GITHUB_ORG or "PSIT-GDGOC"


def _build_headers() -> Dict[str, str]:
    """Build GitHub API request headers. Uses GITHUB_ACCESS_TOKEN if set."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "GDGOC-Hacktoberfest-OrgSync/1.0",
    }
    token = settings.GITHUB_ACCESS_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _detect_platform(repo_name: str, repo_data: Dict[str, Any]) -> PlatformType:
    """
    Auto-detect platform type from repo name and GitHub metadata.

    Rules (checked in order):
      1. Name contains 'web', 'frontend', 'site', 'webapp' → WEB
      2. Name contains 'app', 'android', 'mobile', 'flutter', 'kotlin' → ANDROID
      3. Language is Kotlin/Java/Dart/Swift → ANDROID
      4. Default → WEB
    """
    name_lower = repo_name.lower()
    language = (repo_data.get("language") or "").lower()

    web_keywords = ["web", "frontend", "site", "webapp", "react", "vue", "angular", "svelte"]
    android_keywords = ["app", "android", "mobile", "flutter", "kotlin", "native"]
    android_langs = ["kotlin", "java", "dart", "swift"]

    if any(kw in name_lower for kw in web_keywords):
        return PlatformType.WEB
    if any(kw in name_lower for kw in android_keywords):
        return PlatformType.ANDROID
    if language in android_langs:
        return PlatformType.ANDROID
    return PlatformType.WEB


def _upsert_repo(db: Session, repo_data: Dict[str, Any]) -> tuple:
    """
    Insert or update a repository row from GitHub API data.

    Returns:
        (repo: Repository, was_created: bool)
    """
    name = repo_data["name"]
    html_url = repo_data["html_url"]
    platform = _detect_platform(name, repo_data)

    # Check for existing row by github_repo_url (URL is the stable unique key)
    existing = db.query(Repository).filter(
        Repository.github_repo_url == html_url
    ).first()

    if existing:
        # Update mutable fields in case the repo was renamed
        existing.name = name
        existing.platform = platform
        db.commit()
        db.refresh(existing)
        return existing, False
    else:
        new_repo = Repository(
            name=name,
            github_repo_url=html_url,
            platform=platform,
            created_at=datetime.utcnow(),
        )
        db.add(new_repo)
        db.commit()
        db.refresh(new_repo)
        return new_repo, True


async def fetch_org_repos_from_github() -> list:
    """
    Fetch all non-archived, non-forked public repos from the PSIT-GDGOC org.
    Handles pagination automatically (100 per page).

    Returns:
        List of raw repo dicts from GitHub API.
    """
    all_repos = []
    page = 1
    org = _get_org()

    async with httpx.AsyncClient(headers=_build_headers(), timeout=_TIMEOUT) as client:
        while True:
            url = f"{GITHUB_API_BASE}/orgs/{org}/repos"
            params = {
                "type": "public",
                "sort": "pushed",
                "per_page": 100,
                "page": page,
            }
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                page_repos = response.json()
                if not page_repos:
                    break
                all_repos.extend(page_repos)
                if len(page_repos) < 100:
                    break  # last page
                page += 1
            except httpx.HTTPStatusError as e:
                logger.error("GitHub org repos API error (HTTP %s): %s", e.response.status_code, e)
                break
            except httpx.RequestError as e:
                logger.error("GitHub org repos request failed: %s", e)
                break

    return all_repos


async def sync_org_repos(db: Session) -> Dict[str, Any]:
    """
    Main sync function: fetches all org repos from GitHub and upserts them into DB.

    Skips repos in SKIP_REPOS set.
    Returns a summary dict with counts.
    """
    org = _get_org()
    logger.info("OrgSync: Starting sync for GitHub org '%s'", org)

    raw_repos = await fetch_org_repos_from_github()

    if not raw_repos:
        logger.warning("OrgSync: No repos returned from GitHub API (check GITHUB_ACCESS_TOKEN?)")
        return {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "org": org,
        }

    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for repo_data in raw_repos:
        name = repo_data.get("name", "")

        # Skip archived, forked, or explicitly excluded repos
        if name in SKIP_REPOS:
            logger.debug("OrgSync: Skipping '%s' (in SKIP_REPOS)", name)
            skipped += 1
            continue
        if repo_data.get("archived"):
            logger.debug("OrgSync: Skipping '%s' (archived)", name)
            skipped += 1
            continue
        if repo_data.get("fork"):
            logger.debug("OrgSync: Skipping '%s' (fork)", name)
            skipped += 1
            continue

        try:
            _, was_created = _upsert_repo(db, repo_data)
            if was_created:
                created += 1
                logger.info("OrgSync: ✅ Created repo '%s' (%s)", name, repo_data["html_url"])
            else:
                updated += 1
                logger.info("OrgSync: 🔄 Updated repo '%s'", name)
        except Exception as e:
            errors += 1
            logger.error("OrgSync: Error upserting repo '%s': %s", name, e)
            db.rollback()

    total_synced = created + updated
    logger.info(
        "OrgSync: Done — %d synced (%d created, %d updated), %d skipped, %d errors",
        total_synced, created, updated, skipped, errors
    )

    return {
        "synced": total_synced,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "org": org,
    }


def sync_single_repo_from_webhook(db: Session, repo_data: Dict[str, Any]) -> Optional[Repository]:
    """
    Instantly add/update a single repository that just appeared via org webhook.
    Called when X-GitHub-Event: repository + action: created fires.

    Returns the upserted Repository object, or None if the repo is in SKIP_REPOS.
    """
    name = repo_data.get("name", "")

    if name in SKIP_REPOS:
        logger.info("OrgSync webhook: Skipping '%s' (in SKIP_REPOS)", name)
        return None

    if repo_data.get("archived") or repo_data.get("fork"):
        logger.info("OrgSync webhook: Skipping '%s' (archived or fork)", name)
        return None

    try:
        repo, was_created = _upsert_repo(db, repo_data)
        action = "Created" if was_created else "Updated"
        logger.info("OrgSync webhook: %s repo '%s' via org webhook", action, name)
        return repo
    except Exception as e:
        logger.error("OrgSync webhook: Error upserting repo '%s': %s", name, e)
        db.rollback()
        return None
