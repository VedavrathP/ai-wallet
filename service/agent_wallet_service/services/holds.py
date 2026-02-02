"""Hold service for creating, capturing, and releasing holds."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.middleware.auth import enforce_limits
from agent_wallet_service.models import APIKey, Hold, Wallet
from agent_wallet_service.models.capture import Capture
from agent_wallet_service.models.hold import HoldStatus
from agent_wallet_service.models.journal_entry import JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.schemas.common import RecipientAddress
from agent_wallet_service.schemas.hold import CaptureResponse, HoldResponse, ReleaseResponse
from agent_wallet_service.services.balance import get_ledger_account_balance
from agent_wallet_service.services.ledger import (
    check_idempotency,
    create_journal_entry,
    get_or_create_ledger_accounts,
    lock_ledger_accounts,
)
from agent_wallet_service.services.recipient import resolve_recipient


async def create_hold(
    db: AsyncSession,
    api_key: APIKey,
    wallet_id: UUID,
    amount: str,
    currency: str,
    idempotency_key: str,
    expires_in_seconds: int = 3600,
    metadata: Optional[dict] = None,
) -> HoldResponse:
    """Create a hold (reservation) on a wallet.

    Args:
        db: Database session
        api_key: API key making the request
        wallet_id: Wallet ID to hold funds from
        amount: Amount to hold
        currency: Currency code
        idempotency_key: Idempotency key
        expires_in_seconds: Hold expiration time
        metadata: Optional metadata

    Returns:
        HoldResponse
    """
    amount_decimal = Decimal(amount)

    if amount_decimal <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )

    # Check for existing idempotent request
    result = await db.execute(
        select(Hold).where(
            Hold.idempotency_key == idempotency_key,
            Hold.created_by_api_key_id == api_key.id,
        )
    )
    existing_hold = result.scalar_one_or_none()
    if existing_hold:
        return HoldResponse(
            id=str(existing_hold.id),
            wallet_id=str(existing_hold.wallet_id),
            amount=str(existing_hold.amount),
            remaining_amount=str(existing_hold.remaining_amount),
            currency=existing_hold.currency,
            status=existing_hold.status.value,
            expires_at=existing_hold.expires_at,
            created_at=existing_hold.created_at,
        )

    # Check wallet status
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one()

    if wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "WALLET_NOT_ACTIVE", "message": f"Wallet is {wallet.status.value}"},
        )

    if wallet.currency != currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CURRENCY_MISMATCH", "message": f"Wallet currency is {wallet.currency}"},
        )

    # Enforce limits
    await enforce_limits(db, api_key, amount_decimal)

    # Get ledger accounts
    accounts = await get_or_create_ledger_accounts(db, wallet_id, currency)

    # Lock accounts
    await lock_ledger_accounts(db, [accounts[LedgerAccountKind.AVAILABLE].id, accounts[LedgerAccountKind.HELD].id])

    # Check sufficient balance
    available = await get_ledger_account_balance(db, accounts[LedgerAccountKind.AVAILABLE].id)

    if available < amount_decimal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INSUFFICIENT_FUNDS",
                "message": f"Insufficient funds. Available: {available}, Required: {amount_decimal}",
            },
        )

    # Create journal entry (debit available, credit held)
    lines = [
        (accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.DEBIT, amount_decimal, currency),
        (accounts[LedgerAccountKind.HELD].id, JournalLineDirection.CREDIT, amount_decimal, currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.HOLD,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
        metadata=metadata,
    )

    # Create hold record
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    hold = Hold(
        wallet_id=wallet_id,
        amount=amount_decimal,
        remaining_amount=amount_decimal,
        currency=currency,
        status=HoldStatus.ACTIVE,
        expires_at=expires_at,
        created_by_api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        journal_entry_id=entry.id,
    )
    db.add(hold)
    await db.commit()

    return HoldResponse(
        id=str(hold.id),
        wallet_id=str(hold.wallet_id),
        amount=str(hold.amount),
        remaining_amount=str(hold.remaining_amount),
        currency=hold.currency,
        status=hold.status.value,
        expires_at=hold.expires_at,
        created_at=hold.created_at,
    )


async def capture_hold(
    db: AsyncSession,
    api_key: APIKey,
    hold_id: UUID,
    to_recipient: RecipientAddress,
    amount: Optional[str],
    idempotency_key: str,
) -> CaptureResponse:
    """Capture a hold (transfer held funds to recipient).

    Args:
        db: Database session
        api_key: API key making the request
        hold_id: ID of the hold to capture
        to_recipient: Recipient address
        amount: Amount to capture (optional, defaults to remaining)
        idempotency_key: Idempotency key

    Returns:
        CaptureResponse
    """
    # Check for existing idempotent capture
    result = await db.execute(
        select(Capture).where(Capture.idempotency_key == idempotency_key)
    )
    existing_capture = result.scalar_one_or_none()
    if existing_capture:
        return CaptureResponse(
            id=str(existing_capture.id),
            hold_id=str(existing_capture.hold_id),
            to_wallet_id=str(existing_capture.to_wallet_id),
            amount=str(existing_capture.amount),
            currency=existing_capture.currency,
            journal_entry_id=str(existing_capture.journal_entry_id),
            created_at=existing_capture.created_at,
        )

    # Get hold
    result = await db.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one_or_none()

    if hold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "HOLD_NOT_FOUND", "message": "Hold not found"},
        )

    # Check hold belongs to API key's wallet
    if hold.wallet_id != api_key.wallet_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "FORBIDDEN", "message": "Hold does not belong to this wallet"},
        )

    if not hold.can_capture:
        if hold.is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "HOLD_EXPIRED", "message": "Hold has expired"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "HOLD_NOT_CAPTURABLE", "message": f"Hold status is {hold.status.value}"},
        )

    # Determine capture amount
    capture_amount = Decimal(amount) if amount else hold.remaining_amount

    if capture_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )

    if capture_amount > hold.remaining_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "AMOUNT_EXCEEDS_HOLD",
                "message": f"Amount {capture_amount} exceeds remaining hold {hold.remaining_amount}",
            },
        )

    # Resolve recipient
    to_wallet_id, to_handle = await resolve_recipient(db, to_recipient)

    # Check recipient wallet currency
    result = await db.execute(select(Wallet).where(Wallet.id == to_wallet_id))
    to_wallet = result.scalar_one()

    if to_wallet.currency != hold.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CURRENCY_MISMATCH", "message": f"Recipient currency is {to_wallet.currency}"},
        )

    # Enforce counterparty allowlist
    await enforce_limits(db, api_key, capture_amount, to_wallet_id, to_handle)

    # Get ledger accounts
    from_accounts = await get_or_create_ledger_accounts(db, hold.wallet_id, hold.currency)
    to_accounts = await get_or_create_ledger_accounts(db, to_wallet_id, hold.currency)

    # Lock accounts
    await lock_ledger_accounts(db, [
        from_accounts[LedgerAccountKind.HELD].id,
        to_accounts[LedgerAccountKind.AVAILABLE].id,
    ])

    # Create journal entry (debit held, credit recipient available)
    lines = [
        (from_accounts[LedgerAccountKind.HELD].id, JournalLineDirection.DEBIT, capture_amount, hold.currency),
        (to_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.CREDIT, capture_amount, hold.currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.CAPTURE,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
    )

    # Update hold
    hold.remaining_amount -= capture_amount
    if hold.remaining_amount == 0:
        hold.status = HoldStatus.CAPTURED

    # Create capture record
    capture = Capture(
        hold_id=hold.id,
        to_wallet_id=to_wallet_id,
        amount=capture_amount,
        currency=hold.currency,
        journal_entry_id=entry.id,
        idempotency_key=idempotency_key,
    )
    db.add(capture)
    await db.commit()

    return CaptureResponse(
        id=str(capture.id),
        hold_id=str(capture.hold_id),
        to_wallet_id=str(capture.to_wallet_id),
        amount=str(capture.amount),
        currency=capture.currency,
        journal_entry_id=str(capture.journal_entry_id),
        created_at=capture.created_at,
    )


async def release_hold(
    db: AsyncSession,
    api_key: APIKey,
    hold_id: UUID,
    amount: Optional[str],
    idempotency_key: str,
) -> ReleaseResponse:
    """Release a hold (return held funds to available).

    Args:
        db: Database session
        api_key: API key making the request
        hold_id: ID of the hold to release
        amount: Amount to release (optional, defaults to remaining)
        idempotency_key: Idempotency key

    Returns:
        ReleaseResponse
    """
    # Check for existing idempotent release
    existing_entry = await check_idempotency(db, idempotency_key, api_key.id)
    if existing_entry and existing_entry.type == JournalEntryType.RELEASE:
        # Find the release amount from journal lines
        from agent_wallet_service.models import JournalLine
        result = await db.execute(
            select(JournalLine).where(
                JournalLine.journal_entry_id == existing_entry.id,
                JournalLine.direction == JournalLineDirection.CREDIT,
            )
        )
        credit_line = result.scalar_one()
        return ReleaseResponse(
            id=str(existing_entry.id),
            hold_id=str(hold_id),
            amount=str(credit_line.amount),
            currency=credit_line.currency,
            journal_entry_id=str(existing_entry.id),
            created_at=existing_entry.created_at,
        )

    # Get hold
    result = await db.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one_or_none()

    if hold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "HOLD_NOT_FOUND", "message": "Hold not found"},
        )

    # Check hold belongs to API key's wallet
    if hold.wallet_id != api_key.wallet_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "FORBIDDEN", "message": "Hold does not belong to this wallet"},
        )

    if not hold.can_release:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "HOLD_NOT_RELEASABLE", "message": f"Hold status is {hold.status.value}"},
        )

    # Determine release amount
    release_amount = Decimal(amount) if amount else hold.remaining_amount

    if release_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )

    if release_amount > hold.remaining_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "AMOUNT_EXCEEDS_HOLD",
                "message": f"Amount {release_amount} exceeds remaining hold {hold.remaining_amount}",
            },
        )

    # Get ledger accounts
    accounts = await get_or_create_ledger_accounts(db, hold.wallet_id, hold.currency)

    # Lock accounts
    await lock_ledger_accounts(db, [
        accounts[LedgerAccountKind.HELD].id,
        accounts[LedgerAccountKind.AVAILABLE].id,
    ])

    # Create journal entry (debit held, credit available)
    lines = [
        (accounts[LedgerAccountKind.HELD].id, JournalLineDirection.DEBIT, release_amount, hold.currency),
        (accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.CREDIT, release_amount, hold.currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.RELEASE,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
    )

    # Update hold
    hold.remaining_amount -= release_amount
    if hold.remaining_amount == 0:
        hold.status = HoldStatus.RELEASED

    await db.commit()

    return ReleaseResponse(
        id=str(entry.id),
        hold_id=str(hold.id),
        amount=str(release_amount),
        currency=hold.currency,
        journal_entry_id=str(entry.id),
        created_at=entry.created_at,
    )
