"""Hold endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.hold import (
    CaptureRequest,
    CaptureResponse,
    HoldRequest,
    HoldResponse,
    ReleaseRequest,
    ReleaseResponse,
)
from agent_wallet_service.services.holds import capture_hold, create_hold, release_hold

router = APIRouter()


@router.post("", response_model=HoldResponse)
async def create_hold_endpoint(
    request: HoldRequest,
    api_key: APIKey = Depends(require_scope("hold:create")),
    db: AsyncSession = Depends(get_db),
) -> HoldResponse:
    """Create a hold (reservation) on the wallet."""
    return await create_hold(
        db=db,
        api_key=api_key,
        wallet_id=api_key.wallet_id,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=request.idempotency_key,
        expires_in_seconds=request.expires_in_seconds,
        metadata=request.metadata,
    )


@router.post("/{hold_id}/capture", response_model=CaptureResponse)
async def capture_hold_endpoint(
    hold_id: UUID,
    request: CaptureRequest,
    api_key: APIKey = Depends(require_scope("hold:capture")),
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    """Capture a hold (partial or full)."""
    return await capture_hold(
        db=db,
        api_key=api_key,
        hold_id=hold_id,
        to_recipient=request.to,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{hold_id}/release", response_model=ReleaseResponse)
async def release_hold_endpoint(
    hold_id: UUID,
    request: ReleaseRequest,
    api_key: APIKey = Depends(require_scope("hold:release")),
    db: AsyncSession = Depends(get_db),
) -> ReleaseResponse:
    """Release a hold (partial or full)."""
    return await release_hold(
        db=db,
        api_key=api_key,
        hold_id=hold_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )
