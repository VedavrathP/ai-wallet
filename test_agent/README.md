# Test Agent

This folder contains a simple test agent that demonstrates how to use the Agent Wallet SDK.

## Files

- `wallet_tool.py` - Wrapper class for the wallet SDK with tool definitions for LLM function calling
- `simple_agent.py` - A simple rule-based agent that processes natural language commands
- `test_wallet_operations.py` - Automated test script to verify wallet operations

## Prerequisites

1. Start the wallet service:
   ```bash
   cd ..
   docker-compose up -d
   ```

2. Seed the database (creates test wallets and API keys):
   ```bash
   docker-compose exec service python -m agent_wallet_service.scripts.seed
   ```

## Running the Tests

### Automated Test Script

Run the test script to verify all wallet operations:

```bash
python test_wallet_operations.py
```

This will test:
- Getting wallet info
- Checking balance
- Transferring funds
- Creating holds
- Capturing holds (partial)
- Releasing holds
- Insufficient funds handling
- Idempotency

### Interactive Agent

Run the simple agent for interactive testing:

```bash
python simple_agent.py
```

Example commands:
```
You: check balance
You: transfer $25 to @acme_store
You: create hold for $100
You: capture hold <hold_id> to @acme_store
You: release hold <hold_id>
You: help
You: quit
```

## Test API Keys

The seed script creates these test API keys:

| Wallet | Handle | API Key |
|--------|--------|---------|
| Alice (Customer) | @alice | `aw_alice_test_key_12345678901234567890` |
| Acme Store (Merchant) | @acme_store | `aw_merchant_test_key_12345678901234567890` |
| System (Admin) | @system | `aw_admin_test_key_123456789012345678901` |

Alice starts with $1000 balance.

## Integrating with LLMs

The `wallet_tool.py` file includes `WALLET_TOOLS` - a list of tool definitions in OpenAI function calling format. You can use these with any LLM that supports function calling:

```python
from wallet_tool import WalletTool, WALLET_TOOLS

# Initialize the tool
wallet = WalletTool(api_key="your_api_key")

# Use WALLET_TOOLS with your LLM
# Example with OpenAI:
# response = openai.chat.completions.create(
#     model="gpt-4",
#     messages=[...],
#     tools=WALLET_TOOLS,
# )

# Execute the tool call
if tool_call.function.name == "get_balance":
    result = wallet.get_balance()
elif tool_call.function.name == "transfer":
    result = wallet.transfer(**json.loads(tool_call.function.arguments))
# ... etc
```
