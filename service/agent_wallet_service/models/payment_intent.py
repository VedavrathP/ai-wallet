"""Payment intent model."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.wallet import Wallet


class PaymentIntentStatus(str, enum.Enum):
    """Payment intent status enumeration."""

    REQUIRES_PAYMENT = "requires_payment"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentIntent(Base):
    """Payment intent model for commerce-safe payments.

    Merchants create payment intents, and payers pay them.
    This is the safest path for agent payments as it ensures
    the merchant explicitly requests the payment.
    """

    __tablename__ = "payment_intents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    merchant_wallet_id: Mapped[UUID] = mapped_column(
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
    status: Mapped[PaymentIntentStatus] = mapped_column(
        Enum(PaymentIntentStatus, name="payment_intent_status"),
        nullable=False,
        default=PaymentIntentStatus.REQUIRES_PAYMENT,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    payer_wallet_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="SET NULL"),
        nullable=True,
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
    merchant_wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="payment_intents",
        foreign_keys=[merchant_wallet_id],
    )

    def __repr__(self) -> str:
        return f"<PaymentIntent(id={self.id}, amount={self.amount}, status={self.status})>"

    @property
    def is_expired(self) -> bool:
        """Check if the payment intent has expired."""
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def can_pay(self) -> bool:
        """Check if the payment intent can be paid."""
        return self.status == PaymentIntentStatus.REQUIRES_PAYMENT and not self.is_expired
