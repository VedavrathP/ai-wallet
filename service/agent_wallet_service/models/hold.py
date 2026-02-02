"""Hold model."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.capture import Capture
    from agent_wallet_service.models.wallet import Wallet


class HoldStatus(str, enum.Enum):
    """Hold status enumeration."""

    ACTIVE = "active"
    CAPTURED = "captured"
    RELEASED = "released"
    EXPIRED = "expired"


class Hold(Base):
    """Hold model representing a reservation of funds.

    Holds reserve funds from the available balance to the held balance.
    They can be captured (transferred to another wallet) or released
    (returned to available balance).
    """

    __tablename__ = "holds"

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
    amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
        nullable=False,
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    status: Mapped[HoldStatus] = mapped_column(
        Enum(HoldStatus, name="hold_status"),
        nullable=False,
        default=HoldStatus.ACTIVE,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_by_api_key_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
    journal_entry_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="holds",
    )
    captures: Mapped[list["Capture"]] = relationship(
        "Capture",
        back_populates="hold",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            "created_by_api_key_id",
            name="uq_hold_idempotency",
        ),
    )

    def __repr__(self) -> str:
        return f"<Hold(id={self.id}, amount={self.amount}, status={self.status})>"

    @property
    def is_expired(self) -> bool:
        """Check if the hold has expired."""
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def can_capture(self) -> bool:
        """Check if the hold can be captured."""
        return self.status == HoldStatus.ACTIVE and not self.is_expired and self.remaining_amount > 0

    @property
    def can_release(self) -> bool:
        """Check if the hold can be released."""
        return self.status == HoldStatus.ACTIVE and self.remaining_amount > 0
