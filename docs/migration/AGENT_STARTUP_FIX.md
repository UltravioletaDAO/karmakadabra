# Agent Startup Fix - Whitespace Handling

**Date**: 2025-10-25
**Issue**: Agents failing with `binascii.Error: Non-hexadecimal digit found`

---

## Problem

When running agents:
```bash
cd agents/karma-hello && python main.py
```

Error occurred:
```
[2025-10-25 01:42:32,190] WARNING - [karma-hello-agent] Using provided private key (testing mode)
...
binascii.Error: Non-hexadecimal digit found
```

---

## Root Cause

**.env files had whitespace after `PRIVATE_KEY=`:**

```bash
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
            ^^
            Two spaces here!
```

**What happened:**
1. `os.getenv("PRIVATE_KEY")` returns `"  "` (two spaces)
2. `"  " or None` evaluates to `"  "` (whitespace is truthy!)
3. Code thinks you provided a private key
4. Tries to parse `"  "` as hex → fails

---

## Fix

**Changed in all agents:**

### Before (broken):
```python
config = {
    "private_key": os.getenv("PRIVATE_KEY") or None,
    ...
}
```

### After (fixed):
```python
config = {
    "private_key": os.getenv("PRIVATE_KEY", "").strip() or None,
    ...                                       ^^^^^^^^
                                             Strips whitespace!
}
```

**Now the logic is:**
1. `os.getenv("PRIVATE_KEY", "")` → Gets value or `""` if not set
2. `.strip()` → Removes whitespace (so `"  "` becomes `""`)
3. `or None` → If empty string, use `None` instead
4. `None` → Fetches from AWS Secrets Manager ✅

---

## Agents Fixed

✅ agents/karma-hello/main.py
✅ agents/skill-extractor/main.py
✅ agents/voice-extractor/main.py
✅ agents/abracadabra/main.py

---

## Test It Works

```bash
# Should now fetch from AWS successfully
cd agents/karma-hello && python main.py
```

**Expected output:**
```
[INFO] [karma-hello-agent] Connecting to Fuji...
[INFO] [karma-hello-agent] Connected to Fuji (Chain ID: 43113)
[INFO] [karma-hello-agent] Loading private key from AWS Secrets Manager
[AWS Secrets] PRIVATE_KEY not in env, fetching from AWS Secrets Manager...
[AWS Secrets] Retrieved key for 'karma-hello-agent' from AWS
[INFO] [karma-hello-agent] Wallet address: 0x2C3e071df446B25B821F59425152838ae4931E75
[INFO] [karma-hello-agent] Balance: 0.4950 AVAX
```

---

## Why This Pattern is Better

**Old pattern problems:**
- ❌ Doesn't handle whitespace
- ❌ Doesn't handle empty strings well
- ❌ Fails silently with cryptic errors

**New pattern benefits:**
- ✅ Handles whitespace gracefully
- ✅ Handles empty strings correctly
- ✅ Clear behavior: empty/whitespace → AWS, value → override

---

## Alternative: Clean .env Files

You could also just ensure .env files have NO spaces:

```bash
# Correct
PRIVATE_KEY=
OPENAI_API_KEY=

# Wrong (causes issues with old code)
PRIVATE_KEY=  # comment with spaces before
```

But the code fix is more robust and handles both cases!

---

**Status**: ✅ Fixed in all 4 service agents
**Commits**: ef4a4e8
