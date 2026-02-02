"""Wallet model."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.api_key import APIKey
    from agent_wallet_service.models.external_identity import ExternalIdentity
    from agent_wallet_service.models.hold import Hold
    from agent_wallet_service.models.ledger_account import LedgerAccount
    from agent_wallet_service.models.payment_intent import PaymentIntent


class WalletType(str, enum.Enum):
    """Wallet type enumeration."""

    CUSTOMER = "customer"
    BUSINESS = "business"
    SYSTEM = "system"


class WalletStatus(str, enum.Enum):
    """Wallet status enumeration."""

    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Wallet(Base):
    """Wallet model representing a financial account."""

    __tablename__ = "wallets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    type: Mapped[WalletType] = mapped_column(
        Enum(WalletType, name="wallet_type"),
        nullable=False,
    )
    status: Mapped[WalletStatus] = mapped_column(
        Enum(WalletStatus, name="wallet_status"),
        nullable=False,
        default=WalletStatus.ACTIVE,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    handle: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )
    wallet_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    ledger_accounts: Mapped[list["LedgerAccount"]] = relationship(
        "LedgerAccount",
        back_populates="wallet",
        lazy="selectin",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="wallet",
        lazy="selectin",
    )
    external_identities: Mapped[list["ExternalIdentity"]] = relationship(
        "ExternalIdentity",
        back_populates="wallet",
        lazy="selectin",
    )
    holds: Mapped[list["Hold"]] = relationship(
        "Hold",
        back_populates="wallet",
        lazy="selectin",
    )
    payment_intents: Mapped[list["PaymentIntent"]] = relationship(
        "PaymentIntent",
        back_populates="merchant_wallet",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_wallets_created_at", "created_at"),
        Index("ix_wallets_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, handle={self.handle}, type={self.type})>"
