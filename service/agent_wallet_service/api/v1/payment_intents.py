"""Payment intent endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.payment_intent import (
    PaymentIntentRequest,
    PaymentIntentResponse,
    PayPaymentIntentRequest,
    PaymentResultResponse,
)
from agent_wallet_service.services.payment_intents import create_payment_intent, pay_payment_intent

router = APIRouter()


@router.post("", response_model=PaymentIntentResponse)
async def create_payment_intent_endpoint(
    request: PaymentIntentRequest,
    api_key: APIKey = Depends(require_scope("payment_intent:create")),
    db: AsyncSession = Depends(get_db),
) -> PaymentIntentResponse:
    """Create a payment intent (merchant operation)."""
    return await create_payment_intent(
        db=db,
        api_key=api_key,
        merchant_wallet_id=api_key.wallet_id,
        amount=request.amount,
        currency=request.currency,
        expires_in_seconds=request.expires_in_seconds,
        metadata=request.metadata,
    )


@router.post("/{intent_id}/pay", response_model=PaymentResultResponse)
async def pay_payment_intent_endpoint(
    intent_id: UUID,
    request: PayPaymentIntentRequest,
    api_key: APIKey = Depends(require_scope("payment_intent:pay")),
    db: AsyncSession = Depends(get_db),
) -> PaymentResultResponse:
    """Pay a payment intent."""
    return await pay_payment_intent(
        db=db,
        api_key=api_key,
        payer_wallet_id=api_key.wallet_id,
        intent_id=intent_id,
        idempotency_key=request.idempotency_key,
    )
