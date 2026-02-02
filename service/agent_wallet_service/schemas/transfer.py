"""Transfer-related schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from agent_wallet_service.schemas.common import RecipientAddress


class TransferRequest(BaseModel):
    """Transfer request body."""

    amount: str = Field(..., description="Amount to transfer (as string, e.g., '12.50')")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    to: RecipientAddress = Field(..., description="Recipient address")
    idempotency_key: str = Field(..., description="Unique key for idempotent operation")
    reference_id: Optional[str] = Field(None, description="Optional reference ID")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional metadata")


class TransferResponse(BaseModel):
    """Transfer response."""

    id: str
    journal_entry_id: str
    from_wallet_id: str
    to_wallet_id: str
    amount: str
    currency: str
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
