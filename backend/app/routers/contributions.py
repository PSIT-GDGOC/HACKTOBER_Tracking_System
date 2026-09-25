from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User, UserRole, ContributionStatus, ContributionValidation
from app.schemas.contribution import (
    ContributionResponse,
    UserContributionTimelineResponse,
    ContributionValidationUpdate
)
from app.services.contribution_service import (
    get_user_contribution_timeline,
    update_validation_status,
    transition_contribution_status,
    list_contributions
)

router = APIRouter(prefix="/contributions", tags=["Contributions"])


@router.get("", response_model=List[ContributionResponse], summary="List contributions with moderation filters")
def get_all_contributions(
    status: Optional[ContributionStatus] = Query(None, description="Filter by contribution status"),
    validation_status: Optional[ContributionValidation] = Query(None, description="Filter by validation status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List contributions across the platform with filtering by lifecycle status and validation status.
    Useful for maintainers and moderators.
    """
    items, _ = list_contributions(
        db=db,
        status_filter=status,
        validation_filter=validation_status,
        skip=skip,
        limit=limit
    )
    return items


@router.get("/my", response_model=UserContributionTimelineResponse, summary="Get full contribution timeline for authenticated user")
def get_my_timeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the authenticated student's full contribution history and timeline.
    """
    return get_user_contribution_timeline(db=db, user_id=current_user.id)


@router.get("/{user_id}/timeline", response_model=UserContributionTimelineResponse, summary="Get full contribution timeline for user (alias)")
@router.get("/{user_id}", response_model=UserContributionTimelineResponse, summary="Get full contribution timeline for user")
def get_timeline(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Get full contribution history and timeline for a contributor:
    Lifecycle progression: claimed → in_progress → pr_submitted → under_review → changes_requested → accepted → merged.
    """
    return get_user_contribution_timeline(db=db, user_id=user_id)


@router.patch("/{contribution_id}/validate", response_model=ContributionResponse, summary="Update contribution validation status (alias)")
@router.patch("/{contribution_id}/validation", response_model=ContributionResponse, summary="Update contribution validation status")
def moderate_validation(
    contribution_id: int,
    payload: ContributionValidationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update contribution validation status (valid, pending, rejected, duplicate, invalid).
    Typically restricted to maintainers and organizers.
    """
    return update_validation_status(
        db=db,
        contribution_id=contribution_id,
        new_validation=payload.validation_status,
        note=payload.note,
        actor_id=current_user.id
    )


@router.patch("/{contribution_id}/status", response_model=ContributionResponse, summary="Transition contribution status")
def transition_status(
    contribution_id: int,
    new_status: ContributionStatus = Query(..., description="Target status in lifecycle state machine"),
    detail: Optional[str] = Query(None, description="Optional transition note"),
    db: Session = Depends(get_db),
):
    """
    Explicitly advance contribution status according to the valid state machine graph.
    """
    return transition_contribution_status(
        db=db,
        contribution_id=contribution_id,
        new_status=new_status,
        detail=detail
    )
