"""Recipient resolution service."""

from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import ExternalIdentity, Wallet
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.schemas.common import RecipientAddress, RecipientInfo


async def resolve_recipient(
    db: AsyncSession,
    recipient: RecipientAddress,
) -> tuple[UUID, Optional[str]]:
    """Resolve a recipient address to a wallet ID and handle.

    Args:
        db: Database session
        recipient: Recipient address containing type and value

    Returns:
        Tuple of (wallet_id, handle)

    Raises:
        HTTPException: If recipient cannot be resolved
    """
    if recipient.type == "wallet_id":
        return await _resolve_by_wallet_id(db, recipient.value)
    elif recipient.type == "handle":
        return await _resolve_by_handle(db, recipient.value)
    elif recipient.type == "external_id":
        return await _resolve_by_external_id(db, recipient.value)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_RECIPIENT_TYPE",
                "message": f"Invalid recipient type: {recipient.type}",
            },
        )


async def _resolve_by_wallet_id(
    db: AsyncSession,
    value: str | dict[str, Any],
) -> tuple[UUID, Optional[str]]:
    """Resolve recipient by wallet ID."""
    try:
        wallet_id = UUID(str(value))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_WALLET_ID",
                "message": "Invalid wallet ID format",
            },
        )

    result = await db.execute(
        select(Wallet).where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "RECIPIENT_NOT_FOUND",
                "message": "Wallet not found",
            },
        )

    _check_wallet_status(wallet)
    return wallet.id, wallet.handle


async def _resolve_by_handle(
    db: AsyncSession,
    value: str | dict[str, Any],
) -> tuple[UUID, Optional[str]]:
    """Resolve recipient by handle."""
    handle = str(value)

    # Normalize handle (ensure it starts with @)
    if not handle.startswith("@"):
        handle = f"@{handle}"

    result = await db.execute(
        select(Wallet).where(Wallet.handle == handle)
    )
    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "RECIPIENT_NOT_FOUND",
                "message": f"Wallet with handle {handle} not found",
            },
        )

    _check_wallet_status(wallet)
    return wallet.id, wallet.handle


async def _resolve_by_external_id(
    db: AsyncSession,
    value: str | dict[str, Any],
) -> tuple[UUID, Optional[str]]:
    """Resolve recipient by external ID."""
    if isinstance(value, dict):
        provider = value.get("provider")
        external_user_id = value.get("external_user_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_EXTERNAL_ID",
                "message": "External ID must include provider and external_user_id",
            },
        )

    if not provider or not external_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_EXTERNAL_ID",
                "message": "External ID must include provider and external_user_id",
            },
        )

    result = await db.execute(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == provider,
            ExternalIdentity.external_user_id == external_user_id,
        )
    )
    external_identity = result.scalar_one_or_none()

    if external_identity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "RECIPIENT_NOT_FOUND",
                "message": f"No wallet found for provider={provider}, external_user_id={external_user_id}",
            },
        )

    # Get the wallet
    result = await db.execute(
        select(Wallet).where(Wallet.id == external_identity.wallet_id)
    )
    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "RECIPIENT_NOT_FOUND",
                "message": "Wallet not found",
            },
        )

    _check_wallet_status(wallet)
    return wallet.id, wallet.handle


def _check_wallet_status(wallet: Wallet) -> None:
    """Check if wallet status allows receiving funds."""
    if wallet.status == WalletStatus.FROZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "WALLET_FROZEN",
                "message": "Recipient wallet is frozen",
            },
        )
    elif wallet.status == WalletStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "WALLET_CLOSED",
                "message": "Recipient wallet is closed",
            },
        )


async def resolve_recipient_by_type(
    db: AsyncSession,
    type: str,
    value: str,
    provider: Optional[str] = None,
) -> RecipientInfo:
    """Resolve a recipient by type and value (for the /resolve endpoint).

    Args:
        db: Database session
        type: Type of identifier (handle, wallet_id, external_id)
        value: Value of the identifier
        provider: Provider for external_id type

    Returns:
        RecipientInfo with resolved wallet information
    """
    if type == "external_id":
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "MISSING_PROVIDER",
                    "message": "Provider is required for external_id type",
                },
            )
        recipient = RecipientAddress(
            type="external_id",
            value={"provider": provider, "external_user_id": value},
        )
    else:
        recipient = RecipientAddress(type=type, value=value)

    wallet_id, handle = await resolve_recipient(db, recipient)

    # Get wallet type
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one()

    return RecipientInfo(
        wallet_id=str(wallet_id),
        handle=handle,
        type=wallet.type.value,
    )
