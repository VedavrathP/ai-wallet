# Changelog

All notable changes to the Agent Wallet SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-31

### Added

- Initial release of the Agent Wallet SDK
- `WalletClient` class with all core methods:
  - `balance()` - Get wallet balance
  - `transactions()` - List transactions with pagination
  - `transfer()` - Transfer funds to another wallet
  - `hold()` - Create a hold/reservation
  - `capture()` - Capture a hold
  - `release()` - Release a hold
  - `create_payment_intent()` - Create a payment intent
  - `pay_payment_intent()` - Pay a payment intent
  - `refund()` - Request a refund
- Exception classes for error handling:
  - `InsufficientFunds`
  - `ForbiddenScope`
  - `LimitExceeded`
  - `RecipientNotFound`
  - `CurrencyMismatch`
  - `ConflictIdempotency`
- Automatic retry with exponential backoff for network errors
- Idempotency key support for all write operations
- Type-safe responses using Pydantic models
