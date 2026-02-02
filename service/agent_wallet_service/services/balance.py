"""Balance service for deriving wallet balances from journal entries."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import JournalEntry, JournalLine, LedgerAccount, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryStatus
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.schemas.wallet import BalanceResponse


async def get_ledger_account_balance(
    db: AsyncSession,
    ledger_account_id: UUID,
) -> Decimal:
    """Calculate the balance of a ledger account from journal lines.

    Balance = sum(credits) - sum(debits)

    For asset accounts (like wallet available/held):
    - Credits increase the balance
    - Debits decrease the balance

    Args:
        db: Database session
        ledger_account_id: ID of the ledger account

    Returns:
        Current balance as Decimal
    """
    # Sum credits
    credit_result = await db.execute(
        select(func.coalesce(func.sum(JournalLine.amount), Decimal("0")))
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalLine.ledger_account_id == ledger_account_id,
            JournalLine.direction == JournalLineDirection.CREDIT,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    total_credits = credit_result.scalar() or Decimal("0")

    # Sum debits
    debit_result = await db.execute(
        select(func.coalesce(func.sum(JournalLine.amount), Decimal("0")))
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalLine.ledger_account_id == ledger_account_id,
            JournalLine.direction == JournalLineDirection.DEBIT,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    total_debits = debit_result.scalar() or Decimal("0")

    return total_credits - total_debits


async def get_wallet_balance(
    db: AsyncSession,
    wallet_id: UUID,
) -> BalanceResponse:
    """Get the balance of a wallet.

    Args:
        db: Database session
        wallet_id: ID of the wallet

    Returns:
        BalanceResponse with available, held, and total amounts
    """
    # Get wallet currency
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one()

    # Get ledger accounts
    result = await db.execute(
        select(LedgerAccount).where(LedgerAccount.wallet_id == wallet_id)
    )
    ledger_accounts = {la.kind: la for la in result.scalars().all()}

    # Calculate balances
    available = Decimal("0")
    held = Decimal("0")

    if LedgerAccountKind.AVAILABLE in ledger_accounts:
        available = await get_ledger_account_balance(
            db, ledger_accounts[LedgerAccountKind.AVAILABLE].id
        )

    if LedgerAccountKind.HELD in ledger_accounts:
        held = await get_ledger_account_balance(
            db, ledger_accounts[LedgerAccountKind.HELD].id
        )

    total = available + held

    return BalanceResponse(
        wallet_id=str(wallet_id),
        available=str(available),
        held=str(held),
        total=str(total),
        currency=wallet.currency,
    )


async def get_available_balance(
    db: AsyncSession,
    wallet_id: UUID,
) -> Decimal:
    """Get only the available balance of a wallet.

    Args:
        db: Database session
        wallet_id: ID of the wallet

    Returns:
        Available balance as Decimal
    """
    result = await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == wallet_id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    available_account = result.scalar_one_or_none()

    if available_account is None:
        return Decimal("0")

    return await get_ledger_account_balance(db, available_account.id)


async def get_held_balance(
    db: AsyncSession,
    wallet_id: UUID,
) -> Decimal:
    """Get only the held balance of a wallet.

    Args:
        db: Database session
        wallet_id: ID of the wallet

    Returns:
        Held balance as Decimal
    """
    result = await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == wallet_id,
            LedgerAccount.kind == LedgerAccountKind.HELD,
        )
    )
    held_account = result.scalar_one_or_none()

    if held_account is None:
        return Decimal("0")

    return await get_ledger_account_balance(db, held_account.id)
