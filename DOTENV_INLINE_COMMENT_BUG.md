# python-dotenv Inline Comment Bug

**Date**: 2025-10-25
**Critical Issue**: python-dotenv reads inline comments as VALUES!

---

## The Problem

**Error when running agents:**
```
binascii.Error: Non-hexadecimal digit found
```

**Debug output showed:**
```
[DEBUG] PRIVATE_KEY raw: '# Leave empty - fetched from AWS Secrets Manager' (len=48)
```

The ENTIRE COMMENT was being loaded as the PRIVATE_KEY value!

---

## Root Cause: python-dotenv Inline Comment Parsing

**.env file had:**
```bash
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
```

**python-dotenv parsed it as:**
```python
os.getenv("PRIVATE_KEY") = "# Leave empty - fetched from AWS Secrets Manager"
```

**NOT** as:
```python
os.getenv("PRIVATE_KEY") = ""  # (what we expected)
```

---

## Why This Happened

python-dotenv (and most .env parsers) treat **everything after `=` as the value**, including comments!

**Inline comments are NOT supported** in .env files for most parsers.

---

## The Fix

Move comments to their **own line BEFORE** the variable:

### ❌ WRONG (inline comment):
```bash
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
OPENAI_API_KEY=sk-proj-...  # Your OpenAI API key
```

### ✅ CORRECT (separate line comment):
```bash
# Leave empty - fetched from AWS Secrets Manager
PRIVATE_KEY=

# Your OpenAI API key
OPENAI_API_KEY=sk-proj-...
```

---

## What Was Fixed

### .env Files (manually fixed - not in git):
- `agents/karma-hello/.env`
- `agents/abracadabra/.env`
- `agents/skill-extractor/.env`
- `agents/voice-extractor/.env`
- `agents/validator/.env`
- `client-agents/template/.env`

### .env.example Files (committed to git):
- `agents/karma-hello/.env.example`
- `agents/abracadabra/.env.example`
- `client-agents/template/.env.example`

### Pattern Changed From:
```bash
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
AGENT_ADDRESS=0x2C3e071df446B25B821F59425152838ae4931E75  # Public address
```

### Pattern Changed To:
```bash
# Leave empty - fetched from AWS Secrets Manager
PRIVATE_KEY=
# Public address (safe to store)
AGENT_ADDRESS=0x2C3e071df446B25B821F59425152838ae4931E75
```

---

## Verification

After fixing, running the agent shows:
```bash
cd agents/karma-hello && python main.py
```

**Output:**
```
[INFO] [karma-hello-agent] Connecting to Fuji...
[INFO] [karma-hello-agent] Connected to Fuji (Chain ID: 43113)
[INFO] [karma-hello-agent] Loading private key from AWS Secrets Manager
[AWS Secrets] PRIVATE_KEY not in env, fetching from AWS Secrets Manager...
[AWS Secrets] Retrieved key for 'karma-hello-agent' from AWS
[INFO] [karma-hello-agent] Wallet address: 0x2C3e071df446B25B821F59425152838ae4931E75
✅ Started successfully!
```

**No more errors!** ✅

---

## python-dotenv Comment Rules

According to python-dotenv documentation:

### ✅ SUPPORTED:
```bash
# Full line comments
VARIABLE=value

# Comments before variables
# This is a comment
ANOTHER_VAR=value
```

### ❌ NOT SUPPORTED:
```bash
# Inline comments are treated as part of the value!
VARIABLE=value  # This becomes part of the value
VARIABLE=  # Even this comment becomes the value
```

---

## Lesson Learned

**Always put comments on their own line in .env files!**

This is a common gotcha with .env file parsers across multiple languages (Python, Node.js, etc.)

---

## Files to Update Manually

If you have any .env files with inline comments, update them:

```bash
# Check all .env files for inline comments
grep -r "=.*#" agents/*/.env client-agents/*/.env
```

Then move those comments to separate lines above the variable.

---

## Quick Fix Script (Optional)

If you have many .env files to fix:

```bash
# WARNING: Review changes before running!
# This removes all inline comments from .env files

for file in agents/*/.env client-agents/*/.env; do
  if [ -f "$file" ]; then
    # Remove inline comments (everything after # on same line as =)
    sed -i 's/\(.*=.*\)  *#.*/\1/' "$file"
  fi
done
```

**Better**: Manually fix each file to preserve the comment information on separate lines!

---

**Status**: ✅ Fixed in all agent .env and .env.example files
**Agents now start successfully!** 🎉
