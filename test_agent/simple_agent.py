"""A simple agent that demonstrates using the wallet tool."""

import json
from wallet_tool import WalletTool, WALLET_TOOLS


class SimpleWalletAgent:
    """A simple agent that can execute wallet operations based on user requests.
    
    This is a basic rule-based agent for demonstration. In production,
    you would integrate with an LLM (like OpenAI, Anthropic, etc.) that
    can use the WALLET_TOOLS definitions for function calling.
    """
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        """Initialize the agent with wallet credentials."""
        self.wallet = WalletTool(api_key=api_key, base_url=base_url)
        self.conversation_history = []
    
    def process_command(self, command: str) -> str:
        """Process a natural language command and execute the appropriate action.
        
        Args:
            command: User's natural language command
            
        Returns:
            Response string describing the result
        """
        command_lower = command.lower()
        
        # Simple keyword-based routing
        if "balance" in command_lower or "how much" in command_lower:
            return self._handle_balance()
        
        elif "transfer" in command_lower or "send" in command_lower or "pay" in command_lower:
            return self._handle_transfer(command)
        
        elif "hold" in command_lower and ("create" in command_lower or "reserve" in command_lower):
            return self._handle_create_hold(command)
        
        elif "capture" in command_lower:
            return self._handle_capture(command)
        
        elif "release" in command_lower:
            return self._handle_release(command)
        
        elif "wallet" in command_lower and "info" in command_lower:
            return self._handle_wallet_info()
        
        elif "help" in command_lower:
            return self._handle_help()
        
        else:
            return (
                "I didn't understand that command. Try:\n"
                "- 'check balance'\n"
                "- 'transfer $X to @handle'\n"
                "- 'create hold for $X'\n"
                "- 'capture hold <hold_id> to @handle'\n"
                "- 'release hold <hold_id>'\n"
                "- 'wallet info'\n"
                "- 'help'"
            )
    
    def _handle_balance(self) -> str:
        """Handle balance check request."""
        result = self.wallet.get_balance()
        if result["success"]:
            return (
                f"💰 Wallet Balance:\n"
                f"  Available: ${result['available']} {result['currency']}\n"
                f"  Held: ${result['held']} {result['currency']}\n"
                f"  Total: ${result['total']} {result['currency']}"
            )
        return f"❌ Error checking balance: {result['error']}"
    
    def _handle_transfer(self, command: str) -> str:
        """Handle transfer request."""
        # Simple parsing - look for amount and handle
        import re
        
        # Find amount (e.g., $25, 25.00, $25.50)
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', command)
        # Find handle (e.g., @merchant, @alice)
        handle_match = re.search(r'@(\w+)', command)
        
        if not amount_match:
            return "❌ Please specify an amount (e.g., '$25' or '25.00')"
        if not handle_match:
            return "❌ Please specify a recipient handle (e.g., '@merchant')"
        
        amount = amount_match.group(1)
        handle = f"@{handle_match.group(1)}"
        
        result = self.wallet.transfer(to_handle=handle, amount=amount)
        if result["success"]:
            return (
                f"✅ Transfer successful!\n"
                f"  Amount: ${result['amount']} {result['currency']}\n"
                f"  To: {handle}\n"
                f"  Transfer ID: {result['transfer_id']}"
            )
        return f"❌ Transfer failed: {result['error']}"
    
    def _handle_create_hold(self, command: str) -> str:
        """Handle hold creation request."""
        import re
        
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', command)
        if not amount_match:
            return "❌ Please specify an amount (e.g., '$100' or '100.00')"
        
        amount = amount_match.group(1)
        result = self.wallet.create_hold(amount=amount)
        
        if result["success"]:
            return (
                f"✅ Hold created!\n"
                f"  Hold ID: {result['hold_id']}\n"
                f"  Amount: ${result['amount']}\n"
                f"  Status: {result['status']}\n"
                f"  Expires: {result['expires_at']}"
            )
        return f"❌ Hold creation failed: {result['error']}"
    
    def _handle_capture(self, command: str) -> str:
        """Handle hold capture request."""
        import re
        
        # Find hold ID (UUID format or simple ID)
        hold_match = re.search(r'hold[_\s]+([a-f0-9-]+)', command, re.IGNORECASE)
        if not hold_match:
            # Try to find any UUID-like string
            hold_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', command)
        
        handle_match = re.search(r'@(\w+)', command)
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', command)
        
        if not hold_match:
            return "❌ Please specify a hold ID"
        if not handle_match:
            return "❌ Please specify a recipient handle (e.g., '@merchant')"
        
        hold_id = hold_match.group(1)
        handle = f"@{handle_match.group(1)}"
        amount = amount_match.group(1) if amount_match else None
        
        result = self.wallet.capture_hold(hold_id=hold_id, to_handle=handle, amount=amount)
        
        if result["success"]:
            return (
                f"✅ Hold captured!\n"
                f"  Capture ID: {result['capture_id']}\n"
                f"  Amount: ${result['amount']}\n"
                f"  To: {handle}"
            )
        return f"❌ Capture failed: {result['error']}"
    
    def _handle_release(self, command: str) -> str:
        """Handle hold release request."""
        import re
        
        hold_match = re.search(r'hold[_\s]+([a-f0-9-]+)', command, re.IGNORECASE)
        if not hold_match:
            hold_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', command)
        
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', command)
        
        if not hold_match:
            return "❌ Please specify a hold ID"
        
        hold_id = hold_match.group(1)
        amount = amount_match.group(1) if amount_match else None
        
        result = self.wallet.release_hold(hold_id=hold_id, amount=amount)
        
        if result["success"]:
            return (
                f"✅ Hold released!\n"
                f"  Release ID: {result['release_id']}\n"
                f"  Amount: ${result['amount']}"
            )
        return f"❌ Release failed: {result['error']}"
    
    def _handle_wallet_info(self) -> str:
        """Handle wallet info request."""
        result = self.wallet.get_wallet_info()
        if result["success"]:
            return (
                f"📋 Wallet Info:\n"
                f"  ID: {result['wallet_id']}\n"
                f"  Handle: {result['handle']}\n"
                f"  Type: {result['type']}\n"
                f"  Status: {result['status']}\n"
                f"  Currency: {result['currency']}"
            )
        return f"❌ Error getting wallet info: {result['error']}"
    
    def _handle_help(self) -> str:
        """Return help message."""
        return """
🤖 Wallet Agent Commands:

📊 Balance & Info:
  - "check balance" or "how much do I have?"
  - "wallet info"

💸 Transfers:
  - "transfer $25 to @merchant"
  - "send $100 to @alice"
  - "pay @acme_store $50"

🔒 Holds (Reservations):
  - "create hold for $100"
  - "reserve $50"

✅ Capture Hold:
  - "capture hold <hold_id> to @merchant"
  - "capture hold <hold_id> to @merchant for $50"

🔓 Release Hold:
  - "release hold <hold_id>"
  - "release hold <hold_id> for $25"

❓ Help:
  - "help"
"""
    
    def run_interactive(self):
        """Run the agent in interactive mode."""
        print("=" * 50)
        print("🤖 Wallet Agent Started")
        print("=" * 50)
        print("Type 'help' for available commands, 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("Goodbye! 👋")
                    break
                
                response = self.process_command(user_input)
                print(f"\nAgent: {response}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    # Use Alice's test API key from the seed script
    ALICE_API_KEY = "aw_alice_test_key_12345678901234567890"
    
    print("Initializing Wallet Agent...")
    print("Using Alice's wallet (@alice)")
    print()
    
    agent = SimpleWalletAgent(api_key=ALICE_API_KEY)
    agent.run_interactive()
