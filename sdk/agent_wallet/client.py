"""Agent Wallet API client."""

from typing import Any, Optional

import httpx

from agent_wallet.exceptions import raise_for_error_response
from agent_wallet.retry import RetryableClient
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
    Transfer,
    Wallet,
)


class WalletClient(RetryableClient):
    """Client for the Agent Wallet API.

    Args:
        api_key: API key for authentication
        base_url: Base URL of the Agent Wallet API
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for network errors
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def __enter__(self) -> "WalletClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method
            path: API path
            json: JSON body
            params: Query parameters
            idempotency_key: Idempotency key for the request

        Returns:
            Response data as dictionary

        Raises:
            WalletAPIError: If the API returns an error
        """
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        def make_request() -> httpx.Response:
            return self._client.request(
                method=method,
                url=path,
                json=json,
                params=params,
                headers=headers,
            )

        response = self._execute_with_retry(make_request)

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"message": response.text, "error_code": "UNKNOWN_ERROR"}
            raise_for_error_response(response.status_code, error_data)

        return response.json()

    def me(self) -> Wallet:
        """Get the current wallet information.

        Returns:
            Wallet information
        """
        data = self._request("GET", "/v1/wallets/me")
        return Wallet(**data)

    def balance(self) -> Balance:
        """Get the current wallet balance.

        Returns:
            Balance information with available, held, and total amounts
        """
        data = self._request("GET", "/v1/wallets/me/balance")
        return Balance(**data)

    def transactions(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        type: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> PaginatedTransactions:
        """List transactions for the current wallet.

        Args:
            cursor: Pagination cursor
            limit: Maximum number of transactions to return
            type: Filter by transaction type
            status: Filter by transaction status
            from_date: Filter by start date (ISO format)
            to_date: Filter by end date (ISO format)

        Returns:
            Paginated list of transactions
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if type:
            params["type"] = type
        if status:
            params["status"] = status
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        data = self._request("GET", "/v1/wallets/me/transactions", params=params)
        return PaginatedTransactions(**data)

    def transfer(
        self,
        amount: str,
        currency: str,
        idempotency_key: str,
        to_handle: Optional[str] = None,
        to_wallet_id: Optional[str] = None,
        to_external_id: Optional[tuple[str, str]] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Transfer:
        """Transfer funds to another wallet.

        Args:
            amount: Amount to transfer (as string, e.g., "12.50")
            currency: Currency code (e.g., "USD")
            idempotency_key: Unique key to ensure idempotent operation
            to_handle: Recipient handle (e.g., "@merchant")
            to_wallet_id: Recipient wallet ID
            to_external_id: Tuple of (provider, external_user_id)
            reference_id: Optional reference ID for the transfer
            metadata: Optional metadata dictionary

        Returns:
            Transfer result

        Note:
            Exactly one of to_handle, to_wallet_id, or to_external_id must be provided.
        """
        to: dict[str, Any]
        if to_handle:
            to = {"type": "handle", "value": to_handle}
        elif to_wallet_id:
            to = {"type": "wallet_id", "value": to_wallet_id}
        elif to_external_id:
            to = {
                "type": "external_id",
                "value": {"provider": to_external_id[0], "external_user_id": to_external_id[1]},
            }
        else:
            raise ValueError("One of to_handle, to_wallet_id, or to_external_id must be provided")

        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "to": to,
            "idempotency_key": idempotency_key,
        }
        if reference_id:
            body["reference_id"] = reference_id
        if metadata:
            body["metadata"] = metadata

        data = self._request("POST", "/v1/transfers", json=body, idempotency_key=idempotency_key)
        return Transfer(**data)

    def hold(
        self,
        amount: str,
        currency: str,
        idempotency_key: str,
        expires_in_seconds: int = 3600,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Hold:
        """Create a hold (reservation) on the wallet.

        Args:
            amount: Amount to hold (as string, e.g., "50.00")
            currency: Currency code (e.g., "USD")
            idempotency_key: Unique key to ensure idempotent operation
            expires_in_seconds: Hold expiration time in seconds (default: 1 hour)
            metadata: Optional metadata dictionary

        Returns:
            Hold result
        """
        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "idempotency_key": idempotency_key,
            "expires_in_seconds": expires_in_seconds,
        }
        if metadata:
            body["metadata"] = metadata

        data = self._request("POST", "/v1/holds", json=body, idempotency_key=idempotency_key)
        return Hold(**data)

    def capture(
        self,
        hold_id: str,
        idempotency_key: str,
        to_handle: Optional[str] = None,
        to_wallet_id: Optional[str] = None,
        to_external_id: Optional[tuple[str, str]] = None,
        amount: Optional[str] = None,
    ) -> Capture:
        """Capture a hold (partial or full).

        Args:
            hold_id: ID of the hold to capture
            idempotency_key: Unique key to ensure idempotent operation
            to_handle: Recipient handle (e.g., "@merchant")
            to_wallet_id: Recipient wallet ID
            to_external_id: Tuple of (provider, external_user_id)
            amount: Amount to capture (optional, defaults to remaining hold amount)

        Returns:
            Capture result

        Note:
            Exactly one of to_handle, to_wallet_id, or to_external_id must be provided.
        """
        to: dict[str, Any]
        if to_handle:
            to = {"type": "handle", "value": to_handle}
        elif to_wallet_id:
            to = {"type": "wallet_id", "value": to_wallet_id}
        elif to_external_id:
            to = {
                "type": "external_id",
                "value": {"provider": to_external_id[0], "external_user_id": to_external_id[1]},
            }
        else:
            raise ValueError("One of to_handle, to_wallet_id, or to_external_id must be provided")

        body: dict[str, Any] = {
            "to": to,
            "idempotency_key": idempotency_key,
        }
        if amount:
            body["amount"] = amount

        data = self._request(
            "POST",
            f"/v1/holds/{hold_id}/capture",
            json=body,
            idempotency_key=idempotency_key,
        )
        return Capture(**data)

    def release(
        self,
        hold_id: str,
        idempotency_key: str,
        amount: Optional[str] = None,
    ) -> Release:
        """Release a hold (partial or full).

        Args:
            hold_id: ID of the hold to release
            idempotency_key: Unique key to ensure idempotent operation
            amount: Amount to release (optional, defaults to remaining hold amount)

        Returns:
            Release result
        """
        body: dict[str, Any] = {
            "idempotency_key": idempotency_key,
        }
        if amount:
            body["amount"] = amount

        data = self._request(
            "POST",
            f"/v1/holds/{hold_id}/release",
            json=body,
            idempotency_key=idempotency_key,
        )
        return Release(**data)

    def create_payment_intent(
        self,
        amount: str,
        currency: str,
        expires_in_seconds: int = 900,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PaymentIntent:
        """Create a payment intent (merchant operation).

        Args:
            amount: Amount for the payment intent (as string, e.g., "50.00")
            currency: Currency code (e.g., "USD")
            expires_in_seconds: Expiration time in seconds (default: 15 minutes)
            metadata: Optional metadata dictionary

        Returns:
            Payment intent
        """
        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "expires_in_seconds": expires_in_seconds,
        }
        if metadata:
            body["metadata"] = metadata

        data = self._request("POST", "/v1/payment_intents", json=body)
        return PaymentIntent(**data)

    def pay_payment_intent(
        self,
        intent_id: str,
        idempotency_key: str,
    ) -> PaymentResult:
        """Pay a payment intent.

        Args:
            intent_id: ID of the payment intent to pay
            idempotency_key: Unique key to ensure idempotent operation

        Returns:
            Payment result
        """
        body: dict[str, Any] = {
            "idempotency_key": idempotency_key,
        }

        data = self._request(
            "POST",
            f"/v1/payment_intents/{intent_id}/pay",
            json=body,
            idempotency_key=idempotency_key,
        )
        return PaymentResult(**data)

    def refund(
        self,
        capture_id: str,
        idempotency_key: str,
        amount: Optional[str] = None,
    ) -> Refund:
        """Request a refund against a capture.

        Args:
            capture_id: ID of the capture to refund
            idempotency_key: Unique key to ensure idempotent operation
            amount: Amount to refund (optional, defaults to full capture amount)

        Returns:
            Refund result
        """
        body: dict[str, Any] = {
            "capture_id": capture_id,
            "idempotency_key": idempotency_key,
        }
        if amount:
            body["amount"] = amount

        data = self._request("POST", "/v1/refunds", json=body, idempotency_key=idempotency_key)
        return Refund(**data)

    # ==================== Admin Operations ====================
    # These require admin:deposits scope

    def deposit(
        self,
        amount: str,
        currency: str,
        idempotency_key: str,
        wallet_id: Optional[str] = None,
        handle: Optional[str] = None,
        external_reference: Optional[str] = None,
        payment_method: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Deposit:
        """Load funds into a wallet (admin operation).

        This is used to credit a wallet after confirming payment from an
        external source (e.g., Stripe webhook, bank transfer confirmation).

        Args:
            amount: Amount to deposit (as string, e.g., "100.00")
            currency: Currency code (e.g., "USD")
            idempotency_key: Unique key to ensure idempotent operation
            wallet_id: Target wallet ID (use this OR handle, not both)
            handle: Target wallet handle (e.g., "@alice")
            external_reference: Reference from external payment system
            payment_method: How the deposit was funded (bank_transfer, card, etc.)
            metadata: Optional metadata dictionary

        Returns:
            Deposit result

        Note:
            Requires admin:deposits scope.
            Exactly one of wallet_id or handle must be provided.
        """
        if not wallet_id and not handle:
            raise ValueError("One of wallet_id or handle must be provided")
        if wallet_id and handle:
            raise ValueError("Provide wallet_id OR handle, not both")

        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "idempotency_key": idempotency_key,
        }
        if wallet_id:
            body["wallet_id"] = wallet_id
        if handle:
            body["handle"] = handle
        if external_reference:
            body["external_reference"] = external_reference
        if payment_method:
            body["payment_method"] = payment_method
        if metadata:
            body["metadata"] = metadata

        data = self._request(
            "POST", "/admin/deposits", json=body, idempotency_key=idempotency_key
        )
        return Deposit(**data)
