"""Capture model."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.hold import Hold
    from agent_wallet_service.models.refund import Refund


class Capture(Base):
    """Capture model representing a captured hold.

    When a hold is captured, funds move from the held balance
    to the recipient's available balance.
    """

    __tablename__ = "captures"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    hold_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("holds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_wallet_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    journal_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
        nullable=False,
        default=Decimal("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    hold: Mapped["Hold"] = relationship(
        "Hold",
        back_populates="captures",
    )
    refunds: Mapped[list["Refund"]] = relationship(
        "Refund",
        back_populates="capture",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Capture(id={self.id}, amount={self.amount})>"

    @property
    def refundable_amount(self) -> Decimal:
        """Get the amount that can still be refunded."""
        return self.amount - self.refunded_amount
