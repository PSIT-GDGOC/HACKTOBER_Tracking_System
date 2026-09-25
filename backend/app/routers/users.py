from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.user import (
    UserPublicProfileResponse,
    UserProfileResponse,
    UserUpdateProfileRequest
)
from app.services.user_service import (
    get_user_public_profile,
    get_current_user_profile,
    update_current_user_profile
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse, summary="Get own profile")
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the full profile for the authenticated student/maintainer/admin.
    """
    return get_current_user_profile(user=current_user)


@router.patch("/me", response_model=UserProfileResponse, summary="Update own profile")
def update_my_profile(
    update_data: UserUpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update profile details (such as display name or linked GitHub username) for the authenticated user.
    """
    return update_current_user_profile(db=db, user=current_user, update_data=update_data)


@router.get("/{user_id}", response_model=UserPublicProfileResponse, summary="Get public profile")
def get_public_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve a public read-only contributor profile with contribution stats and recent open-source activity.
    """
    return get_user_public_profile(db=db, user_id=user_id)
