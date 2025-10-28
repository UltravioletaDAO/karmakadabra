# Karmacadabra Shared Utilities - Test Suite

Comprehensive test suite for `shared/` utilities including unit tests (fast, mocked) and integration tests (real blockchain).

---

## 🧪 Test Structure

```
tests/
├── conftest.py                      # Pytest fixtures and configuration
├── pytest.ini                       # Pytest settings
├── requirements-test.txt            # Testing dependencies
├── unit/                            # Unit tests (fast, no network)
│   ├── test_payment_signer.py       # EIP-712 signature tests
│   ├── test_a2a_protocol.py         # A2A protocol tests
│   └── ...
└── integration/                     # Integration tests (requires network)
    ├── test_base_agent.py           # ERC8004 on-chain tests
    └── ...
```

---

## 🚀 Quick Start

### Install Dependencies

```bash
cd shared/tests
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# Run all unit tests (fast, no network required)
pytest -m unit

# Run all tests (unit + integration)
pytest

# Run with coverage
pytest --cov=../ --cov-report=html
```

---

## 📊 Test Categories

### Unit Tests (Default)

**Fast, mocked tests that don't require network access**

```bash
# Run only unit tests
pytest -m unit

# Run specific test file
pytest unit/test_payment_signer.py

# Run specific test
pytest unit/test_payment_signer.py::TestPaymentSigner::test_sign_transfer_authorization
```

**Coverage:**
- ✅ `payment_signer.py` - EIP-712 signature creation/verification
- ✅ `a2a_protocol.py` - AgentCard creation, skill management

**No requirements:** Runs without blockchain access or API keys


### Integration Tests

**Tests that interact with real infrastructure**

```bash
# Run integration tests
pytest -m integration

# Skip integration tests
pytest -m "not integration"
```

**Requirements:**
- Fuji RPC access (public node works)
- For funded tests: `TEST_PRIVATE_KEY` env var with funded wallet

**Coverage:**
- ✅ `base_agent.py` - ERC8004 contract reads (no funding needed)
- ⚠️ `base_agent.py` - Registration/rating (requires AVAX, commented out)

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in `tests/` directory:

```bash
# Blockchain (uses public nodes by default)
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# Contract addresses (defaults to deployed contracts)
IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
REPUTATION_REGISTRY=0x932d32194C7A47c0fe246C1d61caF244A4804C6a
VALIDATION_REGISTRY=0x9aF4590035C109859B4163fd8f2224b820d11bc2
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz

# For integration tests requiring funding (optional)
TEST_PRIVATE_KEY=0x...  # Funded wallet for integration tests

# For CrewAI validation tests (optional)
OPENAI_API_KEY=sk-...   # OpenAI API key
```

---

## 🏷️ Test Markers

Use pytest markers to select test subsets:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Skip tests requiring funding
pytest -m "not requires_funding"

# Skip tests requiring OpenAI
pytest -m "not requires_openai"

# Combine markers
pytest -m "unit and not slow"
```

---

## 📝 Writing Tests

### Unit Test Example

```python
import pytest
from payment_signer import PaymentSigner

@pytest.mark.unit
class TestPaymentSigner:
    def test_signature_creation(self, test_private_key, test_address):
        """Test EIP-712 signature creation"""
        signer = PaymentSigner(
            glue_token_address="0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
            chain_id=43113
        )

        signature = signer.sign_transfer_authorization(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            value=10000,
            private_key=test_private_key
        )

        assert signature["v"] in [27, 28]
```

### Integration Test Example

```python
import pytest
from base_agent import ERC8004BaseAgent

@pytest.mark.integration
class TestERC8004Integration:
    def test_query_agent(self, readonly_agent):
        """Test querying agent from registry"""
        exists = readonly_agent.agent_exists(1)
        assert isinstance(exists, bool)
```

---

## 🔍 Available Fixtures

See `conftest.py` for all fixtures. Common ones:

- `test_config` - Test configuration from env
- `test_private_key` - Generated test wallet key
- `test_address` - Test wallet address
- `funded_test_key` - Funded wallet (from env or generated)
- `w3` - Web3 instance connected to Fuji
- `mock_w3` - Mock Web3 for unit tests
- `sample_logs_data` - Sample Twitch logs
- `sample_agent_card` - Sample AgentCard

---

## 📈 Coverage

Generate coverage report:

```bash
# HTML report
pytest --cov=../ --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=../ --cov-report=term-missing

# XML report (for CI)
pytest --cov=../ --cov-report=xml
```

---

## 🤖 CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Shared Utilities

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd shared/tests
          pip install -r requirements-test.txt

      - name: Run unit tests
        run: pytest -m unit --cov=shared --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## ⚠️ Important Notes

### Integration Tests Cost Money

Some integration tests (marked with `@pytest.mark.requires_funding`) execute transactions on Fuji testnet that cost AVAX:

- ✅ Read operations: FREE (no gas)
- ❌ Write operations: ~0.005-0.01 AVAX per transaction

**These tests are commented out by default.** Uncomment them only when testing with funded wallets.

### Rate Limiting

- Public RPC nodes may rate-limit
- Use private RPC for intensive testing
- Add delays between tests if needed

### Test Data

- Tests use temporary wallets (not production wallets)
- Integration tests may leave test data on-chain
- Clean up test agents periodically

---

## 🐛 Troubleshooting

**"RPC connection failed"**
- Check `RPC_URL_FUJI` is accessible
- Try alternative public node
- Verify network connectivity

**"Contract call reverted"**
- Contract may not be deployed
- Check contract addresses in `.env`
- Verify you're on correct network (Fuji = 43113)

**"Insufficient funds"**
- Get AVAX from https://faucet.avax.network/
- Ensure `TEST_PRIVATE_KEY` wallet has AVAX
- Skip funded tests: `pytest -m "not requires_funding"`

**"Import errors"**
- Install test dependencies: `pip install -r requirements-test.txt`
- Ensure `shared/` is in Python path
- Run from `shared/tests/` directory

---

## 📚 Resources

- **Pytest docs**: https://docs.pytest.org/
- **Avalanche Fuji faucet**: https://faucet.avax.network/
- **ERC-8004 spec**: https://eips.ethereum.org/EIPS/eip-8004
- **Project docs**: `../../README.md`

---

**Questions?** See main [README.md](../../README.md) or [MASTER_PLAN.md](../../MASTER_PLAN.md)
