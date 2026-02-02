"""Refund endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.refund import RefundRequest, RefundResponse
from agent_wallet_service.services.refunds import create_refund

router = APIRouter()


@router.post("", response_model=RefundResponse)
async def create_refund_endpoint(
    request: RefundRequest,
    api_key: APIKey = Depends(require_scope("refund:create")),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """Create a refund against a capture."""
    return await create_refund(
        db=db,
        api_key=api_key,
        capture_id=request.capture_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )
