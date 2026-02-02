#!/usr/bin/env python3
"""Standalone test for the SDK components (no server required).

This test verifies the SDK classes work correctly without needing
the actual service to be running.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add SDK to path for local testing
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_exceptions():
    """Test exception classes."""
    print_header("TEST: Exception Classes")
    
    from agent_wallet.exceptions import (
        InsufficientFunds,
        ForbiddenScope,
        LimitExceeded,
        RecipientNotFound,
        CurrencyMismatch,
        ConflictIdempotency,
        WalletAPIError,
        raise_for_error_response,
    )
    
    # Test InsufficientFunds
    exc = InsufficientFunds(message="Not enough funds", details={"available": "100"})
    assert exc.status_code == 400
    assert exc.error_code == "INSUFFICIENT_FUNDS"
    print("✅ InsufficientFunds exception works correctly")
    
    # Test ForbiddenScope
    exc = ForbiddenScope(message="Missing scope")
    assert exc.status_code == 403
    assert exc.error_code == "FORBIDDEN_SCOPE"
    print("✅ ForbiddenScope exception works correctly")
    
    # Test raise_for_error_response
    try:
        raise_for_error_response(400, {
            "error_code": "INSUFFICIENT_FUNDS",
            "message": "Not enough funds"
        })
        assert False, "Should have raised exception"
    except InsufficientFunds as e:
        assert e.message == "Not enough funds"
        print("✅ raise_for_error_response maps errors correctly")
    
    print("\n✅ All exception tests passed!")


def test_types():
    """Test type definitions."""
    print_header("TEST: Type Definitions")
    
    from agent_wallet.types import (
        Balance,
        Wallet,
        Transfer,
        Hold,
        Capture,
        Release,
        PaymentIntent,
        PaymentResult,
        Refund,
    )
    
    # Test Balance
    balance = Balance(
        wallet_id="wallet_123",
        available="1000.00",
        held="50.00",
        total="1050.00",
        currency="USD"
    )
    assert balance.available == "1000.00"
    assert balance.currency == "USD"
    print("✅ Balance type works correctly")
    
    # Test Wallet
    wallet = Wallet(
        id="wallet_123",
        type="customer",
        status="active",
        currency="USD",
        handle="@alice",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert wallet.handle == "@alice"
    print("✅ Wallet type works correctly")
    
    # Test Transfer
    transfer = Transfer(
        id="txn_123",
        journal_entry_id="je_123",
        from_wallet_id="wallet_1",
        to_wallet_id="wallet_2",
        amount="50.00",
        currency="USD",
        created_at=datetime.now()
    )
    assert transfer.amount == "50.00"
    print("✅ Transfer type works correctly")
    
    # Test Hold
    hold = Hold(
        id="hold_123",
        wallet_id="wallet_1",
        amount="100.00",
        remaining_amount="100.00",
        currency="USD",
        status="active",
        expires_at=datetime.now(),
        created_at=datetime.now()
    )
    assert hold.status == "active"
    print("✅ Hold type works correctly")
    
    print("\n✅ All type tests passed!")


def test_retry_logic():
    """Test retry logic."""
    print_header("TEST: Retry Logic")
    
    from agent_wallet.retry import (
        calculate_backoff,
        with_retry,
        RetryableClient,
        RETRYABLE_STATUS_CODES,
    )
    
    # Test exponential backoff
    delay_0 = calculate_backoff(0, base_delay=1.0, jitter=False)
    delay_1 = calculate_backoff(1, base_delay=1.0, jitter=False)
    delay_2 = calculate_backoff(2, base_delay=1.0, jitter=False)
    
    assert delay_0 == 1.0
    assert delay_1 == 2.0
    assert delay_2 == 4.0
    print("✅ Exponential backoff works correctly")
    
    # Test max delay cap
    delay = calculate_backoff(10, base_delay=1.0, max_delay=5.0, jitter=False)
    assert delay == 5.0
    print("✅ Max delay cap works correctly")
    
    # Test retryable status codes
    assert 502 in RETRYABLE_STATUS_CODES
    assert 503 in RETRYABLE_STATUS_CODES
    assert 504 in RETRYABLE_STATUS_CODES
    assert 400 not in RETRYABLE_STATUS_CODES
    print("✅ Retryable status codes defined correctly")
    
    # Test retry decorator
    call_count = 0
    
    @with_retry(max_retries=2, base_delay=0.01)
    def successful_func():
        nonlocal call_count
        call_count += 1
        return "success"
    
    result = successful_func()
    assert result == "success"
    assert call_count == 1
    print("✅ Retry decorator works on success")
    
    print("\n✅ All retry tests passed!")


def test_client_initialization():
    """Test client initialization."""
    print_header("TEST: Client Initialization")
    
    from agent_wallet import WalletClient
    
    # Test basic initialization
    client = WalletClient(
        api_key="test_key",
        base_url="http://localhost:8000"
    )
    assert client.api_key == "test_key"
    assert client.base_url == "http://localhost:8000"
    print("✅ Client initializes correctly")
    
    # Test with custom timeout
    client = WalletClient(
        api_key="test_key",
        base_url="http://localhost:8000",
        timeout=60.0
    )
    assert client.timeout == 60.0
    print("✅ Client accepts custom timeout")
    
    # Test with custom retries
    client = WalletClient(
        api_key="test_key",
        base_url="http://localhost:8000",
        max_retries=5
    )
    assert client.max_retries == 5
    print("✅ Client accepts custom max_retries")
    
    client.close()
    print("✅ Client closes correctly")
    
    print("\n✅ All client initialization tests passed!")


def test_wallet_tool():
    """Test the wallet tool wrapper."""
    print_header("TEST: Wallet Tool Wrapper")
    
    from wallet_tool import WalletTool, WALLET_TOOLS
    import httpx
    
    # Test tool definitions exist
    assert len(WALLET_TOOLS) > 0
    tool_names = [t["function"]["name"] for t in WALLET_TOOLS]
    assert "get_balance" in tool_names
    assert "transfer" in tool_names
    assert "create_hold" in tool_names
    assert "capture_hold" in tool_names
    assert "release_hold" in tool_names
    print("✅ Tool definitions are complete")
    
    # Test tool initialization
    with patch.object(httpx.Client, "__init__", return_value=None):
        with patch.object(httpx.Client, "close"):
            tool = WalletTool(api_key="test_key", base_url="http://test")
            assert tool.client is not None
            print("✅ WalletTool initializes correctly")
    
    print("\n✅ All wallet tool tests passed!")


def test_simple_agent():
    """Test the simple agent."""
    print_header("TEST: Simple Agent")
    
    from simple_agent import SimpleWalletAgent
    import httpx
    
    # Mock the HTTP client
    with patch.object(httpx.Client, "__init__", return_value=None):
        with patch.object(httpx.Client, "close"):
            with patch.object(httpx.Client, "request") as mock_request:
                # Mock balance response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "wallet_id": "wallet_123",
                    "available": "1000.00",
                    "held": "0.00",
                    "total": "1000.00",
                    "currency": "USD"
                }
                mock_request.return_value = mock_response
                
                agent = SimpleWalletAgent(api_key="test_key")
                
                # Test balance command
                response = agent.process_command("check balance")
                assert "1000.00" in response
                print("✅ Agent handles balance command")
                
                # Test help command
                response = agent.process_command("help")
                assert "Wallet Agent Commands" in response
                print("✅ Agent handles help command")
                
                # Test unknown command
                response = agent.process_command("do something random")
                assert "didn't understand" in response
                print("✅ Agent handles unknown commands")
    
    print("\n✅ All agent tests passed!")


def run_all_tests():
    """Run all standalone tests."""
    print("\n" + "=" * 60)
    print("  AGENT WALLET SDK - STANDALONE TESTS")
    print("=" * 60)
    print("\nThese tests verify SDK components without requiring")
    print("the service to be running.\n")
    
    try:
        test_exceptions()
        test_types()
        test_retry_logic()
        test_client_initialization()
        test_wallet_tool()
        test_simple_agent()
        
        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\nThe SDK components are working correctly.")
        print("\nTo test with the actual service:")
        print("1. Start Docker: docker compose up -d")
        print("2. Seed database: docker compose exec service python -m agent_wallet_service.scripts.seed")
        print("3. Run: python test_wallet_operations.py")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
