"""Pydantic schemas for Auth & Verification Module."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole, VerificationMethod
from app.schemas.user import UserProfileResponse


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full student name as on PSIT ID card")
    email: str = Field(..., min_length=5, max_length=255, description="Student email address")
    psit_roll_no: str = Field(..., min_length=2, max_length=50, description="Official PSIT roll number")


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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class VerifyIDCardRequest(BaseModel):
    psit_roll_no: str = Field(..., description="Student roll number to verify")
    qr_token: Optional[str] = Field(None, description="Decoded QR payload from ID card")
    id_card_image_base64: Optional[str] = Field(None, description="Base64-encoded ID card photo")
    portal_snapshot: Optional[Dict[str, Any]] = Field(None, description="PSIT portal student record")


class VerifyIDCardResponse(BaseModel):
    verified: bool
    status: str  # "auto_verified" | "pending_review"
    verification_method: Optional[VerificationMethod] = None
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
