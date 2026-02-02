"""Ledger engine for double-entry accounting operations."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.middleware.auth import enforce_limits
from agent_wallet_service.models import APIKey, JournalEntry, JournalLine, LedgerAccount, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryStatus, JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.schemas.common import RecipientAddress
from agent_wallet_service.schemas.transfer import TransferResponse
from agent_wallet_service.services.balance import get_ledger_account_balance
from agent_wallet_service.services.recipient import resolve_recipient


async def get_or_create_ledger_accounts(
    db: AsyncSession,
    wallet_id: UUID,
    currency: str,
) -> dict[LedgerAccountKind, LedgerAccount]:
    """Get or create ledger accounts for a wallet.

    Args:
        db: Database session
        wallet_id: ID of the wallet
        currency: Currency code

    Returns:
        Dictionary mapping account kind to LedgerAccount
    """
    result = await db.execute(
        select(LedgerAccount).where(LedgerAccount.wallet_id == wallet_id)
    )
    existing = {la.kind: la for la in result.scalars().all()}

    # Create missing accounts
    for kind in LedgerAccountKind:
        if kind not in existing:
            account = LedgerAccount(
                wallet_id=wallet_id,
                kind=kind,
                currency=currency,
            )
            db.add(account)
            existing[kind] = account

    await db.flush()
    return existing


async def lock_ledger_accounts(
    db: AsyncSession,
    account_ids: list[UUID],
) -> dict[UUID, LedgerAccount]:
    """Lock ledger accounts using SELECT FOR UPDATE.

    This prevents concurrent modifications to the same accounts.

    Args:
        db: Database session
        account_ids: List of ledger account IDs to lock

    Returns:
        Dictionary mapping account ID to LedgerAccount
    """
    # Sort IDs to prevent deadlocks
    sorted_ids = sorted(account_ids)

    result = await db.execute(
        select(LedgerAccount)
        .where(LedgerAccount.id.in_(sorted_ids))
        .with_for_update()
    )
    accounts = {la.id: la for la in result.scalars().all()}

    return accounts


async def check_idempotency(
    db: AsyncSession,
    idempotency_key: str,
    api_key_id: UUID,
) -> Optional[JournalEntry]:
    """Check if a journal entry with this idempotency key already exists.

    Args:
        db: Database session
        idempotency_key: Idempotency key
        api_key_id: API key ID

    Returns:
        Existing JournalEntry if found, None otherwise
    """
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.idempotency_key == idempotency_key,
            JournalEntry.created_by_api_key_id == api_key_id,
        )
    )
    return result.scalar_one_or_none()


async def create_journal_entry(
    db: AsyncSession,
    entry_type: JournalEntryType,
    api_key_id: UUID,
    idempotency_key: str,
    lines: list[tuple[UUID, JournalLineDirection, Decimal, str]],
    reference_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> JournalEntry:
    """Create a journal entry with balanced lines.

    Args:
        db: Database session
        entry_type: Type of journal entry
        api_key_id: ID of the API key creating the entry
        idempotency_key: Idempotency key
        lines: List of (ledger_account_id, direction, amount, currency) tuples
        reference_id: Optional reference ID
        metadata: Optional metadata

    Returns:
        Created JournalEntry

    Raises:
        ValueError: If debits don't equal credits
    """
    # Validate that debits equal credits
    total_debits = sum(
        amount for _, direction, amount, _ in lines
        if direction == JournalLineDirection.DEBIT
    )
    total_credits = sum(
        amount for _, direction, amount, _ in lines
        if direction == JournalLineDirection.CREDIT
    )

    if total_debits != total_credits:
        raise ValueError(
            f"Journal entry is unbalanced: debits={total_debits}, credits={total_credits}"
        )

    # Create journal entry
    entry = JournalEntry(
        type=entry_type,
        status=JournalEntryStatus.POSTED,
        idempotency_key=idempotency_key,
        reference_id=reference_id,
        created_by_api_key_id=api_key_id,
        entry_metadata=metadata or {},
    )
    db.add(entry)
    await db.flush()

    # Create journal lines
    for ledger_account_id, direction, amount, currency in lines:
        line = JournalLine(
            journal_entry_id=entry.id,
            ledger_account_id=ledger_account_id,
            direction=direction,
            amount=amount,
            currency=currency,
        )
        db.add(line)

    await db.flush()
    return entry


async def create_transfer(
    db: AsyncSession,
    api_key: APIKey,
    from_wallet_id: UUID,
    to_recipient: RecipientAddress,
    amount: str,
    currency: str,
    idempotency_key: str,
    reference_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> TransferResponse:
    """Create a transfer between wallets.

    Args:
        db: Database session
        api_key: API key making the request
        from_wallet_id: Source wallet ID
        to_recipient: Recipient address
        amount: Amount to transfer (as string)
        currency: Currency code
        idempotency_key: Idempotency key
        reference_id: Optional reference ID
        metadata: Optional metadata

    Returns:
        TransferResponse

    Raises:
        HTTPException: If transfer fails
    """
    amount_decimal = Decimal(amount)

    if amount_decimal <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_AMOUNT",
                "message": "Amount must be positive",
            },
        )

    # Check for existing idempotent request
    existing_entry = await check_idempotency(db, idempotency_key, api_key.id)
    if existing_entry:
        # Return the existing transfer result
        return await _build_transfer_response(db, existing_entry, from_wallet_id)

    # Resolve recipient
    to_wallet_id, to_handle = await resolve_recipient(db, to_recipient)

    # Prevent self-transfer
    if from_wallet_id == to_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "SELF_TRANSFER",
                "message": "Cannot transfer to the same wallet",
            },
        )

    # Check source wallet status
    result = await db.execute(select(Wallet).where(Wallet.id == from_wallet_id))
    from_wallet = result.scalar_one()

    if from_wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "WALLET_NOT_ACTIVE",
                "message": f"Source wallet is {from_wallet.status.value}",
            },
        )

    # Check currency match
    if from_wallet.currency != currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "CURRENCY_MISMATCH",
                "message": f"Wallet currency is {from_wallet.currency}, not {currency}",
            },
        )

    # Check destination wallet currency
    result = await db.execute(select(Wallet).where(Wallet.id == to_wallet_id))
    to_wallet = result.scalar_one()

    if to_wallet.currency != currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "CURRENCY_MISMATCH",
                "message": f"Recipient wallet currency is {to_wallet.currency}, not {currency}",
            },
        )

    # Enforce limits
    await enforce_limits(db, api_key, amount_decimal, to_wallet_id, to_handle)

    # Get or create ledger accounts
    from_accounts = await get_or_create_ledger_accounts(db, from_wallet_id, currency)
    to_accounts = await get_or_create_ledger_accounts(db, to_wallet_id, currency)

    # Lock accounts to prevent concurrent modifications
    account_ids = [
        from_accounts[LedgerAccountKind.AVAILABLE].id,
        to_accounts[LedgerAccountKind.AVAILABLE].id,
    ]
    await lock_ledger_accounts(db, account_ids)

    # Check sufficient balance
    from_available = await get_ledger_account_balance(
        db, from_accounts[LedgerAccountKind.AVAILABLE].id
    )

    if from_available < amount_decimal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INSUFFICIENT_FUNDS",
                "message": f"Insufficient funds. Available: {from_available}, Required: {amount_decimal}",
                "details": {
                    "available": str(from_available),
                    "required": str(amount_decimal),
                },
            },
        )

    # Create journal entry
    lines = [
        (from_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.DEBIT, amount_decimal, currency),
        (to_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.CREDIT, amount_decimal, currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.TRANSFER,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
        reference_id=reference_id,
        metadata=metadata,
    )

    await db.commit()

    return TransferResponse(
        id=str(entry.id),
        journal_entry_id=str(entry.id),
        from_wallet_id=str(from_wallet_id),
        to_wallet_id=str(to_wallet_id),
        amount=amount,
        currency=currency,
        reference_id=reference_id,
        metadata=metadata or {},
        created_at=entry.created_at,
    )


async def _build_transfer_response(
    db: AsyncSession,
    entry: JournalEntry,
    from_wallet_id: UUID,
) -> TransferResponse:
    """Build a TransferResponse from an existing journal entry."""
    # Get the journal lines to find the to_wallet_id
    result = await db.execute(
        select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
    )
    lines = result.scalars().all()

    # Find the credit line (destination)
    credit_line = next(
        (l for l in lines if l.direction == JournalLineDirection.CREDIT),
        None
    )

    if credit_line is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "message": "Invalid journal entry"},
        )

    # Get the destination wallet ID from the ledger account
    result = await db.execute(
        select(LedgerAccount).where(LedgerAccount.id == credit_line.ledger_account_id)
    )
    to_account = result.scalar_one()

    return TransferResponse(
        id=str(entry.id),
        journal_entry_id=str(entry.id),
        from_wallet_id=str(from_wallet_id),
        to_wallet_id=str(to_account.wallet_id),
        amount=str(credit_line.amount),
        currency=credit_line.currency,
        reference_id=entry.reference_id,
        metadata=entry.entry_metadata or {},
        created_at=entry.created_at,
    )
