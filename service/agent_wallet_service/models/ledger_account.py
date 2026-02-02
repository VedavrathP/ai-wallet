"""Ledger account model."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.journal_line import JournalLine
    from agent_wallet_service.models.wallet import Wallet


class LedgerAccountKind(str, enum.Enum):
    """Ledger account kind enumeration."""

    AVAILABLE = "available"
    HELD = "held"


class LedgerAccount(Base):
    """Ledger account model for double-entry accounting.

    Each wallet has two ledger accounts:
    - available: funds available for spending
    - held: funds reserved/held for pending operations
    """

    __tablename__ = "ledger_accounts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[LedgerAccountKind] = mapped_column(
        Enum(LedgerAccountKind, name="ledger_account_kind"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="ledger_accounts",
    )
    journal_lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="ledger_account",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("wallet_id", "kind", name="uq_ledger_account_wallet_kind"),
    )

    def __repr__(self) -> str:
        return f"<LedgerAccount(id={self.id}, wallet_id={self.wallet_id}, kind={self.kind})>"
