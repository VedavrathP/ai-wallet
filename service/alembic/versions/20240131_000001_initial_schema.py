"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-31 00:00:01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    wallet_type = postgresql.ENUM("customer", "business", "system", name="wallet_type")
    wallet_type.create(op.get_bind(), checkfirst=True)

    wallet_status = postgresql.ENUM("active", "frozen", "closed", name="wallet_status")
    wallet_status.create(op.get_bind(), checkfirst=True)

    api_key_status = postgresql.ENUM("active", "revoked", name="api_key_status")
    api_key_status.create(op.get_bind(), checkfirst=True)

    ledger_account_kind = postgresql.ENUM("available", "held", name="ledger_account_kind")
    ledger_account_kind.create(op.get_bind(), checkfirst=True)

    journal_entry_type = postgresql.ENUM(
        "deposit_external",
        "transfer",
        "hold",
        "capture",
        "release",
        "refund",
        "reversal",
        "adjustment",
        name="journal_entry_type",
    )
    journal_entry_type.create(op.get_bind(), checkfirst=True)

    journal_entry_status = postgresql.ENUM(
        "pending", "posted", "reversed", "failed", name="journal_entry_status"
    )
    journal_entry_status.create(op.get_bind(), checkfirst=True)

    journal_line_direction = postgresql.ENUM("debit", "credit", name="journal_line_direction")
    journal_line_direction.create(op.get_bind(), checkfirst=True)

    hold_status = postgresql.ENUM("active", "captured", "released", "expired", name="hold_status")
    hold_status.create(op.get_bind(), checkfirst=True)

    payment_intent_status = postgresql.ENUM(
        "requires_payment", "paid", "expired", "cancelled", name="payment_intent_status"
    )
    payment_intent_status.create(op.get_bind(), checkfirst=True)

    # Create wallets table
    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", wallet_type, nullable=False),
        sa.Column("status", wallet_status, nullable=False, server_default="active"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("handle", sa.String(64), unique=True, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_wallets_handle", "wallets", ["handle"])
    op.create_index("ix_wallets_created_at", "wallets", ["created_at"])
    op.create_index("ix_wallets_status", "wallets", ["status"])

    # Create external_identities table
    op.create_table(
        "external_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_user_id", sa.String(256), nullable=False),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("provider", "external_user_id", name="uq_external_identity"),
    )
    op.create_index("ix_external_identities_provider", "external_identities", ["provider"])
    op.create_index(
        "ix_external_identities_external_user_id", "external_identities", ["external_user_id"]
    )
    op.create_index("ix_external_identities_wallet_id", "external_identities", ["wallet_id"])

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(256), nullable=False, unique=True),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("limits", postgresql.JSONB, nullable=True),
        sa.Column("status", api_key_status, nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_api_keys_wallet_id", "api_keys", ["wallet_id"])
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])

    # Create ledger_accounts table
    op.create_table(
        "ledger_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", ledger_account_kind, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("wallet_id", "kind", name="uq_ledger_account_wallet_kind"),
    )
    op.create_index("ix_ledger_accounts_wallet_id", "ledger_accounts", ["wallet_id"])

    # Create journal_entries table
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", journal_entry_type, nullable=False),
        sa.Column("status", journal_entry_status, nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("reference_id", sa.String(256), nullable=True),
        sa.Column(
            "created_by_api_key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "idempotency_key", "created_by_api_key_id", name="uq_journal_entry_idempotency"
        ),
    )
    op.create_index("ix_journal_entries_type", "journal_entries", ["type"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])
    op.create_index("ix_journal_entries_idempotency_key", "journal_entries", ["idempotency_key"])
    op.create_index("ix_journal_entries_reference_id", "journal_entries", ["reference_id"])
    op.create_index(
        "ix_journal_entries_created_by_api_key_id", "journal_entries", ["created_by_api_key_id"]
    )

    # Create journal_lines table
    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ledger_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ledger_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", journal_line_direction, nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
    op.create_index("ix_journal_lines_ledger_account_id", "journal_lines", ["ledger_account_id"])

    # Create holds table
    op.create_table(
        "holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", hold_status, nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_api_key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("idempotency_key", "created_by_api_key_id", name="uq_hold_idempotency"),
    )
    op.create_index("ix_holds_wallet_id", "holds", ["wallet_id"])
    op.create_index("ix_holds_status", "holds", ["status"])
    op.create_index("ix_holds_idempotency_key", "holds", ["idempotency_key"])
    op.create_index("ix_holds_created_by_api_key_id", "holds", ["created_by_api_key_id"])

    # Create payment_intents table
    op.create_table(
        "payment_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "status", payment_intent_status, nullable=False, server_default="requires_payment"
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "payer_wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_payment_intents_merchant_wallet_id", "payment_intents", ["merchant_wallet_id"])
    op.create_index("ix_payment_intents_status", "payment_intents", ["status"])

    # Create captures table
    op.create_table(
        "captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hold_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("holds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("refunded_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_captures_hold_id", "captures", ["hold_id"])
    op.create_index("ix_captures_to_wallet_id", "captures", ["to_wallet_id"])
    op.create_index("ix_captures_idempotency_key", "captures", ["idempotency_key"])

    # Create refunds table
    op.create_table(
        "refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "capture_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("captures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_refunds_capture_id", "refunds", ["capture_id"])
    op.create_index("ix_refunds_idempotency_key", "refunds", ["idempotency_key"])

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("route", sa.String(256), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_logs_api_key_id", "audit_logs", ["api_key_id"])
    op.create_index("ix_audit_logs_route", "audit_logs", ["route"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("audit_logs")
    op.drop_table("refunds")
    op.drop_table("captures")
    op.drop_table("payment_intents")
    op.drop_table("holds")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("ledger_accounts")
    op.drop_table("api_keys")
    op.drop_table("external_identities")
    op.drop_table("wallets")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS payment_intent_status")
    op.execute("DROP TYPE IF EXISTS hold_status")
    op.execute("DROP TYPE IF EXISTS journal_line_direction")
    op.execute("DROP TYPE IF EXISTS journal_entry_status")
    op.execute("DROP TYPE IF EXISTS journal_entry_type")
    op.execute("DROP TYPE IF EXISTS ledger_account_kind")
    op.execute("DROP TYPE IF EXISTS api_key_status")
    op.execute("DROP TYPE IF EXISTS wallet_status")
    op.execute("DROP TYPE IF EXISTS wallet_type")
