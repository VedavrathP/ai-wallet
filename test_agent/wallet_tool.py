"""Wallet tool for AI agents to interact with the Agent Wallet API."""

import sys
from pathlib import Path

# Add SDK to path for local testing
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

from typing import Any, Optional
from agent_wallet import WalletClient
from agent_wallet.exceptions import WalletAPIError


class WalletTool:
    """A tool wrapper for AI agents to interact with the Agent Wallet API.
    
    This class provides simple methods that can be called by an AI agent
    to perform wallet operations.
    """
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        """Initialize the wallet tool.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL of the wallet service
        """
        self.client = WalletClient(api_key=api_key, base_url=base_url)
    
    def get_balance(self) -> dict[str, Any]:
        """Get the current wallet balance.
        
        Returns:
            Dictionary with available, held, total, and currency
        """
        try:
            balance = self.client.balance()
            return {
                "success": True,
                "available": balance.available,
                "held": balance.held,
                "total": balance.total,
                "currency": balance.currency,
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e)}
    
    def transfer(
        self,
        to_handle: str,
        amount: str,
        currency: str = "USD",
        idempotency_key: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Transfer funds to another wallet.
        
        Args:
            to_handle: Recipient handle (e.g., "@merchant")
            amount: Amount to transfer (e.g., "25.00")
            currency: Currency code (default: USD)
            idempotency_key: Unique key for idempotent operation
            reference_id: Optional reference ID
            
        Returns:
            Dictionary with transfer result or error
        """
        import uuid
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        
        try:
            transfer = self.client.transfer(
                to_handle=to_handle,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
                reference_id=reference_id,
            )
            return {
                "success": True,
                "transfer_id": transfer.id,
                "from_wallet_id": transfer.from_wallet_id,
                "to_wallet_id": transfer.to_wallet_id,
                "amount": transfer.amount,
                "currency": transfer.currency,
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e), "error_code": e.error_code}
    
    def create_hold(
        self,
        amount: str,
        currency: str = "USD",
        idempotency_key: Optional[str] = None,
        expires_in_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Create a hold (reservation) on the wallet.
        
        Args:
            amount: Amount to hold
            currency: Currency code
            idempotency_key: Unique key for idempotent operation
            expires_in_seconds: Hold expiration time
            
        Returns:
            Dictionary with hold result or error
        """
        import uuid
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        
        try:
            hold = self.client.hold(
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
                expires_in_seconds=expires_in_seconds,
            )
            return {
                "success": True,
                "hold_id": hold.id,
                "amount": hold.amount,
                "remaining_amount": hold.remaining_amount,
                "status": hold.status,
                "expires_at": str(hold.expires_at),
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e), "error_code": e.error_code}
    
    def capture_hold(
        self,
        hold_id: str,
        to_handle: str,
        amount: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture a hold (transfer held funds to recipient).
        
        Args:
            hold_id: ID of the hold to capture
            to_handle: Recipient handle
            amount: Amount to capture (optional, defaults to full hold)
            idempotency_key: Unique key for idempotent operation
            
        Returns:
            Dictionary with capture result or error
        """
        import uuid
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        
        try:
            capture = self.client.capture(
                hold_id=hold_id,
                to_handle=to_handle,
                amount=amount,
                idempotency_key=idempotency_key,
            )
            return {
                "success": True,
                "capture_id": capture.id,
                "hold_id": capture.hold_id,
                "to_wallet_id": capture.to_wallet_id,
                "amount": capture.amount,
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e), "error_code": e.error_code}
    
    def release_hold(
        self,
        hold_id: str,
        amount: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Release a hold (return held funds to available).
        
        Args:
            hold_id: ID of the hold to release
            amount: Amount to release (optional, defaults to remaining)
            idempotency_key: Unique key for idempotent operation
            
        Returns:
            Dictionary with release result or error
        """
        import uuid
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        
        try:
            release = self.client.release(
                hold_id=hold_id,
                amount=amount,
                idempotency_key=idempotency_key,
            )
            return {
                "success": True,
                "release_id": release.id,
                "hold_id": release.hold_id,
                "amount": release.amount,
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e), "error_code": e.error_code}
    
    def get_wallet_info(self) -> dict[str, Any]:
        """Get wallet information.
        
        Returns:
            Dictionary with wallet info or error
        """
        try:
            wallet = self.client.me()
            return {
                "success": True,
                "wallet_id": wallet.id,
                "type": wallet.type,
                "status": wallet.status,
                "currency": wallet.currency,
                "handle": wallet.handle,
            }
        except WalletAPIError as e:
            return {"success": False, "error": str(e)}


# Tool definitions for function calling (OpenAI format)
WALLET_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Get the current wallet balance including available, held, and total amounts",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer",
            "description": "Transfer funds to another wallet by handle",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_handle": {
                        "type": "string",
                        "description": "Recipient handle (e.g., '@merchant')",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to transfer (e.g., '25.00')",
                    },
                    "reference_id": {
                        "type": "string",
                        "description": "Optional reference ID for the transfer",
                    },
                },
                "required": ["to_handle", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_hold",
            "description": "Create a hold/reservation on funds for later capture",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "string",
                        "description": "Amount to hold (e.g., '100.00')",
                    },
                    "expires_in_seconds": {
                        "type": "integer",
                        "description": "Hold expiration time in seconds (default: 3600)",
                    },
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_hold",
            "description": "Capture a hold to transfer the held funds to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "hold_id": {
                        "type": "string",
                        "description": "ID of the hold to capture",
                    },
                    "to_handle": {
                        "type": "string",
                        "description": "Recipient handle",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to capture (optional, defaults to full hold)",
                    },
                },
                "required": ["hold_id", "to_handle"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "release_hold",
            "description": "Release a hold to return the funds to available balance",
            "parameters": {
                "type": "object",
                "properties": {
                    "hold_id": {
                        "type": "string",
                        "description": "ID of the hold to release",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to release (optional, defaults to remaining)",
                    },
                },
                "required": ["hold_id"],
            },
        },
    },
]
