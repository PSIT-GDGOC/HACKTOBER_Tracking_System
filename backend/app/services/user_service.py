from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    User,
    Contribution,
    PullRequest, PRStatus,
    Claim, ClaimStatus
)
from app.schemas.user import (
    UserPublicProfileResponse,
    UserProfileResponse,
    UserUpdateProfileRequest
)
from app.services.contribution_service import _build_contribution_response


def get_user_public_profile(db: Session, user_id: int) -> UserPublicProfileResponse:
    """
    Retrieve read-only public profile for any participant.
    Preserves privacy by omitting sensitive institutional roll numbers and personal emails.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    contributions_count = db.query(Contribution).filter(Contribution.user_id == user_id).count()
    merged_prs_count = (
        db.query(PullRequest)
        .filter(PullRequest.user_id == user_id, PullRequest.status == PRStatus.MERGED)
        .count()
    )
    active_claims_count = (
        db.query(Claim)
        .filter(Claim.user_id == user_id, Claim.status == ClaimStatus.ACTIVE)
        .count()
    )

    recent_contributions = (
        db.query(Contribution)
        .filter(Contribution.user_id == user_id)
        .order_by(Contribution.created_at.desc())
        .limit(5)
        .all()
    )

    return UserPublicProfileResponse(
        id=user.id,
        name=user.name,
        github_username=user.github_username,
        role=user.role,
        verified=user.verified,
        created_at=user.created_at,
        contributions_count=contributions_count,
        merged_prs_count=merged_prs_count,
        active_claims_count=active_claims_count,
        recent_contributions=[_build_contribution_response(c) for c in recent_contributions]
    )


def get_current_user_profile(user: User) -> UserProfileResponse:
    """Retrieve full authenticated user profile."""
    return UserProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        psit_roll_no=user.psit_roll_no,
        verified=user.verified,
        verified_at=user.verified_at,
        verification_method=user.verification_method,
        github_username=user.github_username,
        github_id=user.github_id,
        role=user.role,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


def update_current_user_profile(
    db: Session,
    user: User,
    update_data: UserUpdateProfileRequest
) -> UserProfileResponse:
    """Update profile information for the authenticated user."""
    if update_data.name is not None:
        user.name = update_data.name.strip()

    if update_data.github_username is not None:
        new_gh = update_data.github_username.strip()
        # Verify uniqueness
        existing = (
            db.query(User)
            .filter(User.github_username.ilike(new_gh), User.id != user.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub username '{new_gh}' is already associated with another student account."
            )
        user.github_username = new_gh

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return get_current_user_profile(user)
