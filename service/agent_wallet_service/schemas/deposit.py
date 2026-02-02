"""Deposit-related schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    """Deposit request body."""
    
    wallet_id: Optional[UUID] = Field(
        None,
        description="Target wallet ID (use this OR handle, not both)",
    )
    handle: Optional[str] = Field(
        None,
        description="Target wallet handle (e.g., '@alice')",
    )
    amount: str = Field(
        ...,
        description="Amount to deposit (as string, e.g., '100.00')",
    )
    currency: str = Field(
        ...,
        description="Currency code (e.g., 'USD')",
    )
    idempotency_key: str = Field(
        ...,
        description="Unique key for idempotent operation",
    )
    external_reference: Optional[str] = Field(
        None,
        description="Reference from external payment system (e.g., Stripe payment_intent ID)",
    )
    payment_method: Optional[str] = Field(
        None,
        description="How the deposit was funded (bank_transfer, card, crypto, etc.)",
    )
    metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Additional metadata",
    )


class DepositResponse(BaseModel):
    """Deposit response."""
    
    id: str
    journal_entry_id: str
    wallet_id: str
    amount: str
    currency: str
    status: str
    external_reference: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: datetime
