"""Deposit service for loading funds into wallets.

In production, deposits would typically come from:
1. Bank transfers (ACH, wire)
2. Card payments (Stripe, Adyen)
3. Crypto on-ramps
4. Partner system credits

This service provides the internal mechanism to credit wallets
once external payment is confirmed.
"""

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import APIKey, JournalEntry, LedgerAccount, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryStatus, JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.services.ledger import (
    check_idempotency,
    create_journal_entry,
    get_or_create_ledger_accounts,
    lock_ledger_accounts,
)


# System wallet handle - this is the source for all deposits
SYSTEM_WALLET_HANDLE = "@system"


async def get_system_wallet(db: AsyncSession) -> Wallet:
    """Get the system wallet used as the source for deposits."""
    result = await db.execute(
        select(Wallet).where(Wallet.handle == SYSTEM_WALLET_HANDLE)
    )
    system_wallet = result.scalar_one_or_none()
    
    if system_wallet is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "SYSTEM_WALLET_NOT_FOUND",
                "message": "System wallet not configured. Run the seed script first.",
            },
        )
    
    return system_wallet


async def create_deposit(
    db: AsyncSession,
    api_key: APIKey,
    wallet_id: UUID,
    amount: str,
    currency: str,
    idempotency_key: str,
    external_reference: Optional[str] = None,
    payment_method: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a deposit to load funds into a wallet.
    
    This is an admin-only operation. In production, this would be called
    after confirming payment from an external source (Stripe webhook, 
    bank transfer confirmation, etc.)
    
    Args:
        db: Database session
        api_key: Admin API key making the request
        wallet_id: Target wallet to credit
        amount: Amount to deposit (as string, e.g., "100.00")
        currency: Currency code (e.g., "USD")
        idempotency_key: Unique key for idempotent operation
        external_reference: Reference from external payment system
        payment_method: How the deposit was funded (bank_transfer, card, etc.)
        metadata: Additional metadata
        
    Returns:
        Deposit result with journal entry details
    """
    amount_decimal = Decimal(amount)
    
    if amount_decimal <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )
    
    # Check for existing idempotent request
    existing_entry = await check_idempotency(db, idempotency_key, api_key.id)
    if existing_entry:
        return {
            "id": str(existing_entry.id),
            "journal_entry_id": str(existing_entry.id),
            "wallet_id": str(wallet_id),
            "amount": amount,
            "currency": currency,
            "status": "completed",
            "created_at": existing_entry.created_at,
        }
    
    # Get target wallet
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    target_wallet = result.scalar_one_or_none()
    
    if target_wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "WALLET_NOT_FOUND", "message": "Target wallet not found"},
        )
    
    if target_wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "WALLET_NOT_ACTIVE",
                "message": f"Wallet is {target_wallet.status.value}",
            },
        )
    
    if target_wallet.currency != currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "CURRENCY_MISMATCH",
                "message": f"Wallet currency is {target_wallet.currency}, not {currency}",
            },
        )
    
    # Get system wallet
    system_wallet = await get_system_wallet(db)
    
    # Get ledger accounts
    system_accounts = await get_or_create_ledger_accounts(db, system_wallet.id, currency)
    target_accounts = await get_or_create_ledger_accounts(db, wallet_id, currency)
    
    # Lock accounts
    await lock_ledger_accounts(db, [
        system_accounts[LedgerAccountKind.AVAILABLE].id,
        target_accounts[LedgerAccountKind.AVAILABLE].id,
    ])
    
    # Build metadata
    deposit_metadata = {
        "type": "deposit",
        "payment_method": payment_method or "external",
        "external_reference": external_reference,
        **(metadata or {}),
    }
    
    # Create journal entry (debit system, credit target)
    lines = [
        (
            system_accounts[LedgerAccountKind.AVAILABLE].id,
            JournalLineDirection.DEBIT,
            amount_decimal,
            currency,
        ),
        (
            target_accounts[LedgerAccountKind.AVAILABLE].id,
            JournalLineDirection.CREDIT,
            amount_decimal,
            currency,
        ),
    ]
    
    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.DEPOSIT_EXTERNAL,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
        reference_id=external_reference,
        metadata=deposit_metadata,
    )
    
    await db.commit()
    
    return {
        "id": str(entry.id),
        "journal_entry_id": str(entry.id),
        "wallet_id": str(wallet_id),
        "amount": amount,
        "currency": currency,
        "status": "completed",
        "external_reference": external_reference,
        "payment_method": payment_method,
        "created_at": entry.created_at,
    }


async def create_deposit_by_handle(
    db: AsyncSession,
    api_key: APIKey,
    handle: str,
    amount: str,
    currency: str,
    idempotency_key: str,
    external_reference: Optional[str] = None,
    payment_method: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a deposit using wallet handle instead of ID.
    
    Convenience method for depositing by handle (e.g., "@alice").
    """
    # Normalize handle
    if not handle.startswith("@"):
        handle = f"@{handle}"
    
    # Find wallet by handle
    result = await db.execute(select(Wallet).where(Wallet.handle == handle))
    wallet = result.scalar_one_or_none()
    
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "WALLET_NOT_FOUND", "message": f"Wallet {handle} not found"},
        )
    
    return await create_deposit(
        db=db,
        api_key=api_key,
        wallet_id=wallet.id,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        external_reference=external_reference,
        payment_method=payment_method,
        metadata=metadata,
    )
