#!/usr/bin/env python3
"""Test script to verify wallet operations work correctly.

This script tests the wallet tool by performing various operations
and verifying the results.
"""

import sys
from pathlib import Path

# Add SDK to path for local testing
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

from wallet_tool import WalletTool


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(operation: str, result: dict):
    """Print operation result."""
    status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
    print(f"\n{operation}: {status}")
    for key, value in result.items():
        if key != "success":
            print(f"  {key}: {value}")


def test_wallet_operations():
    """Run a series of wallet operation tests."""
    
    # API keys from seed script
    ALICE_API_KEY = "aw_alice_test_key_12345678901234567890"
    MERCHANT_API_KEY = "aw_merchant_test_key_12345678901234567890"
    
    print_header("WALLET TOOL TEST SUITE")
    print("\nThis test will verify the wallet operations work correctly.")
    print("Make sure the service is running: docker-compose up -d")
    print("And the database is seeded: python -m agent_wallet_service.scripts.seed")
    
    # Initialize wallet tools
    print("\n📦 Initializing wallet tools...")
    alice_wallet = WalletTool(api_key=ALICE_API_KEY)
    merchant_wallet = WalletTool(api_key=MERCHANT_API_KEY)
    
    # Test 1: Get wallet info
    print_header("TEST 1: Get Wallet Info")
    result = alice_wallet.get_wallet_info()
    print_result("Alice's Wallet Info", result)
    
    result = merchant_wallet.get_wallet_info()
    print_result("Merchant's Wallet Info", result)
    
    # Test 2: Check balance
    print_header("TEST 2: Check Balance")
    result = alice_wallet.get_balance()
    print_result("Alice's Balance", result)
    initial_balance = result.get("available", "0")
    
    result = merchant_wallet.get_balance()
    print_result("Merchant's Balance", result)
    
    # Test 3: Transfer funds
    print_header("TEST 3: Transfer Funds")
    result = alice_wallet.transfer(
        to_handle="@acme_store",
        amount="25.00",
        reference_id="test_transfer_001"
    )
    print_result("Transfer $25 to @acme_store", result)
    
    # Check balances after transfer
    print("\n📊 Balances after transfer:")
    result = alice_wallet.get_balance()
    print_result("Alice's Balance", result)
    
    result = merchant_wallet.get_balance()
    print_result("Merchant's Balance", result)
    
    # Test 4: Create a hold
    print_header("TEST 4: Create Hold")
    result = alice_wallet.create_hold(
        amount="50.00",
        expires_in_seconds=3600
    )
    print_result("Create $50 Hold", result)
    hold_id = result.get("hold_id")
    
    # Check balance after hold
    print("\n📊 Balance after hold:")
    result = alice_wallet.get_balance()
    print_result("Alice's Balance (should show $50 held)", result)
    
    # Test 5: Partial capture
    print_header("TEST 5: Partial Capture")
    if hold_id:
        result = alice_wallet.capture_hold(
            hold_id=hold_id,
            to_handle="@acme_store",
            amount="30.00"
        )
        print_result("Capture $30 of $50 hold", result)
        
        # Check balance after partial capture
        print("\n📊 Balance after partial capture:")
        result = alice_wallet.get_balance()
        print_result("Alice's Balance", result)
    else:
        print("❌ Skipping capture test - no hold_id")
    
    # Test 6: Release remaining hold
    print_header("TEST 6: Release Remaining Hold")
    if hold_id:
        result = alice_wallet.release_hold(hold_id=hold_id)
        print_result("Release remaining $20", result)
        
        # Check final balance
        print("\n📊 Final balance after release:")
        result = alice_wallet.get_balance()
        print_result("Alice's Balance", result)
    else:
        print("❌ Skipping release test - no hold_id")
    
    # Test 7: Insufficient funds
    print_header("TEST 7: Insufficient Funds (Expected to Fail)")
    result = alice_wallet.transfer(
        to_handle="@acme_store",
        amount="999999.00"
    )
    print_result("Transfer $999,999 (should fail)", result)
    
    # Test 8: Idempotency
    print_header("TEST 8: Idempotency Test")
    idempotency_key = "test_idempotency_12345"
    
    result1 = alice_wallet.transfer(
        to_handle="@acme_store",
        amount="10.00",
        idempotency_key=idempotency_key
    )
    print_result("First transfer with key", result1)
    transfer_id_1 = result1.get("transfer_id")
    
    result2 = alice_wallet.transfer(
        to_handle="@acme_store",
        amount="10.00",
        idempotency_key=idempotency_key
    )
    print_result("Second transfer with same key", result2)
    transfer_id_2 = result2.get("transfer_id")
    
    if transfer_id_1 and transfer_id_2:
        if transfer_id_1 == transfer_id_2:
            print("\n✅ Idempotency working: Same transfer ID returned")
        else:
            print("\n❌ Idempotency failed: Different transfer IDs")
    
    # Summary
    print_header("TEST SUMMARY")
    print("""
Tests completed! Review the results above.

Expected outcomes:
✅ Wallet info should return handle and type
✅ Balance should show available, held, and total
✅ Transfer should succeed and update balances
✅ Hold should reserve funds (move to held)
✅ Partial capture should transfer part of hold
✅ Release should return remaining to available
✅ Insufficient funds should fail with error
✅ Idempotency should return same transfer ID
""")


if __name__ == "__main__":
    try:
        test_wallet_operations()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\nMake sure:")
        print("1. Docker containers are running: docker-compose up -d")
        print("2. Database is seeded: docker-compose exec service python -m agent_wallet_service.scripts.seed")
        raise
