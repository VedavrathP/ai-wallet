"""Payment intent-related schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PaymentIntentRequest(BaseModel):
    """Payment intent creation request body."""

    amount: str = Field(..., description="Amount for the payment intent (as string)")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    expires_in_seconds: int = Field(
        900,
        description="Expiration time in seconds (default: 15 minutes)",
        ge=60,
        le=86400,  # Max 24 hours
    )
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional metadata")


class PaymentIntentResponse(BaseModel):
    """Payment intent response."""

    id: str
    merchant_wallet_id: str
    amount: str
    currency: str
    status: str
    expires_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PayPaymentIntentRequest(BaseModel):
    """Pay payment intent request body."""

    idempotency_key: str = Field(..., description="Unique key for idempotent operation")


class PaymentResultResponse(BaseModel):
    """Payment result response."""

    payment_intent_id: str
    journal_entry_id: str
    payer_wallet_id: str
    merchant_wallet_id: str
    amount: str
    currency: str
    created_at: datetime
