"""Hold-related schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from agent_wallet_service.schemas.common import RecipientAddress


class HoldRequest(BaseModel):
    """Hold creation request body."""

    amount: str = Field(..., description="Amount to hold (as string, e.g., '50.00')")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    idempotency_key: str = Field(..., description="Unique key for idempotent operation")
    expires_in_seconds: int = Field(
        3600,
        description="Hold expiration time in seconds (default: 1 hour)",
        ge=60,
        le=604800,  # Max 7 days
    )
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional metadata")


class HoldResponse(BaseModel):
    """Hold response."""

    id: str
    wallet_id: str
    amount: str
    remaining_amount: str
    currency: str
    status: str
    expires_at: datetime
    created_at: datetime


class CaptureRequest(BaseModel):
    """Capture request body."""

    to: RecipientAddress = Field(..., description="Recipient address")
    idempotency_key: str = Field(..., description="Unique key for idempotent operation")
    amount: Optional[str] = Field(
        None,
        description="Amount to capture (optional, defaults to remaining hold amount)",
    )


class CaptureResponse(BaseModel):
    """Capture response."""

    id: str
    hold_id: str
    to_wallet_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime


class ReleaseRequest(BaseModel):
    """Release request body."""

    idempotency_key: str = Field(..., description="Unique key for idempotent operation")
    amount: Optional[str] = Field(
        None,
        description="Amount to release (optional, defaults to remaining hold amount)",
    )


class ReleaseResponse(BaseModel):
    """Release response."""

    id: str
    hold_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime
