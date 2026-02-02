"""Seed script for creating test data."""

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_wallet_service.core.config import settings
from agent_wallet_service.middleware.auth import hash_api_key
from agent_wallet_service.models import APIKey, JournalEntry, JournalLine, LedgerAccount, Wallet
from agent_wallet_service.models.api_key import APIKeyStatus
from agent_wallet_service.models.journal_entry import JournalEntryStatus, JournalEntryType
from agent_wallet_service.models.journal_line import JournalLineDirection
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.models.wallet import WalletStatus, WalletType


# Predefined API keys for testing (in production, these would be generated)
ALICE_API_KEY = "aw_alice_test_key_12345678901234567890"
MERCHANT_API_KEY = "aw_merchant_test_key_12345678901234567890"
ADMIN_API_KEY = "aw_admin_test_key_123456789012345678901"


async def seed_database(session: AsyncSession) -> None:
    """Seed the database with test data."""
    print("Starting database seed...")

    # Check if already seeded
    result = await session.execute(select(Wallet).where(Wallet.handle == "@alice"))
    if result.scalar_one_or_none():
        print("Database already seeded. Skipping...")
        return

    # Create system wallet (for external deposits)
    print("Creating system wallet...")
    system_wallet = Wallet(
        type=WalletType.SYSTEM,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@system",
        wallet_metadata={"description": "System wallet for external deposits"},
    )
    session.add(system_wallet)
    await session.flush()

    # Create system ledger accounts
    for kind in LedgerAccountKind:
        account = LedgerAccount(
            wallet_id=system_wallet.id,
            kind=kind,
            currency="USD",
        )
        session.add(account)

    # Create customer wallet (@alice)
    print("Creating customer wallet @alice...")
    alice_wallet = Wallet(
        type=WalletType.CUSTOMER,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@alice",
        wallet_metadata={"name": "Alice", "email": "alice@example.com"},
    )
    session.add(alice_wallet)
    await session.flush()

    # Create alice ledger accounts
    alice_accounts = {}
    for kind in LedgerAccountKind:
        account = LedgerAccount(
            wallet_id=alice_wallet.id,
            kind=kind,
            currency="USD",
        )
        session.add(account)
        alice_accounts[kind] = account
    await session.flush()

    # Create merchant wallet (@acme_store)
    print("Creating merchant wallet @acme_store...")
    merchant_wallet = Wallet(
        type=WalletType.BUSINESS,
        status=WalletStatus.ACTIVE,
        currency="USD",
        handle="@acme_store",
        wallet_metadata={"name": "Acme Store", "business_id": "acme-123"},
    )
    session.add(merchant_wallet)
    await session.flush()

    # Create merchant ledger accounts
    for kind in LedgerAccountKind:
        account = LedgerAccount(
            wallet_id=merchant_wallet.id,
            kind=kind,
            currency="USD",
        )
        session.add(account)

    # Create admin API key
    print("Creating admin API key...")
    admin_key = APIKey(
        key_hash=hash_api_key(ADMIN_API_KEY),
        wallet_id=system_wallet.id,
        scopes=[
            "admin:wallets",
            "admin:api_keys",
            "wallet:read",
        ],
        limits={},
        status=APIKeyStatus.ACTIVE,
    )
    session.add(admin_key)
    await session.flush()

    # Create Alice's API key
    print("Creating Alice's API key...")
    alice_key = APIKey(
        key_hash=hash_api_key(ALICE_API_KEY),
        wallet_id=alice_wallet.id,
        scopes=[
            "wallet:read",
            "transfer:create",
            "hold:create",
            "hold:capture",
            "hold:release",
            "payment_intent:pay",
        ],
        limits={
            "per_tx_max": "1000.00",
            "daily_max": "5000.00",
        },
        status=APIKeyStatus.ACTIVE,
    )
    session.add(alice_key)
    await session.flush()

    # Create merchant's API key
    print("Creating merchant's API key...")
    merchant_key = APIKey(
        key_hash=hash_api_key(MERCHANT_API_KEY),
        wallet_id=merchant_wallet.id,
        scopes=[
            "wallet:read",
            "payment_intent:create",
            "refund:create",
        ],
        limits={},
        status=APIKeyStatus.ACTIVE,
    )
    session.add(merchant_key)
    await session.flush()

    # Seed deposit for Alice ($1000)
    print("Creating initial deposit for Alice ($1000)...")

    # Get system available account
    result = await session.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == system_wallet.id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    system_available = result.scalar_one()

    # Create deposit journal entry
    deposit_entry = JournalEntry(
        type=JournalEntryType.DEPOSIT_EXTERNAL,
        status=JournalEntryStatus.POSTED,
        idempotency_key="seed_deposit_alice_001",
        reference_id="seed_deposit",
        created_by_api_key_id=admin_key.id,
        entry_metadata={"description": "Initial seed deposit for Alice"},
    )
    session.add(deposit_entry)
    await session.flush()

    # Create journal lines (debit system, credit alice)
    deposit_amount = Decimal("1000.00")

    debit_line = JournalLine(
        journal_entry_id=deposit_entry.id,
        ledger_account_id=system_available.id,
        direction=JournalLineDirection.DEBIT,
        amount=deposit_amount,
        currency="USD",
    )
    session.add(debit_line)

    credit_line = JournalLine(
        journal_entry_id=deposit_entry.id,
        ledger_account_id=alice_accounts[LedgerAccountKind.AVAILABLE].id,
        direction=JournalLineDirection.CREDIT,
        amount=deposit_amount,
        currency="USD",
    )
    session.add(credit_line)

    await session.commit()

    print("\n" + "=" * 60)
    print("DATABASE SEEDED SUCCESSFULLY!")
    print("=" * 60)
    print("\nCreated wallets:")
    print(f"  - System wallet: @system (ID: {system_wallet.id})")
    print(f"  - Customer wallet: @alice (ID: {alice_wallet.id})")
    print(f"  - Merchant wallet: @acme_store (ID: {merchant_wallet.id})")
    print("\nAPI Keys (save these, they won't be shown again):")
    print(f"  - Admin key: {ADMIN_API_KEY}")
    print(f"  - Alice's key: {ALICE_API_KEY}")
    print(f"  - Merchant's key: {MERCHANT_API_KEY}")
    print("\nAlice's initial balance: $1000.00 USD")
    print("\nAlice's scopes: wallet:read, transfer:create, hold:create, hold:capture, hold:release, payment_intent:pay")
    print("Alice's limits: per_tx_max=$1000.00, daily_max=$5000.00")
    print("\nMerchant's scopes: wallet:read, payment_intent:create, refund:create")
    print("=" * 60)


async def main() -> None:
    """Main entry point."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed_database(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
