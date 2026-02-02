"""Agent Wallet SDK - Python client for the Agent Wallet API."""

from agent_wallet.client import WalletClient
from agent_wallet.exceptions import (
    ConflictIdempotency,
    CurrencyMismatch,
    ForbiddenScope,
    InsufficientFunds,
    LimitExceeded,
    RecipientNotFound,
    WalletAPIError,
)
from agent_wallet.types import (
    Balance,
    Capture,
    Deposit,
    Hold,
    PaginatedTransactions,
    PaymentIntent,
    PaymentResult,
    Refund,
    Release,
    Transaction,
    Transfer,
    Wallet,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "WalletClient",
    # Exceptions
    "WalletAPIError",
    "InsufficientFunds",
    "ForbiddenScope",
    "LimitExceeded",
    "RecipientNotFound",
    "CurrencyMismatch",
    "ConflictIdempotency",
    # Types
    "Balance",
    "Wallet",
    "Transaction",
    "PaginatedTransactions",
    "Transfer",
    "Hold",
    "Capture",
    "Release",
    "PaymentIntent",
    "PaymentResult",
    "Refund",
    "Deposit",
]
