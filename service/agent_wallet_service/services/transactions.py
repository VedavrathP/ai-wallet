"""Transaction listing service."""

import base64
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import JournalEntry, JournalLine, LedgerAccount, Wallet
from agent_wallet_service.models.journal_entry import JournalEntryStatus
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.schemas.wallet import TransactionListResponse, TransactionResponse


async def list_wallet_transactions(
    db: AsyncSession,
    wallet_id: UUID,
    cursor: Optional[str] = None,
    limit: int = 50,
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> TransactionListResponse:
    """List transactions for a wallet.

    Args:
        db: Database session
        wallet_id: Wallet ID
        cursor: Pagination cursor (base64 encoded timestamp)
        limit: Maximum number of transactions
        type_filter: Filter by transaction type
        status_filter: Filter by status
        from_date: Filter by start date (ISO format)
        to_date: Filter by end date (ISO format)

    Returns:
        TransactionListResponse
    """
    # Get wallet's ledger accounts
    result = await db.execute(
        select(LedgerAccount).where(LedgerAccount.wallet_id == wallet_id)
    )
    ledger_accounts = {la.id: la for la in result.scalars().all()}
    account_ids = list(ledger_accounts.keys())

    if not account_ids:
        return TransactionListResponse(items=[], cursor=None, has_more=False)

    # Build query for journal lines affecting this wallet
    query = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(JournalLine.ledger_account_id.in_(account_ids))
        .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
    )

    # Apply filters
    if type_filter:
        query = query.where(JournalEntry.type == type_filter)

    if status_filter:
        query = query.where(JournalEntry.status == status_filter)

    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            query = query.where(JournalEntry.created_at >= from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            query = query.where(JournalEntry.created_at <= to_dt)
        except ValueError:
            pass

    # Apply cursor
    if cursor:
        try:
            cursor_data = base64.b64decode(cursor).decode()
            cursor_ts, cursor_id = cursor_data.rsplit(":", 1)
            cursor_dt = datetime.fromisoformat(cursor_ts)
            query = query.where(
                or_(
                    JournalEntry.created_at < cursor_dt,
                    and_(
                        JournalEntry.created_at == cursor_dt,
                        JournalEntry.id < UUID(cursor_id),
                    ),
                )
            )
        except (ValueError, TypeError):
            pass

    # Fetch one extra to check for more
    query = query.limit(limit + 1)

    result = await db.execute(query)
    rows = result.all()

    # Check if there are more results
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Build transaction responses
    transactions: list[TransactionResponse] = []
    seen_entries: set[UUID] = set()

    for line, entry in rows:
        # Skip duplicate entries (we might have multiple lines per entry)
        if entry.id in seen_entries:
            continue
        seen_entries.add(entry.id)

        # Determine direction based on the line
        direction = line.direction.value

        # Find counterparty
        counterparty_wallet_id = None
        counterparty_handle = None

        # Get all lines for this entry to find counterparty
        entry_result = await db.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
        )
        entry_lines = entry_result.scalars().all()

        for other_line in entry_lines:
            if other_line.ledger_account_id not in account_ids:
                # This is the counterparty's account
                la_result = await db.execute(
                    select(LedgerAccount).where(LedgerAccount.id == other_line.ledger_account_id)
                )
                counterparty_account = la_result.scalar_one_or_none()
                if counterparty_account:
                    counterparty_wallet_id = str(counterparty_account.wallet_id)
                    # Get handle
                    wallet_result = await db.execute(
                        select(Wallet).where(Wallet.id == counterparty_account.wallet_id)
                    )
                    counterparty_wallet = wallet_result.scalar_one_or_none()
                    if counterparty_wallet:
                        counterparty_handle = counterparty_wallet.handle
                break

        transactions.append(
            TransactionResponse(
                id=str(entry.id),
                type=entry.type.value,
                status=entry.status.value,
                amount=str(line.amount),
                currency=line.currency,
                direction=direction,
                counterparty_wallet_id=counterparty_wallet_id,
                counterparty_handle=counterparty_handle,
                reference_id=entry.reference_id,
                metadata=entry.entry_metadata or {},
                created_at=entry.created_at,
            )
        )

    # Build next cursor
    next_cursor = None
    if has_more and transactions:
        last_tx = transactions[-1]
        cursor_data = f"{last_tx.created_at.isoformat()}:{last_tx.id}"
        next_cursor = base64.b64encode(cursor_data.encode()).decode()

    return TransactionListResponse(
        items=transactions,
        cursor=next_cursor,
        has_more=has_more,
    )
