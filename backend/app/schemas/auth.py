"""Pydantic schemas for Auth & Verification Module."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re

from app.models.user import UserRole, VerificationMethod
from app.schemas.user import UserProfileResponse

# PSIT roll numbers are exactly 13 alphanumeric characters (e.g. 2100330100051)
_PSIT_ROLL_RE = re.compile(r"^[A-Za-z0-9]{13}$")


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full student name as on PSIT ID card")
    email: str = Field(..., min_length=5, max_length=255, description="Student email address")
    psit_roll_no: str = Field(..., description="Official PSIT roll number — exactly 13 alphanumeric characters")

    @field_validator("psit_roll_no")
    @classmethod
    def validate_roll_number(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) != 13:
            raise ValueError(
                f"PSIT roll number must be exactly 13 characters long (got {len(clean)}). "
                "Example: 2100330100051"
            )
        if not _PSIT_ROLL_RE.match(clean):
            raise ValueError("PSIT roll number must contain only letters and digits.")
        return clean.upper()  # normalise to uppercase


class SignupResponse(BaseModel):
    id: int
    name: str
    email: str
    psit_roll_no: str
    role: UserRole
    verified: bool
    status: str = "pending_verification"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="PSIT roll number or email address")
    password: Optional[str] = Field(None, description="Account password")


class SetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128, description="New strong password (min 8 characters)")


class SetPasswordResponse(BaseModel):
    success: bool = True
    message: str = "Password set successfully."


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class VerifyIDCardRequest(BaseModel):
    """
    Request body for POST /auth/verify-id.

    The client sends the raw ID card image as a base64 string.
    The backend performs ALL verification server-side:
      1. Decodes the QR from the image using OpenCV + pyzbar
      2. Validates the QR URL format (https://www.psit.ac.in/op/card-preview/<32-hex>)
      3. Fetches student data from the PSIT portal API using the 32-char token
      4. Cross-checks roll number (exact) and name (fuzzy) against registered values
    """
    psit_roll_no: str = Field(..., description="Student roll number to verify (must be 13 chars)")
    id_card_image_base64: str = Field(
        ...,
        description=(
            "Base64-encoded ID card photo (JPEG or PNG). "
            "Strip the data:image/...;base64, prefix before sending."
        )
    )

    @field_validator("psit_roll_no")
    @classmethod
    def validate_roll_number(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) != 13:
            raise ValueError(f"Roll number must be exactly 13 characters (got {len(clean)}).")
        if not _PSIT_ROLL_RE.match(clean):
            raise ValueError("Roll number must contain only letters and digits.")
        return clean.upper()


class VerifyIDCardResponse(BaseModel):
    verified: bool
    status: str  # "auto_verified" | "pending_review" | "qr_unreadable" | "portal_unavailable"
    verification_method: Optional[VerificationMethod] = None
    qr_token: Optional[str] = None      # the 32-char hex token found in QR (for client display)
    message: str


class ManualReviewItemResponse(BaseModel):
    id: int
    name: str
    email: str
    psit_roll_no: str
    verified: bool
    id_card_image_url: Optional[str] = None
    qr_token: Optional[str] = None
    portal_snapshot_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManualReviewActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$", description="'approve' or 'reject'")
    reason: Optional[str] = Field(None, max_length=500, description="Optional admin review note")


class GitHubOAuthLinkRequest(BaseModel):
    github_username: str = Field(..., min_length=1, max_length=100, description="GitHub username")
    github_id: Optional[str] = Field(None, description="GitHub numeric user ID")


class GitHubOAuthLinkResponse(BaseModel):
    success: bool
    github_username: str
    github_id: Optional[str] = None
    message: str


class GitHubOAuthCallbackRequest(BaseModel):
    """Sent by frontend after GitHub redirects back with ?code=..."""
    code: str = Field(..., description="One-time OAuth code received from GitHub callback")
