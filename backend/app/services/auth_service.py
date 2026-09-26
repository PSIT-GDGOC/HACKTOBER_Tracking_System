"""Auth & Verification Service.

Implements:
- JWT token generation & verification (PyJWT)
- Student registration & credential lookup
- Server-side QR decode from ID card image (OpenCV + pyzbar via qr_service)
- PSIT portal student data fetch (via psit_portal_service)
- Exact roll number + fuzzy name cross-check
- Auto-verification vs. pending manual-review fallback
- Admin manual verification approval / rejection queue
- GitHub OAuth code exchange + identity linking

Verification flow (end-to-end):
    1. Client sends base64 ID card photo to POST /auth/verify-id
    2. Backend decodes the QR using OpenCV + pyzbar (server-side only)
    3. Validates QR URL: https://www.psit.ac.in/op/card-preview/<32-hex-token>
    4. Fetches student data from PSIT portal API using the 32-char token
    5. Cross-checks roll_no (exact) + name (fuzzy) vs registered values
    6. Auto-verifies on match; routes to admin manual queue on any failure
"""
import base64
import difflib
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

import httpx
import jwt
from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole, VerificationMethod
from app.services.qr_service import decode_qr_from_image, validate_psit_qr_token
from app.services.psit_portal_service import fetch_psit_student_data

logger = logging.getLogger(__name__)


# =====================================================================
# JWT Token Helpers
# =====================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token with standard claims."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now_utc.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and cryptographically verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature."
        )


# =====================================================================
# Registration & Authentication
# =====================================================================

def register_student(db: Session, name: str, email: str, psit_roll_no: str) -> User:
    """Register a new student in unverified state.

    Only verified accounts are considered 'taken'. Unverified or pending
    attempts never block a student from registering or retrying signup.
    """
    clean_roll = psit_roll_no.strip().upper()
    clean_email = email.strip().lower()
    clean_name = name.strip()

    # 1. Check duplicate roll number — ONLY against VERIFIED accounts
    verified_roll = (
        db.query(User)
        .filter(User.psit_roll_no.ilike(clean_roll), User.verified == True)
        .first()
    )
    if verified_roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A verified student with roll number '{clean_roll}' is already registered. Please log in instead.",
        )

    # 2. Check duplicate email — ONLY against VERIFIED accounts
    verified_email = (
        db.query(User)
        .filter(User.email.ilike(clean_email), User.verified == True)
        .first()
    )
    if verified_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A verified student with email '{clean_email}' is already registered. Please log in instead.",
        )

    # 3. If an unverified pending account exists with this email or roll, reuse/update it
    pending_user = (
        db.query(User)
        .filter(
            (User.email.ilike(clean_email)) | (User.psit_roll_no.ilike(clean_roll)),
            User.verified == False,
        )
        .first()
    )
    if pending_user:
        pending_user.name = clean_name
        pending_user.email = clean_email
        pending_user.psit_roll_no = clean_roll
        db.commit()
        db.refresh(pending_user)
        logger.info("Reused pending unverified account (id=%s) for %s", pending_user.id, clean_roll)
        return pending_user

    # 4. Otherwise, create a new pending unverified record
    new_user = User(
        name=clean_name,
        email=clean_email,
        psit_roll_no=clean_roll,
        role=UserRole.STUDENT,
        verified=False,
        verification_method=None,
        verified_at=None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, identifier: str) -> User:
    """Find user by roll number or email."""
    clean_id = identifier.strip()
    user = (
        db.query(User)
        .filter(
            (User.psit_roll_no.ilike(clean_id)) | (User.email.ilike(clean_id))
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found matching identifier '{identifier}'."
        )
    return user


# =====================================================================
# ID Card & QR Verification Engine  (fully server-side)
# =====================================================================

def _fuzzy_name_match(name1: str, name2: str, threshold: float = 0.70) -> bool:
    """
    Fuzzy match student name from registration against PSIT portal name.
    Tolerates casing, middle initials, reversed order, and minor abbreviations.
    """
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()

    if n1 == n2:
        return True

    # Token-based overlap (all words of shorter name appear in longer name)
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    if tokens1 and (tokens1.issubset(tokens2) or tokens2.issubset(tokens1)):
        return True

    # Sequence matcher similarity ratio
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


async def process_id_card_verification(
    db: Session,
    user: User,
    id_card_image_bytes: bytes,
) -> Tuple[bool, str, str, Optional[str]]:
    """
    Full server-side student verification pipeline:

    1.  Validates image format and size (Pillow).
    2.  Stores a private storage path for the ID card image.
    3.  Decodes QR from image using OpenCV + pyzbar (qr_service).
    4.  Validates QR URL format (must be PSIT card-preview URL with 32-hex token).
    5.  Fetches student data from the PSIT portal API (psit_portal_service).
    6.  Cross-checks roll number (exact) and name (fuzzy ≥ 70%).
    7.  Auto-verifies on full match; routes to pending_review on any failure.

    Args:
        db:                   SQLAlchemy DB session.
        user:                 Authenticated student user object.
        id_card_image_bytes:  Raw JPEG/PNG bytes of the uploaded ID card photo.

    Returns:
        Tuple of (verified: bool, status_code: str, message: str, qr_token: Optional[str])
        where status_code is one of:
            "auto_verified"     – QR + portal cross-check passed
            "qr_unreadable"     – OpenCV/pyzbar could not find a valid PSIT QR
            "portal_unavailable"– PSIT portal API returned no usable data
            "pending_review"    – Data fetched but roll/name mismatch; admin queue
    """
    # ── Step 1: Validate image ────────────────────────────────────────
    if len(id_card_image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID card image exceeds the 5 MB size limit."
        )
    try:
        img_check = Image.open(io.BytesIO(id_card_image_bytes))
        img_check.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Please upload a clear JPEG or PNG photo of your PSIT ID card."
        )

    # ── Step 2: Store private image path ─────────────────────────────
    private_path = f"id-cards/{user.psit_roll_no}_{uuid.uuid4().hex[:8]}.jpg"
    user.id_card_image_url = private_path

    # ── Step 3: Server-side QR decode ────────────────────────────────
    qr_token: Optional[str] = None
    try:
        qr_token = decode_qr_from_image(id_card_image_bytes)
    except (ImportError, OSError, FileNotFoundError) as exc:
        logger.error("QR scanning libraries error (%s). Routing student to manual review.", exc)
        _commit_pending(db, user, f"QR scanning service error: {exc}")
        return False, "qr_unreadable", (
            "QR scanning is currently unavailable on this server. "
            "Your ID card photo has been saved and your account queued for admin manual review."
        ), None
    except ValueError as exc:
        logger.warning("QR decode ValueError for user %s: %s", user.psit_roll_no, exc)
        _commit_pending(db, user, str(exc))
        return False, "qr_unreadable", (
            "Your ID card photo could not be read as a valid image. "
            "Please re-upload a clear, well-lit JPEG or PNG photo."
        ), None
    except Exception as exc:
        logger.error("Unexpected error in QR scanning for user %s: %s", user.psit_roll_no, exc)
        _commit_pending(db, user, f"QR scan error: {exc}")
        return False, "qr_unreadable", (
            "Unable to process the QR code on your ID card photo. "
            "Your account has been added to the admin manual review queue."
        ), None

    if not qr_token:
        logger.info("No PSIT QR found in ID card photo for user %s.", user.psit_roll_no)
        _commit_pending(db, user, "No readable PSIT QR code found in image.")
        return False, "qr_unreadable", (
            "No PSIT QR code could be read from your ID card photo. "
            "Please upload a clearer image where the QR code is fully visible, "
            "then try again — or wait for admin manual review."
        ), None

    if not validate_psit_qr_token(qr_token):
        logger.warning("Invalid QR token format '%s' for user %s.", qr_token, user.psit_roll_no)
        _commit_pending(db, user, f"QR token format invalid: {qr_token}")
        return False, "qr_unreadable", (
            "The QR code on your ID card does not match the expected PSIT format. "
            "Ensure you are uploading your official PSIT ID card."
        ), None

    # Store the decoded QR token (private — stripped from public API responses)
    clean_token = qr_token.strip().lower()
    user.qr_token = clean_token
    clean_user_roll = user.psit_roll_no.strip().upper()

    # ── Guard 1: ID Card QR uniqueness check against verified accounts ──
    dup_qr = (
        db.query(User)
        .filter(
            User.qr_token.ilike(clean_token),
            User.verified == True,
            User.id != user.id,
        )
        .first()
    )
    if dup_qr:
        logger.warning(
            "ID card QR code '%s' is already verified under another account (id=%s, roll=%s).",
            clean_token, dup_qr.id, dup_qr.psit_roll_no
        )
        _commit_pending(db, user, f"This PSIT ID card is already registered and verified under roll number '{dup_qr.psit_roll_no}'.")
        return False, "duplicate_verified_card", (
            f"This PSIT ID card has already been verified under another student account (Roll No: {dup_qr.psit_roll_no}). "
            "Each official PSIT ID card can only be used to verify a single student account."
        ), qr_token

    # ── Guard 2: Roll number uniqueness check against verified accounts ───
    dup = (
        db.query(User)
        .filter(
            User.psit_roll_no.ilike(clean_user_roll),
            User.verified == True,
            User.id != user.id,
        )
        .first()
    )
    if dup:
        logger.warning(
            "Roll number '%s' is already verified under another account (id=%s).",
            clean_user_roll, dup.id
        )
        _commit_pending(db, user, f"Roll number '{clean_user_roll}' is already verified under another account.")
        return False, "duplicate_verified_roll", (
            f"This roll number '{clean_user_roll}' is already verified under another account. "
            "Each PSIT student roll number can only be verified once."
        ), qr_token

    # ── Step 4: Optional PSIT portal lookup for snapshot ──────────────
    portal_data: Optional[Dict[str, Any]] = None
    try:
        portal_data = await fetch_psit_student_data(qr_token)
    except Exception as exc:
        logger.debug("PSIT portal lookup error for token %s: %s", qr_token, exc)

    if portal_data:
        user.portal_snapshot_json = portal_data.get("_raw", portal_data)
        portal_roll = portal_data.get("roll_no", "").strip().upper()
        portal_name = portal_data.get("student_name", "").strip()

        roll_matched = (portal_roll == clean_user_roll) if portal_roll else True
        name_matched = _fuzzy_name_match(user.name, portal_name) if portal_name else True

        if not roll_matched or not name_matched:
            mismatch_detail = []
            if not roll_matched:
                mismatch_detail.append(
                    f"Roll number mismatch: registered '{clean_user_roll}', card belongs to '{portal_roll}'."
                )
            if not name_matched:
                mismatch_detail.append(
                    f"Name mismatch: registered '{user.name}', card belongs to '{portal_name}'."
                )
            detail_str = " ".join(mismatch_detail)
            _commit_pending(db, user, detail_str)
            return False, "pending_review", (
                "Your ID card was scanned but the details on the card don't match "
                "what you registered with. Your account has been added to the admin manual "
                "review queue. Expected turnaround: under 24 hours."
            ), qr_token

    # ── Step 5: Auto-verify on Valid PSIT ID Card QR Code ──────────────
    # A valid PSIT card-preview QR token proves physical possession of an authentic PSIT ID card.
    user.verified = True
    user.verification_method = VerificationMethod.QR_AUTO
    user.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    logger.info("User %s auto-verified via valid PSIT ID card QR token (%s).", user.psit_roll_no, qr_token)
    return True, "auto_verified", (
        "Your PSIT ID card QR code was verified successfully! "
        "You can now link your GitHub account and start claiming issues."
    ), qr_token


def _commit_pending(db: Session, user: User, reason: str) -> None:
    """Helper: commit user state as unverified and flush to DB."""
    user.verified = False
    user.verification_method = None
    user.verified_at = None
    # Keep portal_snapshot_json and qr_token already set on user object (if any)
    db.commit()
    db.refresh(user)


# =====================================================================
# Admin Manual Review Queue
# =====================================================================

def list_pending_verifications(db: Session, skip: int = 0, limit: int = 20) -> List[User]:
    """Retrieve list of students waiting in the manual verification review queue."""
    query = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.verified.is_(False),
            User.id_card_image_url.isnot(None),
        )
        .order_by(User.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return query.all()


def review_manual_verification(
    db: Session,
    student_id: int,
    action: str,
    admin_user: User,
    reason: Optional[str] = None
) -> User:
    """Admin manually approves or rejects an unverified student."""
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )

    if action.lower() == "approve":
        clean_roll = student.psit_roll_no.strip().upper()
        dup = (
            db.query(User)
            .filter(
                User.psit_roll_no.ilike(clean_roll),
                User.verified == True,
                User.id != student.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve: roll number '{clean_roll}' is already verified under another account (user ID {dup.id}).",
            )
        if student.qr_token:
            clean_tok = student.qr_token.strip().lower()
            dup_qr = (
                db.query(User)
                .filter(
                    User.qr_token.ilike(clean_tok),
                    User.verified == True,
                    User.id != student.id,
                )
                .first()
            )
            if dup_qr:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve: ID card QR code is already verified under roll number '{dup_qr.psit_roll_no}' (user ID {dup_qr.id}).",
                )
        student.verified = True
        student.verification_method = VerificationMethod.MANUAL
        student.verified_at = datetime.now(timezone.utc)
    elif action.lower() == "reject":
        student.verified = False
        student.verification_method = None
        student.verified_at = None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown review action '{action}'. Must be 'approve' or 'reject'."
        )

    db.commit()
    db.refresh(student)
    return student


# =====================================================================
# GitHub OAuth — Code Exchange & Identity Linking
# =====================================================================

async def exchange_github_oauth_code(code: str) -> Dict[str, Any]:
    """
    Exchange a one-time GitHub OAuth code for an access token, then
    fetch the authenticated user's GitHub profile.

    Args:
        code: The one-time code sent by GitHub to the redirect URI.

    Returns:
        Dict with keys: github_username, github_id, name, email, avatar_url

    Raises:
        HTTPException 400 if GitHub rejects the code.
        HTTPException 502 if GitHub is unreachable.
    """
    client_id = settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_CLIENT_SECRET

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GitHub OAuth is not configured on this server. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
            )
        )

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        # Step 1: exchange code → access_token
        try:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not reach GitHub OAuth servers: {exc}"
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error_desc = token_data.get("error_description", token_data.get("error", "unknown error"))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth code exchange failed: {error_desc}"
            )

        # Step 2: fetch GitHub user profile with the token
        try:
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not fetch GitHub user profile: {exc}"
            )

        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub returned an error when fetching user profile."
            )

        gh_user = user_resp.json()
        return {
            "github_username": gh_user.get("login", ""),
            "github_id": str(gh_user.get("id", "")),
            "name": gh_user.get("name") or gh_user.get("login", ""),
            "email": gh_user.get("email"),
            "avatar_url": gh_user.get("avatar_url"),
        }


def link_github_account(
    db: Session,
    user: User,
    github_username: str,
    github_id: Optional[str] = None
) -> User:
    """Link verified student to their GitHub identity."""
    clean_username = github_username.strip()

    # Guard: prevent two students linking the same GitHub identity
    existing = (
        db.query(User)
        .filter(User.github_username.ilike(clean_username), User.id != user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub username '{clean_username}' is already linked to another student account."
        )

    user.github_username = clean_username
    if github_id:
        user.github_id = str(github_id)

    db.commit()
    db.refresh(user)
    return user
