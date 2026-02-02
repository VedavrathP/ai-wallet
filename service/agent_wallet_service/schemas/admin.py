"""Admin-related schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateWalletRequest(BaseModel):
    """Create wallet request body."""

    type: str = Field(..., description="Wallet type: customer, business, or system")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    handle: Optional[str] = Field(None, description="Optional unique handle (e.g., '@alice')")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional metadata")


class WalletResponse(BaseModel):
    """Wallet response."""

    id: str
    type: str
    status: str
    currency: str
    handle: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreateAPIKeyRequest(BaseModel):
    """Create API key request body."""

    wallet_id: UUID = Field(..., description="Wallet ID to associate with the key")
    scopes: list[str] = Field(..., description="List of scopes for the key")
    limits: Optional[dict[str, Any]] = Field(
        None,
        description="Optional limits (per_tx_max, daily_max, allowed_counterparties)",
    )


class CreateAPIKeyResponse(BaseModel):
    """Create API key response."""

    id: str
    api_key: str = Field(..., description="The raw API key (only shown once)")
    wallet_id: str
    scopes: list[str]
    limits: Optional[dict[str, Any]] = None
    created_at: datetime


class FreezeWalletRequest(BaseModel):
    """Freeze/unfreeze wallet request body."""

    freeze: bool = Field(..., description="True to freeze, False to unfreeze")
