"""Admin service for wallet and API key management."""

import secrets
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.core.config import settings
from agent_wallet_service.middleware.auth import hash_api_key
from agent_wallet_service.models import APIKey, LedgerAccount, Wallet
from agent_wallet_service.models.api_key import APIKeyStatus
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus, WalletType
from agent_wallet_service.schemas.admin import CreateAPIKeyResponse, WalletResponse


def generate_api_key() -> str:
    """Generate a new API key."""
    random_part = secrets.token_urlsafe(32)
    return f"{settings.API_KEY_PREFIX}{random_part}"


async def admin_create_wallet(
    db: AsyncSession,
    type: str,
    currency: str,
    handle: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> WalletResponse:
    """Create a new wallet.

    Args:
        db: Database session
        type: Wallet type (customer, business, system)
        currency: Currency code
        handle: Optional unique handle
        metadata: Optional metadata

    Returns:
        WalletResponse
    """
    # Validate type
    try:
        wallet_type = WalletType(type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_WALLET_TYPE", "message": f"Invalid wallet type: {type}"},
        )

    # Check handle uniqueness
    if handle:
        # Normalize handle
        if not handle.startswith("@"):
            handle = f"@{handle}"

        result = await db.execute(select(Wallet).where(Wallet.handle == handle))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "HANDLE_EXISTS", "message": f"Handle {handle} already exists"},
            )

    # Create wallet
    wallet = Wallet(
        type=wallet_type,
        status=WalletStatus.ACTIVE,
        currency=currency.upper(),
        handle=handle,
        metadata=metadata or {},
    )
    db.add(wallet)
    await db.flush()

    # Create ledger accounts
    for kind in LedgerAccountKind:
        account = LedgerAccount(
            wallet_id=wallet.id,
            kind=kind,
            currency=currency.upper(),
        )
        db.add(account)

    await db.commit()

    return WalletResponse(
        id=str(wallet.id),
        type=wallet.type.value,
        status=wallet.status.value,
        currency=wallet.currency,
        handle=wallet.handle,
        metadata=wallet.metadata or {},
        created_at=wallet.created_at,
        updated_at=wallet.updated_at,
    )


async def admin_create_api_key(
    db: AsyncSession,
    wallet_id: UUID,
    scopes: list[str],
    limits: Optional[dict[str, Any]] = None,
) -> CreateAPIKeyResponse:
    """Create a new API key.

    Args:
        db: Database session
        wallet_id: Wallet ID to associate with the key
        scopes: List of scopes
        limits: Optional limits

    Returns:
        CreateAPIKeyResponse with the raw API key (only shown once)
    """
    # Check wallet exists
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "WALLET_NOT_FOUND", "message": "Wallet not found"},
        )

    # Generate API key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    # Create API key record
    api_key = APIKey(
        key_hash=key_hash,
        wallet_id=wallet_id,
        scopes=scopes,
        limits=limits or {},
        status=APIKeyStatus.ACTIVE,
    )
    db.add(api_key)
    await db.commit()

    return CreateAPIKeyResponse(
        id=str(api_key.id),
        api_key=raw_key,
        wallet_id=str(api_key.wallet_id),
        scopes=api_key.scopes,
        limits=api_key.limits,
        created_at=api_key.created_at,
    )


async def admin_revoke_api_key(
    db: AsyncSession,
    key_id: UUID,
) -> None:
    """Revoke an API key.

    Args:
        db: Database session
        key_id: API key ID to revoke
    """
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "API_KEY_NOT_FOUND", "message": "API key not found"},
        )

    api_key.status = APIKeyStatus.REVOKED
    await db.commit()


async def admin_freeze_wallet(
    db: AsyncSession,
    wallet_id: UUID,
    freeze: bool,
) -> None:
    """Freeze or unfreeze a wallet.

    Args:
        db: Database session
        wallet_id: Wallet ID
        freeze: True to freeze, False to unfreeze
    """
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "WALLET_NOT_FOUND", "message": "Wallet not found"},
        )

    if wallet.status == WalletStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "WALLET_CLOSED", "message": "Cannot modify a closed wallet"},
        )

    wallet.status = WalletStatus.FROZEN if freeze else WalletStatus.ACTIVE
    await db.commit()
