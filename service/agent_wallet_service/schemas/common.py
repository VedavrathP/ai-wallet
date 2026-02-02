"""Common schemas used across the API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RecipientAddress(BaseModel):
    """Recipient address for transfers and captures."""

    type: str = Field(
        ...,
        description="Type of recipient identifier: wallet_id, handle, or external_id",
    )
    value: str | dict[str, Any] = Field(
        ...,
        description="Value of the identifier",
    )


class RecipientInfo(BaseModel):
    """Resolved recipient information."""

    wallet_id: str
    handle: Optional[str] = None
    type: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(BaseModel):
    """Base class for paginated responses."""

    cursor: Optional[str] = None
    has_more: bool = False
