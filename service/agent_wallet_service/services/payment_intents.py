"""Payment intent service."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.middleware.auth import enforce_limits
from agent_wallet_service.models import APIKey, PaymentIntent, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.payment_intent import PaymentIntentStatus
from agent_wallet_service.models.wallet import WalletStatus
from agent_wallet_service.schemas.payment_intent import PaymentIntentResponse, PaymentResultResponse
from agent_wallet_service.services.balance import get_ledger_account_balance
from agent_wallet_service.services.ledger import (
    check_idempotency,
    create_journal_entry,
    get_or_create_ledger_accounts,
    lock_ledger_accounts,
)


async def create_payment_intent(
    db: AsyncSession,
    api_key: APIKey,
    merchant_wallet_id: UUID,
    amount: str,
    currency: str,
    expires_in_seconds: int = 900,
    metadata: Optional[dict[str, Any]] = None,
) -> PaymentIntentResponse:
    """Create a payment intent (merchant operation).

    Args:
        db: Database session
        api_key: API key making the request
        merchant_wallet_id: Merchant wallet ID
        amount: Amount for the payment intent
        currency: Currency code
        expires_in_seconds: Expiration time
        metadata: Optional metadata

    Returns:
        PaymentIntentResponse
    """
    amount_decimal = Decimal(amount)

    if amount_decimal <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_AMOUNT", "message": "Amount must be positive"},
        )

    # Check merchant wallet
    result = await db.execute(select(Wallet).where(Wallet.id == merchant_wallet_id))
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

    # Create payment intent
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    intent = PaymentIntent(
        merchant_wallet_id=merchant_wallet_id,
        amount=amount_decimal,
        currency=currency,
        status=PaymentIntentStatus.REQUIRES_PAYMENT,
        expires_at=expires_at,
        intent_metadata=metadata or {},
    )
    db.add(intent)
    await db.commit()

    return PaymentIntentResponse(
        id=str(intent.id),
        merchant_wallet_id=str(intent.merchant_wallet_id),
        amount=str(intent.amount),
        currency=intent.currency,
        status=intent.status.value,
        expires_at=intent.expires_at,
        metadata=intent.intent_metadata or {},
        created_at=intent.created_at,
    )


async def pay_payment_intent(
    db: AsyncSession,
    api_key: APIKey,
    payer_wallet_id: UUID,
    intent_id: UUID,
    idempotency_key: str,
) -> PaymentResultResponse:
    """Pay a payment intent.

    Args:
        db: Database session
        api_key: API key making the request
        payer_wallet_id: Payer wallet ID
        intent_id: Payment intent ID
        idempotency_key: Idempotency key

    Returns:
        PaymentResultResponse
    """
    # Check for existing idempotent payment
    existing_entry = await check_idempotency(db, idempotency_key, api_key.id)
    if existing_entry:
        # Get the payment intent
        result = await db.execute(
            select(PaymentIntent).where(PaymentIntent.journal_entry_id == existing_entry.id)
        )
        intent = result.scalar_one_or_none()
        if intent:
            return PaymentResultResponse(
                payment_intent_id=str(intent.id),
                journal_entry_id=str(existing_entry.id),
                payer_wallet_id=str(intent.payer_wallet_id),
                merchant_wallet_id=str(intent.merchant_wallet_id),
                amount=str(intent.amount),
                currency=intent.currency,
                created_at=existing_entry.created_at,
            )

    # Get payment intent
    result = await db.execute(select(PaymentIntent).where(PaymentIntent.id == intent_id))
    intent = result.scalar_one_or_none()

    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PAYMENT_INTENT_NOT_FOUND", "message": "Payment intent not found"},
        )

    if not intent.can_pay:
        if intent.is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PAYMENT_INTENT_EXPIRED", "message": "Payment intent has expired"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "PAYMENT_INTENT_NOT_PAYABLE", "message": f"Status is {intent.status.value}"},
        )

    # Check payer wallet
    result = await db.execute(select(Wallet).where(Wallet.id == payer_wallet_id))
    payer_wallet = result.scalar_one()

    if payer_wallet.status != WalletStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "WALLET_NOT_ACTIVE", "message": f"Wallet is {payer_wallet.status.value}"},
        )

    if payer_wallet.currency != intent.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CURRENCY_MISMATCH", "message": f"Wallet currency is {payer_wallet.currency}"},
        )

    # Prevent self-payment
    if payer_wallet_id == intent.merchant_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "SELF_PAYMENT", "message": "Cannot pay your own payment intent"},
        )

    # Enforce limits
    await enforce_limits(db, api_key, intent.amount, intent.merchant_wallet_id)

    # Get ledger accounts
    payer_accounts = await get_or_create_ledger_accounts(db, payer_wallet_id, intent.currency)
    merchant_accounts = await get_or_create_ledger_accounts(db, intent.merchant_wallet_id, intent.currency)

    # Lock accounts
    await lock_ledger_accounts(db, [
        payer_accounts[LedgerAccountKind.AVAILABLE].id,
        merchant_accounts[LedgerAccountKind.AVAILABLE].id,
    ])

    # Check sufficient balance
    available = await get_ledger_account_balance(db, payer_accounts[LedgerAccountKind.AVAILABLE].id)

    if available < intent.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INSUFFICIENT_FUNDS",
                "message": f"Insufficient funds. Available: {available}, Required: {intent.amount}",
            },
        )

    # Create journal entry
    lines = [
        (payer_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.DEBIT, intent.amount, intent.currency),
        (merchant_accounts[LedgerAccountKind.AVAILABLE].id, JournalLineDirection.CREDIT, intent.amount, intent.currency),
    ]

    entry = await create_journal_entry(
        db=db,
        entry_type=JournalEntryType.TRANSFER,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
        lines=lines,
        reference_id=str(intent.id),
    )

    # Update payment intent
    intent.status = PaymentIntentStatus.PAID
    intent.payer_wallet_id = payer_wallet_id
    intent.journal_entry_id = entry.id

    await db.commit()

    return PaymentResultResponse(
        payment_intent_id=str(intent.id),
        journal_entry_id=str(entry.id),
        payer_wallet_id=str(payer_wallet_id),
        merchant_wallet_id=str(intent.merchant_wallet_id),
        amount=str(intent.amount),
        currency=intent.currency,
        created_at=entry.created_at,
    )
