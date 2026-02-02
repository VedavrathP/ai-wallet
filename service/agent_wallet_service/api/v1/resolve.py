"""Recipient resolution endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.common import RecipientInfo
from agent_wallet_service.services.recipient import resolve_recipient_by_type

router = APIRouter()


@router.get("", response_model=RecipientInfo)
async def resolve_recipient(
    type: str = Query(..., description="Type of recipient identifier: handle, wallet_id, external_id"),
    value: str = Query(..., description="Value of the identifier"),
    provider: str | None = Query(None, description="Provider for external_id type"),
    api_key: APIKey = Depends(require_scope("wallet:read")),
    db: AsyncSession = Depends(get_db),
) -> RecipientInfo:
    """Resolve a recipient to wallet information."""
    return await resolve_recipient_by_type(
        db=db,
        type=type,
        value=value,
        provider=provider,
    )
