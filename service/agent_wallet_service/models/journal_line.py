"""Journal line model."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.journal_entry import JournalEntry
    from agent_wallet_service.models.ledger_account import LedgerAccount


class JournalLineDirection(str, enum.Enum):
    """Journal line direction enumeration."""

    DEBIT = "debit"
    CREDIT = "credit"


class JournalLine(Base):
    """Journal line model representing a single debit or credit entry.

    Each journal entry has multiple lines that must balance:
    sum(debits) == sum(credits)
    """

    __tablename__ = "journal_lines"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    journal_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ledger_account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ledger_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[JournalLineDirection] = mapped_column(
        Enum(JournalLineDirection, name="journal_line_direction"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
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
    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry",
        back_populates="lines",
    )
    ledger_account: Mapped["LedgerAccount"] = relationship(
        "LedgerAccount",
        back_populates="journal_lines",
    )

    def __repr__(self) -> str:
        return f"<JournalLine(id={self.id}, direction={self.direction}, amount={self.amount})>"
