"""Auth & Verification Router.

Endpoints:
- POST /auth/signup: Student registration (creates pending student account)
- POST /auth/login: Student / Maintainer / Admin login (issues signed JWT)
- GET  /auth/me: Retrieve current authenticated session profile
- POST /auth/verify-id: ID card photo upload & QR verification
- GET  /auth/pending-verifications: Admin manual verification review queue
- POST /auth/verify-manual/{student_id}: Admin approves or rejects manual verification
- GET  /auth/github/login: Initiates GitHub OAuth flow
- POST /auth/github/link: Links GitHub username & identity to student account
"""
import base64
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import User, UserRole
from app.schemas.auth import (
    SignupRequest,
    SignupResponse,
    LoginRequest,
    TokenResponse,
    VerifyIDCardRequest,
    VerifyIDCardResponse,
    ManualReviewItemResponse,
    ManualReviewActionRequest,
    GitHubOAuthLinkRequest,
    GitHubOAuthLinkResponse,
)
from app.schemas.user import UserProfileResponse
from app.services.auth_service import (
    register_student,
    authenticate_user,
    create_access_token,
    process_id_card_verification,
    list_pending_verifications,
    review_manual_verification,
    link_github_account,
)

router = APIRouter(prefix="/auth", tags=["Auth & Verification"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED, summary="Register as a new student")
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
):
    """
    Register student with official PSIT roll number and name.
    Account is created in unverified state pending ID card / QR verification.
    """
    user = register_student(
        db=db,
        name=payload.name,
        email=payload.email,
        psit_roll_no=payload.psit_roll_no
    )
    return user


@router.post("/login", response_model=TokenResponse, summary="Log in with roll number or email")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate student, maintainer, or admin.
    Issues a cryptographically signed JWT scoped by user ID and role.
    """
    user = authenticate_user(db=db, identifier=payload.identifier)

    token_data = {
        "sub": str(user.id),
        "roll_no": user.psit_roll_no,
        "role": user.role.value,
        "verified": user.verified,
    }
    token = create_access_token(data=token_data)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserProfileResponse.model_validate(user)
    )


@router.get("/me", response_model=UserProfileResponse, summary="Get authenticated user session")
def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve profile details for the currently logged-in user session.
    Protected by JWT Bearer token authentication.
    """
    return current_user


@router.post("/verify-id", response_model=VerifyIDCardResponse, summary="Submit ID card and QR code for verification")
def verify_id_card(
    payload: VerifyIDCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-side student verification:
    1. Validates ID card photo format and size.
    2. Performs server-side cross-check of roll number and fuzzy name against portal record.
    3. Auto-verifies on exact roll + fuzzy name match; routes to admin review queue on mismatch/missing data.
    """
    # Verify roll number matches current user
    if current_user.psit_roll_no.strip().lower() != payload.psit_roll_no.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplied roll number does not match authenticated user account."
        )

    # Decode image bytes if base64 provided
    image_bytes = None
    if payload.id_card_image_base64:
        try:
            b64_str = payload.id_card_image_base64
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            image_bytes = base64.b64decode(b64_str)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64 encoding for ID card image."
            )

    verified, status_code_str, message = process_id_card_verification(
        db=db,
        user=current_user,
        id_card_image_bytes=image_bytes,
        qr_token=payload.qr_token,
        portal_snapshot=payload.portal_snapshot,
    )

    return VerifyIDCardResponse(
        verified=verified,
        status=status_code_str,
        verification_method=current_user.verification_method,
        message=message
    )


@router.get(
    "/pending-verifications",
    response_model=List[ManualReviewItemResponse],
    summary="Admin review queue for pending verifications",
    dependencies=[Depends(require_roles(UserRole.ADMIN))]
)
def get_pending_verifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Admin-only review queue: returns unverified students who uploaded ID card photos
    that require manual review and verification decision.
    """
    items = list_pending_verifications(db=db, skip=skip, limit=limit)
    return items


@router.post(
    "/verify-manual/{student_id}",
    response_model=UserProfileResponse,
    summary="Admin approve or reject student verification",
    dependencies=[Depends(require_roles(UserRole.ADMIN))]
)
def manual_verify_student(
    student_id: int,
    payload: ManualReviewActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_user),
):
    """
    Admin decision: approve or reject student verification.
    If approved, student's account is verified with method 'manual'.
    """
    updated_student = review_manual_verification(
        db=db,
        student_id=student_id,
        action=payload.action,
        admin_user=admin_user,
        reason=payload.reason
    )
    return updated_student


@router.get("/github/login", summary="Initiate GitHub OAuth login URL")
def github_oauth_login():
    """
    Returns GitHub OAuth authorization URL for the frontend Auth Wizard.
    """
    client_id = getattr(settings, "GITHUB_CLIENT_ID", "") or "mock-github-client-id"
    redirect_uri = "https://hacktoberfest.gdgocpsit.com/auth/callback"
    oauth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope=read:user"
        f"&redirect_uri={redirect_uri}"
    )
    return {
        "oauth_url": oauth_url,
        "client_id": client_id,
        "redirect_uri": redirect_uri
    }


@router.post("/github/link", response_model=GitHubOAuthLinkResponse, summary="Link GitHub account to student profile")
def link_github(
    payload: GitHubOAuthLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Links authenticated student's profile to their verified GitHub username and GitHub ID.
    Enforces uniqueness across the event.
    """
    updated_user = link_github_account(
        db=db,
        user=current_user,
        github_username=payload.github_username,
        github_id=payload.github_id
    )
    return GitHubOAuthLinkResponse(
        success=True,
        github_username=updated_user.github_username,
        github_id=updated_user.github_id,
        message=f"Successfully linked GitHub account '{updated_user.github_username}'."
    )
