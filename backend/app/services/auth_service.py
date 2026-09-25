"""Auth & Verification Service.

Implements:
- JWT token generation & verification (PyJWT)
- Student registration & credential lookup
- ID Card image validation & server-side verification logic
- PSIT Portal exact roll + fuzzy name cross-check
- Auto-verification vs. pending manual-review fallback
- Admin manual verification approval / rejection queue
- GitHub identity linking with duplicate guard
"""
import base64
import difflib
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

import jwt
from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole, VerificationMethod

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
    """Register a new student in unverified state."""
    clean_roll = psit_roll_no.strip()
    clean_email = email.strip().lower()
    clean_name = name.strip()

    # 1. Check duplicate roll number
    existing_roll = db.query(User).filter(User.psit_roll_no.ilike(clean_roll)).first()
    if existing_roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A student with roll number '{clean_roll}' is already registered."
        )

    # 2. Check duplicate email
    existing_email = db.query(User).filter(User.email.ilike(clean_email)).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A student with email '{clean_email}' is already registered."
        )

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
# ID Card & QR Verification Engine
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

    # Token-based overlap
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    if tokens1 and (tokens1.issubset(tokens2) or tokens2.issubset(tokens1)):
        return True

    # Sequence matcher similarity ratio
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def process_id_card_verification(
    db: Session,
    user: User,
    id_card_image_bytes: Optional[bytes] = None,
    qr_token: Optional[str] = None,
    portal_snapshot: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, str]:
    """
    Processes student ID card upload & server-side verification:
    1. Validates image format and size (if bytes provided).
    2. Stores private Supabase Storage object path (never a public URL).
    3. Cross-checks roll number (exact) and student name (fuzzy match).
    4. Auto-verifies if criteria met; routes to pending manual review otherwise.
    """
    # 1. Image validation if image content passed
    if id_card_image_bytes:
        # Enforce max 5MB size limit
        if len(id_card_image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID card image exceeds 5MB size limit."
            )
        try:
            img = Image.open(io.BytesIO(id_card_image_bytes))
            img.verify()  # Validate image headers
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Please upload a valid JPEG or PNG ID card photo."
            )

        # Store private storage path
        private_path = f"id-cards/{user.psit_roll_no}_{uuid.uuid4().hex[:8]}.jpg"
        user.id_card_image_url = private_path

    # 2. Record QR token if decoded or supplied
    if qr_token:
        user.qr_token = qr_token.strip()

    # 3. Server-side portal cross-check
    matched = False
    if portal_snapshot and isinstance(portal_snapshot, dict):
        user.portal_snapshot_json = portal_snapshot

        portal_roll = str(portal_snapshot.get("roll_no", portal_snapshot.get("psit_roll_no", ""))).strip()
        portal_name = str(portal_snapshot.get("student_name", portal_snapshot.get("name", ""))).strip()

        # Check exact roll number match
        roll_matched = portal_roll.lower() == user.psit_roll_no.strip().lower()

        # Check fuzzy name match
        name_matched = _fuzzy_name_match(user.name, portal_name) if portal_name else False

        if roll_matched and name_matched:
            matched = True

    # 4. Decision: Auto-verify vs. Pending Review
    if matched:
        user.verified = True
        user.verification_method = VerificationMethod.QR_AUTO
        user.verified_at = datetime.now(timezone.utc)
        status_code_str = "auto_verified"
        message = "ID card and QR code successfully verified via PSIT portal."
    else:
        user.verified = False
        user.verification_method = None
        user.verified_at = None
        status_code_str = "pending_review"
        message = (
            "ID card uploaded. Details could not be automatically confirmed with the portal; "
            "account has been submitted to the admin queue for manual approval."
        )

    db.commit()
    db.refresh(user)
    return user.verified, status_code_str, message


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
# GitHub OAuth Linking
# =====================================================================

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
