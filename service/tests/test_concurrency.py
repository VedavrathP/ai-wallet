"""Tests for concurrency and double-spend prevention."""

import asyncio
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.main import app
from agent_wallet_service.models import LedgerAccount
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.services.balance import get_ledger_account_balance


@pytest.mark.asyncio
async def test_concurrent_transfers_no_double_spend(
    db_session: AsyncSession, funded_customer: dict
):
    """Test that concurrent transfers don't allow double-spending."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle
    initial_balance = funded_customer["initial_balance"]

    # Try to make 5 concurrent transfers of $300 each (total $1500)
    # With only $1000 balance, at most 3 should succeed
    async def make_transfer(idx: int) -> dict:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/transfers",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "amount": "300.00",
                    "currency": "USD",
                    "to": {"type": "handle", "value": merchant_handle},
                    "idempotency_key": f"concurrent_transfer_{idx}",
                },
            )
            return {"status": response.status_code, "data": response.json()}

    # Run transfers concurrently
    results = await asyncio.gather(*[make_transfer(i) for i in range(5)])

    # Count successes and failures
    successes = [r for r in results if r["status"] == 200]
    failures = [r for r in results if r["status"] != 200]

    # At most 3 transfers should succeed ($300 * 3 = $900 <= $1000)
    assert len(successes) <= 3

    # Check that balance is non-negative
    customer_wallet_id = funded_customer["wallets"]["customer"].id
    result = await db_session.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == customer_wallet_id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    available_account = result.scalar_one()
    balance = await get_ledger_account_balance(db_session, available_account.id)

    assert balance >= Decimal("0")
    assert balance == initial_balance - (Decimal("300.00") * len(successes))


@pytest.mark.asyncio
async def test_concurrent_holds_no_double_spend(
    db_session: AsyncSession, funded_customer: dict
):
    """Test that concurrent holds don't exceed available balance."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    initial_balance = funded_customer["initial_balance"]

    # Try to make 5 concurrent holds of $300 each
    async def make_hold(idx: int) -> dict:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/holds",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "amount": "300.00",
                    "currency": "USD",
                    "idempotency_key": f"concurrent_hold_{idx}",
                    "expires_in_seconds": 3600,
                },
            )
            return {"status": response.status_code, "data": response.json()}

    # Run holds concurrently
    results = await asyncio.gather(*[make_hold(i) for i in range(5)])

    # Count successes
    successes = [r for r in results if r["status"] == 200]

    # At most 3 holds should succeed
    assert len(successes) <= 3

    # Check that available balance is non-negative
    customer_wallet_id = funded_customer["wallets"]["customer"].id
    result = await db_session.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == customer_wallet_id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    available_account = result.scalar_one()
    available_balance = await get_ledger_account_balance(db_session, available_account.id)

    assert available_balance >= Decimal("0")
