# Contribution Library Dependencies

This folder contains essential Python modules copied from the main Karmacadabra repository to make the `contribution/` folder completely self-contained.

## Files Included

### agent_config.py
**Source:** `/shared/agent_config.py`
**Purpose:** Load agent configuration from .env files and AWS Secrets Manager
**Key Functions:**
- `load_agent_config(agent_name)` - Load complete agent configuration
- Handles PRIVATE_KEY and OPENAI_API_KEY fetching from AWS or .env

### base_agent.py
**Source:** `/shared/base_agent.py`
**Purpose:** Base class for all ERC-8004 compliant agents
**Key Class:**
- `ERC8004BaseAgent` - Core agent functionality
- Identity Registry registration
- Reputation management (bidirectional ratings)
- Web3 integration

**Bidirectional Rating Methods:**
- `rate_client(client_agent_id, rating, feedback_auth_id)` - Rate a client
- `rate_validator(validator_agent_id, rating)` - Rate a validator
- `get_bidirectional_ratings(agent_id)` - Get all ratings for an agent

### secrets_manager.py
**Source:** `/shared/secrets_manager.py`
**Purpose:** AWS Secrets Manager integration
**Key Functions:**
- `get_private_key(agent_name)` - Fetch private key from AWS
- `get_openai_api_key(agent_name)` - Fetch OpenAI key from AWS

## Why Copied?

The contribution folder is designed to be self-contained and portable for EIP-8004 submission. By copying these dependencies instead of referencing the main repo, we ensure:

1. **Portability:** Can be zipped and shared independently
2. **Stability:** Won't break if main repo changes
3. **Clarity:** All code needed for Week 2 is in one place
4. **Reproducibility:** Anyone can run the scripts with just this folder

## Usage in Scripts

```python
# Import from contribution/lib instead of /shared
import sys
sys.path.insert(0, '../lib')  # Add lib to path

from agent_config import load_agent_config
from base_agent import ERC8004BaseAgent

# Use normally
config = load_agent_config("karma-hello")
agent = ERC8004BaseAgent(...)
```

## Dependencies

These modules require:
- web3>=6.0.0
- eth-account>=0.8.0
- python-dotenv>=1.0.0
- boto3>=1.28.0 (for AWS Secrets Manager)

See `../scripts/requirements.txt` for complete list.
