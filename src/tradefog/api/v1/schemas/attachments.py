"""Transport models for private trade attachments."""

from datetime import datetime

from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    """Safe attachment metadata without exposing its storage key."""

    id: int
    trade_id: int
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    content_url: str
