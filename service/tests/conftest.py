"""Test configuration and fixtures."""

import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_wallet_service.core.config import settings
from agent_wallet_service.db.session import Base
from agent_wallet_service.main import app
from agent_wallet_service.middleware.auth import hash_api_key
from agent_wallet_service.models import APIKey, JournalEntry, JournalLine, LedgerAccount, Wallet
from agent_wallet_service.models.api_key import APIKeyStatus
from agent_wallet_service.models.journal_entry import JournalEntryStatus, JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus, WalletType


# Test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace("agent_wallet", "agent_wallet_test")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_wallets(db_session: AsyncSession) -> dict:
    """Create test wallets."""
    # System wallet
    system_wallet = Wallet(
        type=WalletType.SYSTEM,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@system_test",
    )
    db_session.add(system_wallet)

    # Customer wallet
    customer_wallet = Wallet(
        type=WalletType.CUSTOMER,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@customer_test",
    )
    db_session.add(customer_wallet)

    # Merchant wallet
    merchant_wallet = Wallet(
        type=WalletType.BUSINESS,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@merchant_test",
    )
    db_session.add(merchant_wallet)

    await db_session.flush()

    # Create ledger accounts
    wallets = {
        "system": system_wallet,
        "customer": customer_wallet,
        "merchant": merchant_wallet,
    }

    accounts = {}
    for name, wallet in wallets.items():
        accounts[name] = {}
        for kind in LedgerAccountKind:
            account = LedgerAccount(
                wallet_id=wallet.id,
                kind=kind,
                currency="USD",
            )
            db_session.add(account)
            accounts[name][kind] = account

    await db_session.flush()

    return {
        "wallets": wallets,
        "accounts": accounts,
    }


@pytest_asyncio.fixture
async def test_api_keys(db_session: AsyncSession, test_wallets: dict) -> dict:
    """Create test API keys."""
    wallets = test_wallets["wallets"]

    # Customer API key with full permissions
    customer_key_raw = "aw_test_customer_key_123456789012345"
    customer_key = APIKey(
        key_hash=hash_api_key(customer_key_raw),
        wallet_id=wallets["customer"].id,
        scopes=[
            "wallet:read",
            "transfer:create",
            "hold:create",
            "hold:capture",
            "hold:release",
            "payment_intent:pay",
        ],
        limits={
            "per_tx_max": "500.00",
            "daily_max": "2000.00",
        },
        status=APIKeyStatus.ACTIVE,
    )
    db_session.add(customer_key)

    # Merchant API key
    merchant_key_raw = "aw_test_merchant_key_123456789012345"
    merchant_key = APIKey(
        key_hash=hash_api_key(merchant_key_raw),
        wallet_id=wallets["merchant"].id,
        scopes=[
            "wallet:read",
            "payment_intent:create",
            "refund:create",
        ],
        limits={},
        status=APIKeyStatus.ACTIVE,
    )
    db_session.add(merchant_key)

    # Limited API key (no transfer scope)
    limited_key_raw = "aw_test_limited_key_1234567890123456"
    limited_key = APIKey(
        key_hash=hash_api_key(limited_key_raw),
        wallet_id=wallets["customer"].id,
        scopes=["wallet:read"],
        limits={},
        status=APIKeyStatus.ACTIVE,
    )
    db_session.add(limited_key)

    await db_session.flush()

    return {
        "customer": {"key": customer_key, "raw": customer_key_raw},
        "merchant": {"key": merchant_key, "raw": merchant_key_raw},
        "limited": {"key": limited_key, "raw": limited_key_raw},
    }


@pytest_asyncio.fixture
async def funded_customer(
    db_session: AsyncSession, test_wallets: dict, test_api_keys: dict
) -> dict:
    """Create a funded customer wallet."""
    accounts = test_wallets["accounts"]
    api_keys = test_api_keys

    # Create deposit journal entry
    deposit_entry = JournalEntry(
        type=JournalEntryType.DEPOSIT_EXTERNAL,
        status=JournalEntryStatus.POSTED,
        idempotency_key="test_deposit_001",
        created_by_api_key_id=api_keys["customer"]["key"].id,
    )
    db_session.add(deposit_entry)
    await db_session.flush()

    # Create journal lines
    deposit_amount = Decimal("1000.00")

    debit_line = JournalLine(
        journal_entry_id=deposit_entry.id,
        ledger_account_id=accounts["system"][LedgerAccountKind.AVAILABLE].id,
        direction=JournalLineDirection.DEBIT,
        amount=deposit_amount,
        currency="USD",
    )
    db_session.add(debit_line)

    credit_line = JournalLine(
        journal_entry_id=deposit_entry.id,
        ledger_account_id=accounts["customer"][LedgerAccountKind.AVAILABLE].id,
        direction=JournalLineDirection.CREDIT,
        amount=deposit_amount,
        currency="USD",
    )
    db_session.add(credit_line)

    await db_session.commit()

    return {
        "wallets": test_wallets["wallets"],
        "accounts": accounts,
        "api_keys": api_keys,
        "initial_balance": deposit_amount,
    }
