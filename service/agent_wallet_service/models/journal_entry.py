"""Journal entry model."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.api_key import APIKey
    from agent_wallet_service.models.journal_line import JournalLine


class JournalEntryType(str, enum.Enum):
    """Journal entry type enumeration."""

    DEPOSIT_EXTERNAL = "deposit_external"
    TRANSFER = "transfer"
    HOLD = "hold"
    CAPTURE = "capture"
    RELEASE = "release"
    REFUND = "refund"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"


class JournalEntryStatus(str, enum.Enum):
    """Journal entry status enumeration."""

    PENDING = "pending"
    POSTED = "posted"
    REVERSED = "reversed"
    FAILED = "failed"


class JournalEntry(Base):
    """Journal entry model for double-entry accounting.

    Every financial operation creates a journal entry with balanced
    debit and credit lines. Journal entries are immutable once posted.
    """

    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    type: Mapped[JournalEntryType] = mapped_column(
        Enum(JournalEntryType, name="journal_entry_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[JournalEntryStatus] = mapped_column(
        Enum(JournalEntryStatus, name="journal_entry_status"),
        nullable=False,
        default=JournalEntryStatus.PENDING,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
    reference_id: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        index=True,
    )
    created_by_api_key_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    entry_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Keep the column name in DB as "metadata"
        JSONB,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="journal_entry",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            "created_by_api_key_id",
            name="uq_journal_entry_idempotency",
        ),
    )

    def __repr__(self) -> str:
        return f"<JournalEntry(id={self.id}, type={self.type}, status={self.status})>"
