"""Admin endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.admin import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    CreateWalletRequest,
    FreezeWalletRequest,
    WalletResponse,
)
from agent_wallet_service.schemas.deposit import DepositRequest, DepositResponse
from agent_wallet_service.services.admin import (
    admin_create_api_key,
    admin_create_wallet,
    admin_freeze_wallet,
    admin_revoke_api_key,
)
from agent_wallet_service.services.deposits import create_deposit, create_deposit_by_handle

router = APIRouter()


@router.post("/wallets", response_model=WalletResponse)
async def create_wallet(
    request: CreateWalletRequest,
    api_key: APIKey = Depends(require_scope("admin:wallets")),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    """Create a new wallet (admin only)."""
    return await admin_create_wallet(
        db=db,
        type=request.type,
        currency=request.currency,
        handle=request.handle,
        metadata=request.metadata,
    )


@router.post("/api_keys", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    api_key: APIKey = Depends(require_scope("admin:api_keys")),
    db: AsyncSession = Depends(get_db),
) -> CreateAPIKeyResponse:
    """Create a new API key (admin only)."""
    return await admin_create_api_key(
        db=db,
        wallet_id=request.wallet_id,
        scopes=request.scopes,
        limits=request.limits,
    )


@router.post("/api_keys/{key_id}/revoke")
async def revoke_api_key(
    key_id: UUID,
    api_key: APIKey = Depends(require_scope("admin:api_keys")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Revoke an API key (admin only)."""
    await admin_revoke_api_key(db=db, key_id=key_id)
    return {"status": "revoked"}


@router.post("/wallets/{wallet_id}/freeze")
async def freeze_wallet(
    wallet_id: UUID,
    request: FreezeWalletRequest,
    api_key: APIKey = Depends(require_scope("admin:wallets")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Freeze or unfreeze a wallet (admin only)."""
    await admin_freeze_wallet(db=db, wallet_id=wallet_id, freeze=request.freeze)
    return {"status": "frozen" if request.freeze else "active"}


@router.post("/deposits", response_model=DepositResponse)
async def deposit_funds(
    request: DepositRequest,
    api_key: APIKey = Depends(require_scope("admin:deposits")),
    db: AsyncSession = Depends(get_db),
) -> DepositResponse:
    """Load funds into a wallet (admin only).
    
    This endpoint is used to credit a wallet after confirming payment
    from an external source (e.g., Stripe webhook, bank transfer confirmation).
    
    You must provide either `wallet_id` OR `handle`, not both.
    
    Example:
        POST /admin/deposits
        {
            "handle": "@alice",
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "stripe_pi_abc123",
            "external_reference": "pi_abc123",
            "payment_method": "card"
        }
    """
    # Validate that exactly one of wallet_id or handle is provided
    if request.wallet_id is None and request.handle is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_REQUEST",
                "message": "Must provide either wallet_id or handle",
            },
        )
    
    if request.wallet_id is not None and request.handle is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_REQUEST",
                "message": "Provide wallet_id OR handle, not both",
            },
        )
    
    if request.handle:
        result = await create_deposit_by_handle(
            db=db,
            api_key=api_key,
            handle=request.handle,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
            external_reference=request.external_reference,
            payment_method=request.payment_method,
            metadata=request.metadata,
        )
    else:
        result = await create_deposit(
            db=db,
            api_key=api_key,
            wallet_id=request.wallet_id,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
            external_reference=request.external_reference,
            payment_method=request.payment_method,
            metadata=request.metadata,
        )
    
    return DepositResponse(**result)
