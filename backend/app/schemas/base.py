"""Base schema definitions and uniform ISO-8601 UTC datetime serialization."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_serializer


def serialize_utc_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Ensure any naive or timezone-aware datetime serializes as ISO-8601 with trailing 'Z'."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    elif not iso.endswith("Z"):
        return iso + "Z"
    return iso


class AppBaseModel(BaseModel):
    """
    Base Pydantic model for application schemas.
    Ensures all datetime fields are automatically serialized to ISO-8601 UTC with 'Z' suffix.
    """
    @field_serializer("*", mode="wrap")
    def _serialize_datetimes(self, value, handler, info):
        res = handler(value)
        if isinstance(value, datetime):
            return serialize_utc_datetime(value)
        return res
