from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.dashboard import (
    StudentDashboardResponse,
    MaintainerDashboardResponse,
    RepositoryDashboardResponse,
    AdminDashboardResponse
)
from app.services.dashboard_service import (
    get_student_dashboard,
    get_maintainer_dashboard,
    get_repository_dashboard,
    get_admin_dashboard
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/student", response_model=StudentDashboardResponse, summary="Student dashboard overview")
def student_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Personalized student dashboard: active claimed issues, PR progress, and valid contribution count.
    """
    return get_student_dashboard(db=db, student=current_user)


@router.get("/maintainer", response_model=MaintainerDashboardResponse, summary="Maintainer review queue dashboard")
def maintainer_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Maintainer dashboard: review queue of open PRs, pending reviews, and recent review activity.
    """
    return get_maintainer_dashboard(db=db, maintainer=current_user)


@router.get("/repository/{repository_id}", response_model=RepositoryDashboardResponse, summary="Repository statistics dashboard")
def repository_dashboard(
    repository_id: int,
    db: Session = Depends(get_db),
):
    """
    Repository-level dashboard: issue breakdown, PR counts, commit velocity, and contributor count.
    """
    return get_repository_dashboard(db=db, repo_id=repository_id)


@router.get("/admin", response_model=AdminDashboardResponse, summary="Event-wide administration overview")
def admin_dashboard(
    db: Session = Depends(get_db),
):
    """
    Executive event dashboard: student participant metrics, ERP verification rate, cross-repo summary, and moderation workload.
    """
    return get_admin_dashboard(db=db)
