from typing import Any, Dict, Optional
from pydantic import BaseModel


class WebhookResponse(BaseModel):
    status: str
    event: str
    action: Optional[str] = None
    detail: str
    data: Optional[Dict[str, Any]] = None
