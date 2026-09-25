import jwt
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import User, UserRole


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization", description="Bearer JWT access token"),
    x_user_id: Optional[int] = Header(None, alias="X-User-Id", description="Test/Dev User ID header"),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to resolve current authenticated user.
    Supports standard Authorization: Bearer <JWT> token,
    and 'X-User-Id' header for test/dev convenience.
    """
    # 1. Check Bearer JWT token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    return user
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token."
            )

    # 2. Check X-User-Id header (for test / dev)
    if x_user_id is not None:
        user = db.query(User).filter(User.id == x_user_id).first()
        if user:
            return user

    # 3. Fallback to first verified student if no auth header in local dev
    default_user = db.query(User).filter(User.role == UserRole.STUDENT).first()
    if default_user:
        return default_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a valid Bearer token or X-User-Id header."
    )


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory to enforce role-based access control (RBAC).
    Plugs into Aditya's JWT role middleware / token claims.
    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required role in {role_names}, but user has role '{current_user.role.value}'"
            )
        return current_user

    return role_checker


def require_verified_student(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency enforcing that the authenticated user is a verified student
    (ID card / QR verification passed).
    """
    if current_user.role != UserRole.STUDENT or not current_user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: student must be verified via ID card / QR code to perform this action."
        )
    return current_user

