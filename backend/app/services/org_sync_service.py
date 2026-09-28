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
from sqlalchemy import or_
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


def _upsert_repo(db: Session, repo_data: Dict[str, Any], old_name: Optional[str] = None) -> tuple:
    """
    Insert or update a repository row from GitHub API data.
    Supports repo renames via old_name or name matching.

    Returns:
        (repo: Repository, was_created: bool)
    """
    name = repo_data["name"]
    html_url = repo_data["html_url"]
    platform = _detect_platform(name, repo_data)

    # Check for existing row: match by URL, current name, or old name if renamed
    conditions = [Repository.github_repo_url == html_url, Repository.name == name]
    if old_name:
        conditions.append(Repository.name == old_name)

    existing = db.query(Repository).filter(or_(*conditions)).first()

    if existing:
        # Update mutable fields (handles rename, URL change, platform re-detection)
        existing.name = name
        existing.github_repo_url = html_url
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
    Also purges any repositories from DB that were deleted or archived on GitHub.

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
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "org": org,
        }

    created = 0
    updated = 0
    skipped = 0
    errors = 0
    valid_repo_urls = set()

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

        valid_repo_urls.add(repo_data.get("html_url"))

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

    # ── Auto-purge deleted or archived repos ──────────────────────────────────
    purged_count = 0
    try:
        org_pattern = f"%github.com/{org}/%"
        db_repos = db.query(Repository).filter(Repository.github_repo_url.ilike(org_pattern)).all()
        for r in db_repos:
            if r.github_repo_url not in valid_repo_urls and r.name not in SKIP_REPOS:
                logger.info("OrgSync: 🗑️ Purging deleted/archived repo '%s' (%s) from DB", r.name, r.github_repo_url)
                db.delete(r)
                purged_count += 1
        if purged_count > 0:
            db.commit()
    except Exception as e:
        logger.error("OrgSync: Error purging deleted repos: %s", e)
        db.rollback()

    total_synced = created + updated
    logger.info(
        "OrgSync: Done — %d synced (%d created, %d updated), %d deleted, %d skipped, %d errors",
        total_synced, created, updated, purged_count, skipped, errors
    )

    return {
        "synced": total_synced,
        "created": created,
        "updated": updated,
        "deleted": purged_count,
        "skipped": skipped,
        "errors": errors,
        "org": org,
    }


def delete_repo_from_webhook(db: Session, repo_data: Dict[str, Any]) -> Optional[str]:
    """
    Remove a repository from the database when deleted, archived, or privatized on GitHub.
    Returns the deleted repo's name, or None if not found.
    """
    name = repo_data.get("name", "")
    html_url = repo_data.get("html_url", "")

    existing = db.query(Repository).filter(
        or_(Repository.github_repo_url == html_url, Repository.name == name)
    ).first()

    if existing:
        deleted_name = existing.name
        db.delete(existing)
        db.commit()
        logger.info("OrgSync webhook: 🗑️ Removed repository '%s' (%s) from platform", deleted_name, html_url)
        return deleted_name

    logger.info("OrgSync webhook: Repository '%s' not found in DB to delete", name)
    return None


def sync_single_repo_from_webhook(
    db: Session,
    repo_data: Dict[str, Any],
    old_name: Optional[str] = None
) -> Optional[Repository]:
    """
    Instantly add or update a single repository via org webhook.
    Handles 'created', 'edited', 'renamed', 'unarchived', 'publicized'.

    Returns the upserted Repository object, or None if the repo is skipped/removed.
    """
    name = repo_data.get("name", "")

    if name in SKIP_REPOS:
        logger.info("OrgSync webhook: Skipping '%s' (in SKIP_REPOS)", name)
        # If previously tracked and now in SKIP_REPOS, remove it
        delete_repo_from_webhook(db, repo_data)
        return None

    if repo_data.get("archived") or repo_data.get("fork") or repo_data.get("private"):
        logger.info("OrgSync webhook: Repo '%s' is archived, fork, or private. Removing from DB if present.", name)
        delete_repo_from_webhook(db, repo_data)
        return None

    try:
        repo, was_created = _upsert_repo(db, repo_data, old_name=old_name)
        action_verb = "Created" if was_created else "Updated"
        logger.info("OrgSync webhook: %s repo '%s' (%s) via org webhook", action_verb, name, repo.platform.value)
        return repo
    except Exception as e:
        logger.error("OrgSync webhook: Error upserting repo '%s': %s", name, e)
        db.rollback()
        return None
