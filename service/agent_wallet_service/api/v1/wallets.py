"""Wallet endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.middleware.auth import get_current_api_key, require_scope
from agent_wallet_service.models import APIKey
from agent_wallet_service.schemas.wallet import BalanceResponse, TransactionListResponse, WalletResponse
from agent_wallet_service.services.balance import get_wallet_balance
from agent_wallet_service.services.transactions import list_wallet_transactions

router = APIRouter()


@router.get("/me", response_model=WalletResponse)
async def get_current_wallet(
    api_key: APIKey = Depends(require_scope("wallet:read")),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    """Get the current wallet information."""
    from agent_wallet_service.models import Wallet
    from sqlalchemy import select

    result = await db.execute(select(Wallet).where(Wallet.id == api_key.wallet_id))
    wallet = result.scalar_one()

    return WalletResponse(
        id=str(wallet.id),
        type=wallet.type,
        status=wallet.status,
        currency=wallet.currency,
        handle=wallet.handle,
        metadata=wallet.metadata or {},
        created_at=wallet.created_at,
        updated_at=wallet.updated_at,
    )


@router.get("/me/balance", response_model=BalanceResponse)
async def get_balance(
    api_key: APIKey = Depends(require_scope("wallet:read")),
    db: AsyncSession = Depends(get_db),
) -> BalanceResponse:
    """Get the current wallet balance."""
    balance = await get_wallet_balance(db, api_key.wallet_id)
    return balance


@router.get("/me/transactions", response_model=TransactionListResponse)
async def get_transactions(
    cursor: str | None = None,
    limit: int = 50,
    type: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    api_key: APIKey = Depends(require_scope("wallet:read")),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    """List transactions for the current wallet."""
    return await list_wallet_transactions(
        db=db,
        wallet_id=api_key.wallet_id,
        cursor=cursor,
        limit=min(limit, 100),
        type_filter=type,
        status_filter=status,
        from_date=from_date,
        to_date=to_date,
    )
