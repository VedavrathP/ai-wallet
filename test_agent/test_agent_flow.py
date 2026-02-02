#!/usr/bin/env python3
"""Test the complete agent flow with mocked responses.

This demonstrates how an agent would interact with the wallet
in a realistic scenario.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add SDK to path for local testing
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

import httpx
from wallet_tool import WalletTool


class MockWalletServer:
    """Mock server that simulates wallet API responses."""
    
    def __init__(self):
        self.balance = {
            "available": "1000.00",
            "held": "0.00",
            "total": "1000.00"
        }
        self.holds = {}
        self.transfers = []
        self.request_count = 0
    
    def handle_request(self, method: str, url: str, **kwargs) -> MagicMock:
        """Handle a mock request and return appropriate response."""
        self.request_count += 1
        response = MagicMock()
        response.status_code = 200
        
        path = url.split("/v1")[-1] if "/v1" in url else url
        
        if path == "/wallets/me/balance":
            response.json.return_value = {
                "wallet_id": "wallet_alice",
                "available": self.balance["available"],
                "held": self.balance["held"],
                "total": self.balance["total"],
                "currency": "USD"
            }
        
        elif path == "/wallets/me":
            response.json.return_value = {
                "id": "wallet_alice",
                "type": "customer",
                "status": "active",
                "currency": "USD",
                "handle": "@alice",
                "metadata": {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        elif method == "POST" and path == "/transfers":
            body = kwargs.get("json", {})
            amount = float(body.get("amount", 0))
            available = float(self.balance["available"])
            
            if amount > available:
                response.status_code = 400
                response.json.return_value = {
                    "error_code": "INSUFFICIENT_FUNDS",
                    "message": f"Insufficient funds. Available: {available}"
                }
            else:
                self.balance["available"] = f"{available - amount:.2f}"
                self.balance["total"] = self.balance["available"]
                transfer_id = f"txn_{len(self.transfers) + 1}"
                self.transfers.append({
                    "id": transfer_id,
                    "amount": body.get("amount"),
                    "to": body.get("to")
                })
                response.json.return_value = {
                    "id": transfer_id,
                    "journal_entry_id": f"je_{len(self.transfers)}",
                    "from_wallet_id": "wallet_alice",
                    "to_wallet_id": "wallet_merchant",
                    "amount": body.get("amount"),
                    "currency": "USD",
                    "created_at": datetime.now().isoformat()
                }
        
        elif method == "POST" and path == "/holds":
            body = kwargs.get("json", {})
            amount = float(body.get("amount", 0))
            available = float(self.balance["available"])
            
            if amount > available:
                response.status_code = 400
                response.json.return_value = {
                    "error_code": "INSUFFICIENT_FUNDS",
                    "message": f"Insufficient funds. Available: {available}"
                }
            else:
                self.balance["available"] = f"{available - amount:.2f}"
                self.balance["held"] = f"{float(self.balance['held']) + amount:.2f}"
                hold_id = f"hold_{len(self.holds) + 1}"
                self.holds[hold_id] = {
                    "amount": amount,
                    "remaining": amount
                }
                response.json.return_value = {
                    "id": hold_id,
                    "wallet_id": "wallet_alice",
                    "amount": body.get("amount"),
                    "remaining_amount": body.get("amount"),
                    "currency": "USD",
                    "status": "active",
                    "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                    "created_at": datetime.now().isoformat()
                }
        
        elif method == "POST" and "/capture" in path:
            hold_id = path.split("/holds/")[1].split("/capture")[0]
            body = kwargs.get("json", {})
            
            if hold_id in self.holds:
                hold = self.holds[hold_id]
                capture_amount = float(body.get("amount", hold["remaining"]))
                
                if capture_amount > hold["remaining"]:
                    response.status_code = 400
                    response.json.return_value = {
                        "error_code": "AMOUNT_EXCEEDS_HOLD",
                        "message": f"Amount exceeds remaining hold"
                    }
                else:
                    hold["remaining"] -= capture_amount
                    self.balance["held"] = f"{float(self.balance['held']) - capture_amount:.2f}"
                    response.json.return_value = {
                        "id": f"cap_{hold_id}",
                        "hold_id": hold_id,
                        "to_wallet_id": "wallet_merchant",
                        "amount": f"{capture_amount:.2f}",
                        "currency": "USD",
                        "journal_entry_id": "je_cap",
                        "created_at": datetime.now().isoformat()
                    }
            else:
                response.status_code = 404
                response.json.return_value = {
                    "error_code": "HOLD_NOT_FOUND",
                    "message": "Hold not found"
                }
        
        elif method == "POST" and "/release" in path:
            hold_id = path.split("/holds/")[1].split("/release")[0]
            body = kwargs.get("json", {})
            
            if hold_id in self.holds:
                hold = self.holds[hold_id]
                release_amount = float(body.get("amount", hold["remaining"]))
                
                if release_amount > hold["remaining"]:
                    response.status_code = 400
                    response.json.return_value = {
                        "error_code": "AMOUNT_EXCEEDS_HOLD",
                        "message": f"Amount exceeds remaining hold"
                    }
                else:
                    hold["remaining"] -= release_amount
                    self.balance["held"] = f"{float(self.balance['held']) - release_amount:.2f}"
                    self.balance["available"] = f"{float(self.balance['available']) + release_amount:.2f}"
                    response.json.return_value = {
                        "id": f"rel_{hold_id}",
                        "hold_id": hold_id,
                        "amount": f"{release_amount:.2f}",
                        "currency": "USD",
                        "journal_entry_id": "je_rel",
                        "created_at": datetime.now().isoformat()
                    }
            else:
                response.status_code = 404
                response.json.return_value = {
                    "error_code": "HOLD_NOT_FOUND",
                    "message": "Hold not found"
                }
        
        return response


def run_agent_scenario():
    """Run a realistic agent scenario."""
    print("\n" + "=" * 60)
    print("  AGENT WALLET - SIMULATED FLOW TEST")
    print("=" * 60)
    print("\nThis test simulates a realistic agent workflow:")
    print("1. Agent checks balance")
    print("2. Agent makes a purchase (transfer)")
    print("3. Agent creates a hold for a reservation")
    print("4. Agent partially captures the hold")
    print("5. Agent releases the remaining hold")
    print()
    
    # Create mock server
    mock_server = MockWalletServer()
    
    # Patch httpx.Client to use our mock
    original_request = httpx.Client.request
    
    def mock_request(self, method, url, **kwargs):
        return mock_server.handle_request(method, url, **kwargs)
    
    with patch.object(httpx.Client, "request", mock_request):
        wallet = WalletTool(api_key="test_key", base_url="http://mock")
        
        # Step 1: Check initial balance
        print("=" * 40)
        print("STEP 1: Check Initial Balance")
        print("=" * 40)
        result = wallet.get_balance()
        print(f"Result: {result}")
        assert result["success"]
        assert result["available"] == "1000.00"
        print("✅ Balance check successful\n")
        
        # Step 2: Make a transfer
        print("=" * 40)
        print("STEP 2: Transfer $50 to @merchant")
        print("=" * 40)
        result = wallet.transfer(
            to_handle="@merchant",
            amount="50.00",
            reference_id="order_001"
        )
        print(f"Result: {result}")
        assert result["success"]
        print("✅ Transfer successful\n")
        
        # Check balance after transfer
        result = wallet.get_balance()
        print(f"Balance after transfer: {result}")
        assert result["available"] == "950.00"
        print("✅ Balance updated correctly\n")
        
        # Step 3: Create a hold
        print("=" * 40)
        print("STEP 3: Create $200 Hold")
        print("=" * 40)
        result = wallet.create_hold(amount="200.00")
        print(f"Result: {result}")
        assert result["success"]
        hold_id = result["hold_id"]
        print(f"✅ Hold created: {hold_id}\n")
        
        # Check balance after hold
        result = wallet.get_balance()
        print(f"Balance after hold: {result}")
        assert result["available"] == "750.00"
        assert result["held"] == "200.00"
        print("✅ Balance shows held amount\n")
        
        # Step 4: Partial capture
        print("=" * 40)
        print("STEP 4: Capture $150 of Hold")
        print("=" * 40)
        result = wallet.capture_hold(
            hold_id=hold_id,
            to_handle="@merchant",
            amount="150.00"
        )
        print(f"Result: {result}")
        assert result["success"]
        print("✅ Partial capture successful\n")
        
        # Check balance after capture
        result = wallet.get_balance()
        print(f"Balance after capture: {result}")
        assert result["held"] == "50.00"
        print("✅ Held amount reduced\n")
        
        # Step 5: Release remaining
        print("=" * 40)
        print("STEP 5: Release Remaining $50")
        print("=" * 40)
        result = wallet.release_hold(hold_id=hold_id)
        print(f"Result: {result}")
        assert result["success"]
        print("✅ Release successful\n")
        
        # Final balance check
        result = wallet.get_balance()
        print(f"Final balance: {result}")
        assert result["available"] == "800.00"
        assert result["held"] == "0.00"
        print("✅ Final balance correct\n")
        
        # Step 6: Test insufficient funds
        print("=" * 40)
        print("STEP 6: Test Insufficient Funds")
        print("=" * 40)
        result = wallet.transfer(
            to_handle="@merchant",
            amount="10000.00"
        )
        print(f"Result: {result}")
        assert not result["success"]
        assert result["error_code"] == "INSUFFICIENT_FUNDS"
        print("✅ Insufficient funds handled correctly\n")
    
    print("=" * 60)
    print("  ALL SCENARIO TESTS PASSED! ✅")
    print("=" * 60)
    print(f"\nTotal API requests made: {mock_server.request_count}")
    print(f"Transfers completed: {len(mock_server.transfers)}")
    print(f"Holds created: {len(mock_server.holds)}")
    print("\nThe agent successfully completed a realistic workflow!")


if __name__ == "__main__":
    try:
        run_agent_scenario()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
