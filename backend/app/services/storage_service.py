import logging
import os
import uuid
from pathlib import Path
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def get_storage_base_dir() -> Path:
    """Return base Path directory for local media storage."""
    base_dir = Path(settings.STORAGE_DIR)
    if not base_dir.is_absolute():
        # Relative to backend root directory
        backend_root = Path(__file__).resolve().parent.parent.parent
        base_dir = backend_root / settings.STORAGE_DIR
    return base_dir


def save_id_card_image(
    user_id: int,
    roll_no: str,
    image_bytes: bytes,
    extension: str = "jpg"
) -> str:
    """
    Persist uploaded student ID card image bytes.
    Supports Supabase Storage bucket with automatic local filesystem fallback.
    Returns the relative storage key (e.g. 'id-cards/2200320100001_a1b2c3d4.jpg').
    """
    clean_roll = roll_no.strip().upper().replace(" ", "_")
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"{clean_roll}_{unique_suffix}.{extension}"
    storage_key = f"id-cards/{filename}"

    # 1. Attempt Supabase Storage upload if credentials are provided
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase_endpoint = (
                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/"
                f"{settings.SUPABASE_STORAGE_BUCKET}/{storage_key}"
            )
            headers = {
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(supabase_endpoint, content=image_bytes, headers=headers)
                if res.status_code in (200, 201):
                    logger.info("Uploaded ID card image to Supabase Storage for user %s.", user_id)
                    return storage_key
                else:
                    logger.warning(
                        "Supabase storage upload returned status %s: %s. Falling back to disk storage.",
                        res.status_code, res.text[:200]
                    )
        except Exception as exc:
            logger.warning("Supabase storage upload failed (%s). Falling back to disk storage.", exc)

    # 2. Local filesystem storage fallback
    try:
        base_dir = get_storage_base_dir()
        dest_file = base_dir / storage_key
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(image_bytes)
        logger.info("Saved ID card image to local storage (%s) for user %s.", dest_file.name, user_id)
        return storage_key
    except Exception as exc:
        logger.error("Failed to write ID card image to local filesystem: %s", exc)
        return storage_key


def get_id_card_image(storage_key: str) -> Optional[bytes]:
    """
    Retrieve stored ID card image bytes by its storage key.
    Checks local filesystem first, then Supabase Storage.
    """
    if not storage_key:
        return None

    # Sanitize storage key against path traversal
    normalized_key = os.path.normpath(storage_key).replace("\\", "/")
    if normalized_key.startswith("..") or "/../" in normalized_key:
        logger.warning("Path traversal attempt in storage key: %s", storage_key)
        return None

    # 1. Check local filesystem
    try:
        base_dir = get_storage_base_dir()
        local_file = base_dir / normalized_key
        if local_file.is_file():
            return local_file.read_bytes()
    except Exception as exc:
        logger.warning("Local storage read error for key %s: %s", storage_key, exc)

    # 2. Check Supabase Storage
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase_endpoint = (
                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/authenticated/"
                f"{settings.SUPABASE_STORAGE_BUCKET}/{normalized_key}"
            )
            headers = {
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.get(supabase_endpoint, headers=headers)
                if res.status_code == 200:
                    return res.content
        except Exception as exc:
            logger.warning("Supabase storage read error for key %s: %s", storage_key, exc)

    return None
