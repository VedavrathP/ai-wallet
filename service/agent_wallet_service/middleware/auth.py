"""API key authentication middleware."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

import argon2
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.db import get_db
from agent_wallet_service.models import APIKey, JournalEntry, JournalLine
from agent_wallet_service.models.api_key import APIKeyStatus
from agent_wallet_service.models.journal_entry import JournalEntryStatus

# Password hasher for API keys
ph = argon2.PasswordHasher()

# HTTP Bearer security scheme
security = HTTPBearer()


def hash_api_key(api_key: str) -> str:
    """Hash an API key using Argon2."""
    return ph.hash(api_key)


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    try:
        ph.verify(key_hash, api_key)
        return True
    except argon2.exceptions.VerifyMismatchError:
        return False


async def get_api_key_by_raw_key(db: AsyncSession, raw_key: str) -> Optional[APIKey]:
    """Look up an API key by its raw value.

    This is O(n) in the number of API keys, but we can optimize later
    by using a key prefix lookup table.
    """
    # Get all active API keys
    result = await db.execute(
        select(APIKey).where(APIKey.status == APIKeyStatus.ACTIVE)
    )
    api_keys = result.scalars().all()

    # Check each key
    for api_key in api_keys:
        if verify_api_key(raw_key, api_key.key_hash):
            return api_key

    return None


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Get the current API key from the request.

    Raises HTTPException if the key is invalid or revoked.
    """
    raw_key = credentials.credentials

    api_key = await get_api_key_by_raw_key(db, raw_key)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_API_KEY", "message": "Invalid API key"},
        )

    if api_key.status != APIKeyStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "API_KEY_REVOKED", "message": "API key has been revoked"},
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return api_key


def require_scope(required_scope: str) -> Callable[..., APIKey]:
    """Create a dependency that requires a specific scope.

    Usage:
        @router.get("/endpoint")
        async def endpoint(api_key: APIKey = Depends(require_scope("wallet:read"))):
            ...
    """

    async def dependency(
        api_key: APIKey = Depends(get_current_api_key),
    ) -> APIKey:
        if not api_key.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN_SCOPE",
                    "message": f"API key does not have required scope: {required_scope}",
                },
            )
        return api_key

    return dependency


async def check_transaction_limit(
    db: AsyncSession,
    api_key: APIKey,
    amount: Decimal,
) -> None:
    """Check if a transaction exceeds the per-transaction limit.

    Raises HTTPException if the limit is exceeded.
    """
    per_tx_max = api_key.get_limit("per_tx_max")
    if per_tx_max is not None:
        max_amount = Decimal(str(per_tx_max))
        if amount > max_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "LIMIT_EXCEEDED",
                    "message": f"Transaction amount {amount} exceeds per-transaction limit {max_amount}",
                    "details": {"limit": str(max_amount), "requested": str(amount)},
                },
            )


async def check_daily_limit(
    db: AsyncSession,
    api_key: APIKey,
    amount: Decimal,
) -> None:
    """Check if a transaction would exceed the daily spending limit.

    Raises HTTPException if the limit would be exceeded.
    """
    daily_max = api_key.get_limit("daily_max")
    if daily_max is None:
        return

    max_amount = Decimal(str(daily_max))

    # Calculate today's spending from posted journal entries
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Sum all debit amounts from journal lines for this API key's wallet today
    from agent_wallet_service.models import LedgerAccount
    from agent_wallet_service.models.ledger_account import LedgerAccountKind

    # Get the wallet's available ledger account
    result = await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == api_key.wallet_id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    available_account = result.scalar_one_or_none()

    if available_account is None:
        return

    # Sum debits from today
    result = await db.execute(
        select(func.coalesce(func.sum(JournalLine.amount), Decimal("0")))
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalLine.ledger_account_id == available_account.id,
            JournalLine.direction == "debit",
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.created_at >= today_start,
        )
    )
    today_spent = result.scalar() or Decimal("0")

    if today_spent + amount > max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "LIMIT_EXCEEDED",
                "message": f"Transaction would exceed daily limit. Spent today: {today_spent}, Limit: {max_amount}",
                "details": {
                    "daily_limit": str(max_amount),
                    "spent_today": str(today_spent),
                    "requested": str(amount),
                },
            },
        )


async def check_counterparty_allowlist(
    api_key: APIKey,
    counterparty_wallet_id: UUID,
    counterparty_handle: Optional[str] = None,
) -> None:
    """Check if the counterparty is in the allowlist (if configured).

    Raises HTTPException if the counterparty is not allowed.
    """
    allowed_counterparties = api_key.get_limit("allowed_counterparties")
    if allowed_counterparties is None:
        return

    # Check if wallet_id or handle is in the allowlist
    allowed_ids = [str(c.get("wallet_id", "")) for c in allowed_counterparties if "wallet_id" in c]
    allowed_handles = [c.get("handle", "") for c in allowed_counterparties if "handle" in c]

    if str(counterparty_wallet_id) in allowed_ids:
        return

    if counterparty_handle and counterparty_handle in allowed_handles:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "COUNTERPARTY_NOT_ALLOWED",
            "message": "Counterparty is not in the allowlist",
        },
    )


async def enforce_limits(
    db: AsyncSession,
    api_key: APIKey,
    amount: Decimal,
    counterparty_wallet_id: Optional[UUID] = None,
    counterparty_handle: Optional[str] = None,
) -> None:
    """Enforce all limits for a transaction.

    Raises HTTPException if any limit is exceeded.
    """
    await check_transaction_limit(db, api_key, amount)
    await check_daily_limit(db, api_key, amount)

    if counterparty_wallet_id is not None:
        await check_counterparty_allowlist(api_key, counterparty_wallet_id, counterparty_handle)
