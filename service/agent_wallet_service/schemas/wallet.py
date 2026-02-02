"""Wallet-related schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    """Wallet information response."""

    id: str
    type: str
    status: str
    currency: str
    handle: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class BalanceResponse(BaseModel):
    """Wallet balance response."""

    wallet_id: str
    available: str  # Decimal as string
    held: str  # Decimal as string
    total: str  # Decimal as string
    currency: str


class TransactionResponse(BaseModel):
    """Transaction record response."""

    id: str
    type: str
    status: str
    amount: str
    currency: str
    direction: str
    counterparty_wallet_id: Optional[str] = None
    counterparty_handle: Optional[str] = None
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    items: list[TransactionResponse]
    cursor: Optional[str] = None
    has_more: bool = False
