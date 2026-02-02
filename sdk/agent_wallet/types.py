"""Type definitions for the Agent Wallet SDK."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Wallet(BaseModel):
    """Wallet information."""

    id: str
    type: str  # customer, business, system
    status: str  # active, frozen, closed
    currency: str
    handle: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Balance(BaseModel):
    """Wallet balance information."""

    wallet_id: str
    available: str  # Decimal as string
    held: str  # Decimal as string
    total: str  # Decimal as string
    currency: str


class Transaction(BaseModel):
    """Transaction record."""

    id: str
    type: str  # transfer, hold, capture, release, refund, deposit_external
    status: str  # pending, posted, reversed, failed
    amount: str  # Decimal as string
    currency: str
    direction: str  # debit, credit
    counterparty_wallet_id: Optional[str] = None
    counterparty_handle: Optional[str] = None
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaginatedTransactions(BaseModel):
    """Paginated list of transactions."""

    items: list[Transaction]
    cursor: Optional[str] = None
    has_more: bool


class Transfer(BaseModel):
    """Transfer result."""

    id: str
    journal_entry_id: str
    from_wallet_id: str
    to_wallet_id: str
    amount: str
    currency: str
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Hold(BaseModel):
    """Hold/reservation result."""

    id: str
    wallet_id: str
    amount: str
    remaining_amount: str
    currency: str
    status: str  # active, captured, released, expired
    expires_at: datetime
    created_at: datetime


class Capture(BaseModel):
    """Capture result."""

    id: str
    hold_id: str
    to_wallet_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime


class Release(BaseModel):
    """Release result."""

    id: str
    hold_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime


class PaymentIntent(BaseModel):
    """Payment intent."""

    id: str
    merchant_wallet_id: str
    amount: str
    currency: str
    status: str  # requires_payment, paid, expired, cancelled
    expires_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaymentResult(BaseModel):
    """Result of paying a payment intent."""

    payment_intent_id: str
    journal_entry_id: str
    payer_wallet_id: str
    merchant_wallet_id: str
    amount: str
    currency: str
    created_at: datetime


class Refund(BaseModel):
    """Refund result."""

    id: str
    capture_id: str
    amount: str
    currency: str
    journal_entry_id: str
    created_at: datetime


class Deposit(BaseModel):
    """Deposit result (admin operation)."""

    id: str
    journal_entry_id: str
    wallet_id: str
    amount: str
    currency: str
    status: str  # completed
    external_reference: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: datetime


class RecipientInfo(BaseModel):
    """Resolved recipient information."""

    wallet_id: str
    handle: Optional[str] = None
    type: str


class ErrorResponse(BaseModel):
    """API error response."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
