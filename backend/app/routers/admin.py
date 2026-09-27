"""Admin Router — privileged platform management endpoints.

All endpoints in this router require ADMIN role.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_roles
from app.models import UserRole
from app.services.org_sync_service import sync_org_repos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/sync-org-repos",
    summary="Manually trigger PSIT-GDGOC org repository sync",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def manual_sync_org_repos(db: Session = Depends(get_db)):
    """
    Force an immediate re-sync of all public repositories from the
    PSIT-GDGOC GitHub organization into the Repository Hub.

    - Fetches all public, non-archived, non-forked repos from the org
    - Skips .github and HACKTOBER_Tracking_System
    - Creates new entries for repos not yet in the DB
    - Updates name/platform for repos already in the DB

    Admin only.
    """
    logger.info("Admin manual org sync triggered")
    result = await sync_org_repos(db)
    return {
        "status": "success",
        "message": f"Synced {result['synced']} repos from github.com/orgs/PSIT-GDGOC",
        "detail": result,
    }
