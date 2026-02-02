"""Refund service."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import APIKey, Capture, Hold, Refund, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.schemas.refund import RefundResponse
from agent_wallet_service.services.balance import get_ledger_account_balance
from agent_wallet_service.services.ledger import (
    create_journal_entry,
    get_or_create_ledger_accounts,
    lock_ledger_accounts,
)


async def create_refund(
    db: AsyncSession,
    api_key: APIKey,
    capture_id: UUID,
    amount: Optional[str],
    idempotency_key: str,
) -> RefundResponse:
    """Create a refund against a capture.

    Args:
        db: Database session
        api_key: API key making the request (must be merchant)
        capture_id: ID of the capture to refund
        amount: Amount to refund (optional, defaults to full capture amount)
        idempotency_key: Idempotency key

    Returns:
        RefundResponse
    """
    # Check for existing idempotent refund
    result = await db.execute(
        select(Refund).where(Refund.idempotency_key == idempotency_key)
    )
    existing_refund = result.scalar_one_or_none()
    if existing_refund:
        return RefundResponse(
            id=str(existing_refund.id),
            capture_id=str(existing_refund.capture_id),
            amount=str(existing_refund.amount),
            currency=existing_refund.currency,
            journal_entry_id=str(existing_refund.journal_entry_id),
            created_at=existing_refund.created_at,
        )

    # Get capture
    result = await db.execute(select(Capture).where(Capture.id == capture_id))
    capture = result.scalar_one_or_none()

    if capture is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "CAPTURE_NOT_FOUND", "message": "Capture not found"},
        )

    # Check that the API key's wallet is the merchant (recipient of the capture)
    if capture.to_wallet_id != api_key.wallet_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "FORBIDDEN", "message": "Only the merchant can issue refunds"},
        )

    # Determine refund amount
    refund_amount = Decimal(amount) if amount else capture.refundable_amount

    if refund_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )

    if refund_amount > capture.refundable_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "AMOUNT_EXCEEDS_REFUNDABLE",
                "message": f"Amount {refund_amount} exceeds refundable amount {capture.refundable_amount}",
            },
        )

    # Get the hold to find the payer wallet
    result = await db.execute(select(Hold).where(Hold.id == capture.hold_id))
    hold = result.scalar_one()
    payer_wallet_id = hold.wallet_id

    # Check merchant wallet status
    result = await db.execute(select(Wallet).where(Wallet.id == capture.to_wallet_id))
    merchant_wallet = result.scalar_one()

    if merchant_wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "WALLET_NOT_ACTIVE", "message": f"Merchant wallet is {merchant_wallet.status.value}"},
        )

    # Get ledger accounts
    merchant_accounts = await get_or_create_ledger_accounts(db, capture.to_wallet_id, capture.currency)
    payer_accounts = await get_or_create_ledger_accounts(db, payer_wallet_id, capture.currency)

    # Lock accounts
    await lock_ledger_accounts(db, [
        merchant_accounts[LedgerAccountKind.AVAILABLE].id,
        payer_accounts[LedgerAccountKind.AVAILABLE].id,
    ])

    # Check merchant has sufficient balance
    merchant_available = await get_ledger_account_balance(
        db, merchant_accounts[LedgerAccountKind.AVAILABLE].id
    )

    if merchant_available < refund_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INSUFFICIENT_FUNDS",
                "message": f"Insufficient funds for refund. Available: {merchant_available}",
            },
        )

    # Create journal entry (debit merchant, credit payer)
    lines = [
        (merchant_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.DEBIT, refund_amount, capture.currency),
        (payer_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.CREDIT, refund_amount, capture.currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.REFUND,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
        reference_id=str(capture.id),
    )

    # Update capture refunded amount
    capture.refunded_amount += refund_amount

    # Create refund record
    refund = Refund(
        capture_id=capture.id,
        amount=refund_amount,
        currency=capture.currency,
        journal_entry_id=entry.id,
        idempotency_key=idempotency_key,
    )
    db.add(refund)
    await db.commit()

    return RefundResponse(
        id=str(refund.id),
        capture_id=str(refund.capture_id),
        amount=str(refund.amount),
        currency=refund.currency,
        journal_entry_id=str(refund.journal_entry_id),
        created_at=refund.created_at,
    )
