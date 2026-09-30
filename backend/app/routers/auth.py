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
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status, BackgroundTasks, Header
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GitHubOAuthCallbackRequest,
    GitHubOAuthLinkRequest,
    GitHubOAuthLinkResponse,
    LoginRequest,
    ManualReviewActionRequest,
    ManualReviewItemResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SendVerificationRequest,
    SendVerificationResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
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
    process_email_verification,
    process_id_card_verification,
    register_student,
    create_email_token,
    hash_password,
    request_email_verification_token,
    request_password_reset_otp,
    request_password_reset_token,
    reset_password_with_otp,
    reset_password_with_token,
    review_manual_verification,
    set_user_password,
)
from app.services.storage_service import get_id_card_image
from app.services.email_service import (
    check_email_rate_limit,
    send_verification_email,
    send_password_reset_email,
)

router = APIRouter(prefix="/auth", tags=["Auth & Verification"])
logger = logging.getLogger(__name__)


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
    If the account has a password set, password verification is strictly enforced.
    """
    user = authenticate_user(db=db, identifier=payload.identifier, password=payload.password)

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


@router.post("/set-password", response_model=SetPasswordResponse, summary="Set account password after verification")
def set_password(
    payload: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set a strong password for the authenticated student account.
    Requires an active authenticated session (JWT).
    """
    set_user_password(db=db, user=current_user, password=payload.password)
    return SetPasswordResponse(
        success=True,
        message="Password set successfully. You can now use this password to log in."
    )


# ──────────────────────────────────────────────────────────────────────
# Email Verification Endpoints (Resend)
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/send-verification",
    response_model=SendVerificationResponse,
    summary="Send email verification link via Resend",
)
def send_verification(
    background_tasks: BackgroundTasks,
    payload: Optional[SendVerificationRequest] = None,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Send an email verification link using Resend.
    Can be invoked by an authenticated student (uses account email),
    or unauthenticated by supplying an email address in the payload.
    Enforces per-email cooldown (1/60s, max 5/hr).
    """
    target_email = None
    target_name = "there"

    if authorization and authorization.lower().startswith("bearer "):
        try:
            current_user = get_current_user(authorization=authorization, db=db)
            target_email = current_user.email
            target_name = current_user.name
        except Exception:
            pass

    if not target_email and payload and payload.email:
        target_email = str(payload.email).strip().lower()

    if not target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide an email address or log in to request verification.",
        )

    # Cooldown & rate limiting
    check_email_rate_limit(target_email)

    token_result = request_email_verification_token(db=db, email=target_email)
    if token_result:
        user, raw_token = token_result
        try:
            send_verification_email(
                to_email=user.email,
                name=target_name,
                token=raw_token,
            )
        except Exception as exc:
            logger.error("Failed to send verification email to <%s>: %s", user.email, exc)

    return SendVerificationResponse(
        success=True,
        message="If an account with that email exists, a verification link has been sent to your inbox.",
    )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email address using token",
)
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts single-use verification token, validates expiry and purpose,
    and marks user's email as verified.
    """
    process_email_verification(db=db, raw_token=payload.token)
    return VerifyEmailResponse(
        success=True,
        message="Email verified successfully. You may now continue to your dashboard.",
    )


# ──────────────────────────────────────────────────────────────────────
# Password Reset Endpoints (Token-based Resend + Legacy OTP)
# ──────────────────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=ForgotPasswordResponse, summary="Request password reset via email or roll number")
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Send a password reset link and OTP to the registered student's email address.
    
    Accepts either roll number or email:
    - If the input consists entirely of numbers (digits) -> treated as Roll Number.
      The system looks up the student by roll number, fetches their registered email
      from the database, generates a 6-digit OTP + reset token, and dispatches the email.
    - If the input contains '@' (e.g. ends with @gmail.com or @psit.ac.in) -> treated as Email.
    """
    raw_input = (payload.identifier or payload.email or "").strip()
    if not raw_input:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide your registered roll number or email address.",
        )

    # Detect if user entered a numeric roll number or an email address
    is_numeric_roll = raw_input.isdigit()
    is_email = "@" in raw_input or raw_input.lower().endswith("@gmail.com")

    target_user = None

    if is_numeric_roll:
        # Numeric roll number: look up student in DB to fetch their registered email
        target_user = db.query(User).filter(User.psit_roll_no.ilike(raw_input)).first()
    elif is_email:
        clean_email = raw_input.lower()
        target_user = db.query(User).filter(User.email.ilike(clean_email)).first()
    else:
        # Fallback (alphanumeric roll number or identifier)
        target_user = db.query(User).filter(
            (User.psit_roll_no.ilike(raw_input)) | (User.email.ilike(raw_input))
        ).first()

    if target_user and target_user.email:
        # Generate 6-digit OTP code for instant verification
        otp_num = secrets.randbelow(900_000) + 100_000
        otp_code = str(otp_num)
        new_otp_hash = hash_password(otp_code)

        # Keep recent valid hashes (separated by ';') so re-requested OTPs don't instantly break previous ones
        existing_hashes = [h.strip() for h in (target_user.reset_otp_hash or "").split(";") if h.strip()]
        target_user.reset_otp_hash = ";".join([new_otp_hash] + existing_hashes[:2])
        target_user.reset_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Generate Resend token for 1-click email link (commits both user OTP and token in a single round-trip)
        raw_token = create_email_token(
            db=db,
            user=target_user,
            purpose="reset_password",
            expire_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
        )

        # Dispatch reset email synchronously containing BOTH the reset link and OTP
        try:
            send_password_reset_email(
                to_email=target_user.email,
                name=target_user.name,
                token=raw_token,
                otp_code=otp_code,
            )
        except Exception as exc:
            logger.error("Failed to send reset email to <%s>: %s", target_user.email, exc)

        # Compute masked email (e.g. a***a@gmail.com) for user privacy
        parts = target_user.email.split("@")
        masked_email = parts[0][0] + "***" + parts[0][-1] + "@" + parts[1] if len(parts[0]) > 2 else target_user.email

        if is_numeric_roll:
            return ForgotPasswordResponse(
                success=True,
                message=f"Verification code has been sent to your registered email ({masked_email}). Please check your inbox.",
                email=masked_email,
            )
        else:
            return ForgotPasswordResponse(
                success=True,
                message="If an account with that email exists, password reset instructions have been sent.",
                email=target_user.email,
            )

    # If no account found, return generic message to prevent account enumeration
    if is_numeric_roll:
        return ForgotPasswordResponse(
            success=True,
            message="If an account with that roll number exists, password reset instructions have been sent.",
            email=None,
        )
    else:
        return ForgotPasswordResponse(
            success=True,
            message="If an account with that email exists, password reset instructions have been sent.",
            email=raw_input if is_email else None,
        )


@router.post("/reset-password", response_model=ResetPasswordResponse, summary="Reset password using token or OTP")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Reset password using single-use token from email link, or using 6-digit OTP.
    """
    # 1. Token-based reset (Resend email link flow)
    if payload.token and payload.token.strip():
        reset_password_with_token(
            db=db,
            raw_token=payload.token.strip(),
            new_password=payload.new_password.strip(),
        )
        return ResetPasswordResponse(
            success=True,
            message="Your password has been changed successfully. You can now log in with your new password.",
        )

    # 2. Legacy OTP-based reset
    if payload.identifier and payload.otp:
        reset_password_with_otp(
            db=db,
            identifier=payload.identifier.strip(),
            otp=payload.otp.strip(),
            new_password=payload.new_password.strip(),
        )
        return ResetPasswordResponse(
            success=True,
            message="Your password has been changed successfully in the database. You can now log in with your new password.",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either reset token or identifier with OTP code is required.",
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


@router.get(
    "/id-card-image/{student_id}",
    summary="Admin-only: Retrieve uploaded ID card photo for manual review",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_student_id_card_image(
    student_id: int,
    db: Session = Depends(get_db),
):
    """
    Admin-only: securely serves the stored ID card photo for a student in the
    manual verification queue without exposing raw storage keys or PII publicly.
    """
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )
    if not student.id_card_image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ID card image has been uploaded for this student."
        )

    image_bytes = get_id_card_image(student.id_card_image_url)
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ID card image file not found in storage."
        )

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"inline; filename={student.psit_roll_no}_id_card.jpg",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        }
    )


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
async def link_github(
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

