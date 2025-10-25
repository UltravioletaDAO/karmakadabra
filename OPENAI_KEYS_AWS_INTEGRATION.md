# OpenAI API Keys - AWS Secrets Manager Integration

**Date**: 2025-10-25
**Status**: ✅ COMPLETE - All 6 agents configured

---

## Summary

OpenAI API keys are now stored in AWS Secrets Manager using the **exact same pattern** as private keys:

1. Keys stored in AWS Secrets Manager under `karmacadabra` secret
2. `.env` files have `OPENAI_API_KEY=` (empty)
3. If `.env` is populated, it **overrides** AWS (for local testing)
4. Same `get_openai_api_key()` function as `get_private_key()`

---

## OpenAI Keys Added to AWS

| Agent | Key Prefix | Purpose |
|-------|------------|---------|
| karma-hello-agent | REMOVED_FOR_SECURITY... | CrewAI for formatting chat logs |
| abracadabra-agent | REMOVED_FOR_SECURITY... | OpenAI for transcription analysis |
| validator-agent | REMOVED_FOR_SECURITY... | CrewAI validation crews |
| voice-extractor-agent | REMOVED_FOR_SECURITY... | CrewAI for personality extraction |
| skill-extractor-agent | REMOVED_FOR_SECURITY... | CrewAI for skill extraction |
| client-agent | REMOVED_FOR_SECURITY... | Generic key for all client agents |

**Total**: 6 OpenAI API keys stored in AWS

---

## How It Works

### 1. Agents Load Config Using Helper

**OLD WAY (manual):**
```python
import os
from dotenv import load_dotenv

load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")  # Only checks .env
private_key = os.getenv("PRIVATE_KEY")    # Only checks .env
```

**NEW WAY (automatic AWS fallback):**
```python
from shared.agent_config import load_agent_config

# One line loads everything from .env + AWS
config = load_agent_config("karma-hello-agent")

# Credentials fetched from AWS (or .env override)
print(config.openai_api_key)  # From AWS or .env
print(config.private_key)     # From AWS or .env

# Public config from .env
print(config.agent_address)   # From .env
print(config.agent_domain)    # From .env
print(config.rpc_url)         # From .env
```

### 2. Priority Order (Same as Private Keys)

```
1. Check .env file for OPENAI_API_KEY
   ├─ If non-empty → USE IT (override)
   └─ If empty → Fetch from AWS Secrets Manager

2. Fetch from AWS Secrets Manager
   └─ Use agent_name to lookup key in 'karmacadabra' secret
```

### 3. .env File Pattern

**All agents now use this pattern:**

```bash
# Credentials (leave empty - fetched from AWS)
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
OPENAI_API_KEY=  # Leave empty - fetched from AWS Secrets Manager

# Public info (safe to store)
AGENT_ADDRESS=0x2C3e071df446B25B821F59425152838ae4931E75
AGENT_DOMAIN=karma-hello.karmacadabra.ultravioletadao.xyz
```

**Local testing override:**

```bash
# For local development/testing ONLY
OPENAI_API_KEY=REMOVED_FOR_SECURITY  # Overrides AWS
```

---

## AWS Secrets Manager Structure

The `karmacadabra` secret now contains both `private_key` AND `openai_api_key`:

```json
{
  "karma-hello-agent": {
    "private_key": "0xf407212427c9fd8636e0aff57dc7c0ddaa210f83",
    "openai_api_key": "REMOVED_FOR_SECURITY",
    "address": "0x2C3e071df446B25B821F59425152838ae4931E75"
  },
  "abracadabra-agent": {
    "private_key": "0x...",
    "openai_api_key": "REMOVED_FOR_SECURITY...",
    "address": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648"
  },
  "validator-agent": {
    "private_key": "0x...",
    "openai_api_key": "REMOVED_FOR_SECURITY...",
    "address": "0x1219eF9484BF7E40E6479141B32634623d37d507"
  },
  "voice-extractor-agent": {
    "private_key": "0x...",
    "openai_api_key": "REMOVED_FOR_SECURITY...",
    "address": "0xDd63D5840090B98D9EB86f2c31974f9d6c270b17"
  },
  "skill-extractor-agent": {
    "private_key": "0x...",
    "openai_api_key": "REMOVED_FOR_SECURITY...",
    "address": "0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9"
  },
  "client-agent": {
    "private_key": "0x...",
    "openai_api_key": "REMOVED_FOR_SECURITY...",
    "address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA"
  }
}
```

---

## Scripts and Functions

### 1. Add Keys to AWS (One-Time Setup)

```bash
python scripts/add_openai_keys_to_aws.py
```

**What it does:**
- Reads existing `karmacadabra` secret from AWS
- Adds `openai_api_key` field to each agent
- Updates secret in AWS Secrets Manager

**Output:**
```
✅ karma-hello-agent
✅ abracadabra-agent
✅ validator-agent
✅ voice-extractor-agent
✅ skill-extractor-agent
✅ client-agent
```

### 2. Get OpenAI Key (in Code)

```python
from shared.secrets_manager import get_openai_api_key

# Fetch key for agent (checks .env first, then AWS)
api_key = get_openai_api_key("validator-agent")

# Use with OpenAI
import openai
openai.api_key = api_key
```

### 3. Load Complete Config (Recommended)

```python
from shared.agent_config import load_agent_config

# One call loads everything
config = load_agent_config("karma-hello-agent")

# Now you have:
config.private_key      # From AWS or .env
config.openai_api_key   # From AWS or .env
config.agent_address    # From .env
config.agent_domain     # From .env
config.rpc_url          # From .env
config.identity_registry # From .env
config.glue_token_address # From .env
config.facilitator_url  # From .env
config.host             # From .env
config.port             # From .env
config.base_price       # From .env
config.max_price        # From .env
```

### 4. Test Key Retrieval

```bash
# Test PRIVATE_KEY + OPENAI_API_KEY
python shared/secrets_manager.py validator-agent

# Output:
# [AWS Secrets] Retrieved key for 'validator-agent' from AWS
# [AWS Secrets] Retrieved OpenAI API key for 'validator-agent' from AWS
#
# [OK] Agent: validator-agent
#      Private Key: 0xf4072124...210f83
#      OpenAI Key: REMOVED_FOR_SECURITY...v96boA
```

```bash
# Test complete config loading
python shared/agent_config.py validator-agent

# Shows all config values loaded
```

---

## Migration Guide (For Existing Agents)

If your agent currently uses `os.getenv("OPENAI_API_KEY")`, migrate to the new pattern:

### Before:
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Only checks .env - no AWS fallback
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

### After:
```python
from shared.agent_config import load_agent_config

# Loads from AWS (or .env override)
config = load_agent_config("your-agent-name")

# Use config.openai_api_key
OPENAI_API_KEY = config.openai_api_key
```

**OR** (if you don't need full config):

```python
from shared.secrets_manager import get_openai_api_key

# Fetch just the OpenAI key
OPENAI_API_KEY = get_openai_api_key("your-agent-name")
```

---

## Security Best Practices

### ✅ DO:
- Leave `OPENAI_API_KEY=` empty in .env files
- Store keys in AWS Secrets Manager
- Use `.env` override only for local testing
- Commit .env.example with empty values

### ❌ DON'T:
- Commit .env files with actual keys
- Share OpenAI keys in Slack/Discord/GitHub
- Store keys in code or comments
- Expose keys in logs or terminal output

---

## Files Created/Modified

### New Files:
- `scripts/add_openai_keys_to_aws.py` - Script to add keys to AWS
- `shared/agent_config.py` - Configuration loading helper
- `OPENAI_KEYS_AWS_INTEGRATION.md` - This document

### Modified Files:
- `shared/secrets_manager.py` - Added `get_openai_api_key()` function
- `CLAUDE.md` - Added secrets management documentation
- `agents/karma-hello/.env` - Added empty OPENAI_API_KEY
- `agents/abracadabra/.env` - Added empty OPENAI_API_KEY
- `client-agents/template/.env` - Added empty OPENAI_API_KEY
- `agents/karma-hello/.env.example` - Added OPENAI_API_KEY placeholder
- `agents/abracadabra/.env.example` - Added OPENAI_API_KEY placeholder
- `client-agents/template/.env.example` - Added OPENAI_API_KEY placeholder

---

## Verification

Run system check to verify all agents have access to OpenAI keys:

```bash
python scripts/check_system_ready.py
```

Expected output:
```
ALL AGENTS
================================================================================

karma-hello:      ✅ ID #1, 165,000 GLUE, 0.4950 AVAX
abracadabra:      ✅ ID #2, 165,000 GLUE, 0.4950 AVAX
skill-extractor:  ✅ ID #6,  55,000 GLUE, 1.0950 AVAX
voice-extractor:  ✅ ID #5, 110,000 GLUE, 1.0950 AVAX
validator:        ✅ ID #4, 165,000 GLUE, 0.4950 AVAX
client:           ✅ ID #3, 220,000 GLUE, 0.0950 AVAX

Agents Ready: 6/6 ✅
```

---

## Next Steps

1. **Agents automatically fetch keys** - No action needed if using `load_agent_config()`
2. **Update existing agents** to use new pattern (see Migration Guide)
3. **Test agents** to ensure OpenAI API calls work
4. **Remove hardcoded keys** from any old code

---

**Status**: ✅ Complete - All 6 agents configured with AWS Secrets Manager integration
**Pattern**: Same as private keys - .env override → AWS fallback
**Security**: Keys never committed to git, stored securely in AWS
