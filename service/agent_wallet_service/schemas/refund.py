"""Refund-related schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RefundRequest(BaseModel):
    """Refund request body."""

    capture_id: UUID = Field(..., description="ID of the capture to refund")
    idempotency_key: str = Field(..., description="Unique key for idempotent operation")
    amount: Optional[str] = Field(
        None,
        description="Amount to refund (optional, defaults to full capture amount)",
    )


class RefundResponse(BaseModel):
    """Refund response."""

    id: str
    capture_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime
