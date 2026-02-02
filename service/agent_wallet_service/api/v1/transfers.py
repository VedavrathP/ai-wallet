"""Transfer endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.transfer import TransferRequest, TransferResponse
from agent_wallet_service.services.ledger import create_transfer

router = APIRouter()


@router.post("", response_model=TransferResponse)
async def transfer_funds(
    request: TransferRequest,
    api_key: APIKey = Depends(require_scope("transfer:create")),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """Transfer funds to another wallet."""
    return await create_transfer(
        db=db,
        api_key=api_key,
        from_wallet_id=api_key.wallet_id,
        to_recipient=request.to,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=request.idempotency_key,
        reference_id=request.reference_id,
        metadata=request.metadata,
    )
