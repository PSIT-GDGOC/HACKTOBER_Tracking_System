"""Auth & Verification Router.

Endpoints:
- POST /auth/signup              — Student registration (creates pending account; enforces 13-char roll no.)
- POST /auth/login               — Authenticate and receive signed JWT with role claims
- GET  /auth/me                  — Return current authenticated session profile
- POST /auth/verify-id           — Upload ID card photo; backend decodes QR, fetches PSIT portal, cross-checks
- GET  /auth/pending-verifications — Admin review queue for fallback manual approvals
- POST /auth/verify-manual/{id}  — Admin decision (approve / reject)
- GET  /auth/github/login        — Return GitHub OAuth authorization URL
- GET  /auth/github/callback     — GitHub OAuth callback: exchange code → access_token → link GitHub identity
- POST /auth/github/link         — Manually link a GitHub username (fallback / dev use)
"""
import base64
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import User, UserRole
from app.schemas.auth import (
    GitHubOAuthCallbackRequest,
    GitHubOAuthLinkRequest,
    GitHubOAuthLinkResponse,
    LoginRequest,
    ManualReviewActionRequest,
    ManualReviewItemResponse,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    VerifyIDCardRequest,
    VerifyIDCardResponse,
)
from app.schemas.user import UserProfileResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    exchange_github_oauth_code,
    link_github_account,
    list_pending_verifications,
    process_id_card_verification,
    register_student,
    review_manual_verification,
)

router = APIRouter(prefix="/auth", tags=["Auth & Verification"])


# ──────────────────────────────────────────────────────────────────────
# 1.  Signup
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a new student",
)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
):
    """
    Register student with official PSIT roll number (exactly 13 alphanumeric chars) and name.
    Account is created in unverified state — student must complete ID card / QR verification next.
    """
    user = register_student(
        db=db,
        name=payload.name,
        email=payload.email,
        psit_roll_no=payload.psit_roll_no,
    )
    return user


# ──────────────────────────────────────────────────────────────────────
# 2.  Login
# ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Log in with roll number or email")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate student, maintainer, or admin.
    Issues a cryptographically signed JWT scoped by user ID and role.
    Unverified students can still log in but cannot claim issues.
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
        user=UserProfileResponse.model_validate(user),
    )


# ──────────────────────────────────────────────────────────────────────
# 3.  Session profile
# ──────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserProfileResponse, summary="Get authenticated user session")
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile for the currently logged-in user. Protected by Bearer JWT."""
    return current_user


# ──────────────────────────────────────────────────────────────────────
# 4.  ID Card + QR Verification  (fully server-side)
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/verify-id",
    response_model=VerifyIDCardResponse,
    summary="Submit ID card photo for server-side QR + PSIT portal verification",
)
async def verify_id_card(
    payload: VerifyIDCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-side student verification — **the client sends only the raw image**.

    Pipeline (all server-side):
    1. Validates JPEG/PNG format and ≤5 MB size.
    2. Decodes QR from image using OpenCV + pyzbar (5-attempt pipeline).
    3. Validates QR URL format: https://www.psit.ac.in/op/card-preview/<32-hex-token>
    4. Fetches student data from PSIT portal API using the 32-char token.
    5. Cross-checks: roll number must match exactly; name must fuzzy-match ≥70%.
    6. Auto-verifies on full match.
       On any failure → admin manual review queue (never silent rejection).
    """
    # Guard: roll number in request must match the authenticated account
    if current_user.psit_roll_no.strip().upper() != payload.psit_roll_no.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The roll number in your request does not match your registered account.",
        )

    # Decode base64 image → raw bytes
    try:
        b64_str = payload.id_card_image_base64
        if "," in b64_str:                     # strip "data:image/jpeg;base64," prefix
            b64_str = b64_str.split(",", 1)[1]
        image_bytes = base64.b64decode(b64_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoding for ID card image. Strip any data:... prefix before sending.",
        )

    verified, status_code_str, message, qr_token = await process_id_card_verification(
        db=db,
        user=current_user,
        id_card_image_bytes=image_bytes,
    )

    return VerifyIDCardResponse(
        verified=verified,
        status=status_code_str,
        verification_method=current_user.verification_method,
        qr_token=qr_token,
        message=message,
    )


# ──────────────────────────────────────────────────────────────────────
# 5.  Admin manual verification queue
# ──────────────────────────────────────────────────────────────────────

@router.get(
    "/pending-verifications",
    response_model=List[ManualReviewItemResponse],
    summary="Admin review queue for pending verifications",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_pending_verifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Admin-only: returns unverified students who uploaded ID card photos
    but could not be auto-verified (QR unreadable / portal unavailable / name mismatch).
    """
    return list_pending_verifications(db=db, skip=skip, limit=limit)


@router.post(
    "/verify-manual/{student_id}",
    response_model=UserProfileResponse,
    summary="Admin approve or reject student verification",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def manual_verify_student(
    student_id: int,
    payload: ManualReviewActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_user),
):
    """Admin decision: approve or reject student after manual ID review."""
    updated_student = review_manual_verification(
        db=db,
        student_id=student_id,
        action=payload.action,
        admin_user=admin_user,
        reason=payload.reason,
    )
    return updated_student


# ──────────────────────────────────────────────────────────────────────
# 6.  GitHub OAuth  (login URL + callback + manual link)
# ──────────────────────────────────────────────────────────────────────

@router.get("/github/login", summary="Get GitHub OAuth authorization URL")
def github_oauth_login():
    """
    Returns the GitHub OAuth authorization URL for the frontend Auth Wizard.
    Frontend redirects the user to oauth_url; GitHub then redirects back to
    GITHUB_OAUTH_REDIRECT_URI with ?code=... which is handled by /auth/github/callback.
    """
    client_id = settings.GITHUB_CLIENT_ID or "mock-client-id-set-GITHUB_CLIENT_ID-env"
    redirect_uri = settings.GITHUB_OAUTH_REDIRECT_URI
    oauth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope=read:user"
        f"&redirect_uri={redirect_uri}"
    )
    return {
        "oauth_url": oauth_url,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }


@router.post(
    "/github/callback",
    response_model=GitHubOAuthLinkResponse,
    summary="GitHub OAuth callback — exchange code and link GitHub identity",
)
async def github_oauth_callback(
    payload: GitHubOAuthCallbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Called by the frontend after GitHub redirects back with ?code=...

    Flow:
    1. Exchange one-time code for GitHub access token (server-side).
    2. Fetch authenticated GitHub user profile (login, id).
    3. Link GitHub username + id to the student's platform account.
    4. Guard: one GitHub account per student; one student per GitHub account.
    """
    gh_profile = await exchange_github_oauth_code(payload.code)

    updated_user = link_github_account(
        db=db,
        user=current_user,
        github_username=gh_profile["github_username"],
        github_id=gh_profile["github_id"],
    )
    return GitHubOAuthLinkResponse(
        success=True,
        github_username=updated_user.github_username,
        github_id=updated_user.github_id,
        message=(
            f"GitHub account '{updated_user.github_username}' linked successfully. "
            "You can now claim issues and have your PRs tracked automatically."
        ),
    )


@router.post(
    "/github/link",
    response_model=GitHubOAuthLinkResponse,
    summary="Manually link a GitHub username (fallback / dev use)",
)
def link_github(
    payload: GitHubOAuthLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fallback: link GitHub username directly without OAuth code exchange.
    Used during local development or if the OAuth flow is unavailable.
    Prefer /auth/github/callback for production.
    """
    updated_user = link_github_account(
        db=db,
        user=current_user,
        github_username=payload.github_username,
        github_id=payload.github_id,
    )
    return GitHubOAuthLinkResponse(
        success=True,
        github_username=updated_user.github_username,
        github_id=updated_user.github_id,
        message=f"Successfully linked GitHub account '{updated_user.github_username}'.",
    )
