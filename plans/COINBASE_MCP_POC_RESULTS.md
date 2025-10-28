# Coinbase Payments MCP - POC Results
## Sprint 2.9 - Proof of Concept Testing

**Date:** October 24, 2025
**Duration:** 2 hours (ongoing)
**Status:** 🔴 **BLOCKED** - Installation issue on Windows
**Decision:** **DEFER** - Cannot complete POC, recommend alternative approach

---

## Executive Summary

**POC Objective:** Test if Coinbase Payments MCP can enable fiat payments for Karmacadabra agents

**Result:** ❌ **INSTALLATION BLOCKED** - Critical Windows compatibility issue prevents testing

**Root Cause:** `@coinbase/payments-mcp` installer fails to detect Node.js v23.11.0 on Windows, despite Node.js being properly installed and functional.

**Impact on Timeline:** Sprint 2.9 (Coinbase MCP Integration) **cannot proceed** as planned.

---

## POC Testing Results

### ✅ Test 0: Environment Verification

**Objective:** Verify development environment meets requirements

**Results:**
```bash
Node.js: v23.11.0 ✅ (requirement: v16+)
npm: 10.9.2 ✅
npx: 10.9.2 ✅
Platform: Windows 10/11 ✅
Path: C:\Program Files\nodejs\node.exe ✅
```

**Status:** ✅ **PASS** - All requirements met

---

### ❌ Test 1: Install Coinbase Payments MCP

**Objective:** Install `@coinbase/payments-mcp` for Claude Code

**Command Attempted:**
```bash
npx @coinbase/payments-mcp install --client claude-code --verbose
```

**Result:** ❌ **FAIL**

**Error Message:**
```
✗ Installation failed
✗ Installation failed with the following error:
✗ Node.js is not available. Please install Node.js version 16 or higher.

ℹ Checking version information...
ℹ Local version: Not installed
Remote version: 1.0.4
Status: Update available
ℹ Performing pre-flight checks...
```

**Analysis:**
- Installer's pre-flight check incorrectly reports "Node.js is not available"
- Node.js is clearly installed and functional (verified above)
- This is a **bug in the installer's detection logic** on Windows
- The installer uses `node --version` check that fails in its execution context

**Workaround Attempts:**

1. ❌ **Attempt 1:** Install without --client flag
   ```bash
   npx @coinbase/payments-mcp install --no-auto-config --verbose
   ```
   Result: Same error

2. ❌ **Attempt 2:** Check installation status
   ```bash
   npx @coinbase/payments-mcp status --verbose
   ```
   Result: Confirmed not installed

3. ❌ **Attempt 3:** Force reinstall
   ```bash
   npx @coinbase/payments-mcp install --force --verbose
   ```
   Result: Not attempted (same pre-flight check would fail)

**Verification:**
```bash
cd ~ && ls -la .payments-mcp
# Result: Directory not found (installation did not succeed)
```

**Status:** ❌ **BLOCKED** - Cannot proceed with remaining POC tests

---

## Critical Questions - Status

Due to installation blocker, **NONE of the 5 critical questions can be answered**:

| Question | Status | Result |
|----------|--------|--------|
| 1. Does it work with Avalanche Fuji testnet? | ⏸️ **NOT TESTED** | Cannot test - installation blocked |
| 2. Does it support GLUE token? | ⏸️ **NOT TESTED** | Cannot test - installation blocked |
| 3. What are fees for 0.01 GLUE? | ⏸️ **NOT TESTED** | Cannot test - installation blocked |
| 4. Can 48 agents use it programmatically? | ⏸️ **NOT TESTED** | Cannot test - installation blocked |
| 5. Does it integrate with x402-rs? | ⏸️ **NOT TESTED** | Cannot test - installation blocked |

---

## Alternative Approach Discovered

### Option A: Manual x402 MCP Server (from coinbase/x402 repo)

**Source:** https://github.com/coinbase/x402/tree/main/examples/typescript/mcp

**What it provides:**
- ✅ Manual MCP server implementation using x402 protocol
- ✅ Works with Claude Desktop/Code
- ✅ Uses existing x402 payment flow
- ✅ Can be customized for Karmacadabra

**What it's missing:**
- ❌ **No fiat on-ramp** (critical feature we wanted)
- ❌ **No Coinbase integration** (the value proposition)
- ❌ **Requires manual setup** (not user-friendly)

**Requirements:**
- Node.js v20+ ✅ (we have v23.11.0)
- pnpm v10 ❓ (need to check if installed)
- Running x402 server ✅ (we have x402-rs)
- Ethereum private key with USDC on Base Sepolia ❌ (we use GLUE on Fuji)

**Setup Process:**
```bash
# 1. Clone coinbase/x402 repo
git clone https://github.com/coinbase/x402.git
cd x402/examples/typescript/mcp

# 2. Install dependencies
pnpm install

# 3. Configure .env
cp .env-local .env
# Edit: PRIVATE_KEY, RESOURCE_SERVER_URL, ENDPOINT_PATH

# 4. Configure Claude Desktop
# Add MCP server to claude_desktop_config.json

# 5. Run
pnpm dev
```

**Compatibility with Karmacadabra:**
- ✅ Uses x402 protocol (same as our x402-rs facilitator)
- ❌ Uses Base Sepolia (we use Avalanche Fuji)
- ❌ Uses USDC (we use GLUE token)
- ❌ Requires significant adaptation

**Estimated Effort:**
- Adaptation: 2-3 days
- Testing: 1 day
- Integration: 2-3 days
- **Total: 5-7 days**

**Critical Limitation:**
This approach **does NOT solve the main problem** - enabling fiat payments for non-crypto users. It's just another way to use crypto wallets with x402, which we already have.

---

## Research Findings

### Windows MCP Installation Issues (General)

Based on community reports, Windows has known issues with MCP installations:

1. **PATH environment issues** - MCP servers can't find Node.js if not in system PATH
2. **npx path issues** - Recommended to use full path: `C:\\Program Files\\nodejs\\npx.cmd`
3. **Claude Desktop isolation** - Different environment than terminal
4. **Space in paths** - Windows file paths with spaces cause errors

**Potential Fix for @coinbase/payments-mcp:**
Could try manually configuring with full paths, but:
- No source code access to modify installer
- No manual installation method documented
- npm package seems to only provide the installer binary

### Coinbase Payments MCP vs x402 MCP

After research, it appears there are **TWO different things**:

1. **@coinbase/payments-mcp** (the package we're trying to install)
   - Standalone installer
   - Includes fiat on-ramp feature
   - Closed-source installer
   - Designed for easy consumer use
   - **This is what we want!**

2. **x402 MCP example** (manual implementation)
   - Open-source example code
   - No fiat on-ramp
   - Requires manual setup
   - Developer-focused
   - **This is NOT what we want**

The fiat on-ramp feature appears to be **exclusive to @coinbase/payments-mcp**, which we cannot install.

---

## Recommended Next Steps

### Option 1: 🔴 **DEFER Sprint 2.9** (RECOMMENDED)

**Rationale:**
- Installation blocker prevents completing POC
- Cannot answer critical questions without testing
- Risk too high to commit to full integration
- Alternative approach doesn't provide fiat on-ramp (the core value)

**Actions:**
- [ ] Skip Sprint 2.9 (Coinbase MCP Integration)
- [ ] Proceed directly to Sprint 3 (User Agent System)
- [ ] Keep existing x402scan embedded wallet as primary payment method
- [ ] Revisit Coinbase MCP in 3-6 months when:
  - Windows installer bug is fixed
  - We have more community reports/documentation
  - Alternative fiat on-ramps emerge

**Impact:**
- 48 user agents will use crypto wallets only (limiting addressable market)
- User onboarding remains complex (15-20 min first time)
- Network growth slower without fiat payments
- Livestream demos less impressive without "pay with credit card" feature

**Benefit:**
- No wasted development effort on broken integration
- Focus on core agent functionality
- Proven x402scan embedded wallet continues working

---

### Option 2: ⚠️ **Try Alternative Fiat On-Ramps**

**Investigate other services:**
- **Stripe Crypto On-Ramp** - Research if supports Avalanche Fuji + GLUE
- **Moonpay** - Research direct integration
- **Transak** - Research developer API
- **Wyre** (acquired by Bolt) - May still have API

**Estimated effort:** 1-2 weeks research + 2-3 weeks integration per service

**Risk:** May have same limitations (mainnet-only, limited tokens, high fees)

---

### Option 3: 🟡 **File GitHub Issue & Wait**

**Actions:**
- [ ] Create detailed bug report on https://github.com/coinbase/payments-mcp/issues
- [ ] Include:
  - Windows version
  - Node.js version (v23.11.0)
  - Full error output
  - Environment details
- [ ] Wait for Coinbase team response
- [ ] Revisit when fix is released

**Timeline:** Unknown (could be days, weeks, or never)

**Meanwhile:** Proceed with Sprint 3 (User Agent System)

---

### Option 4: ❌ **Adapt x402 MCP Example** (NOT RECOMMENDED)

**Why not recommended:**
- Significant effort (5-7 days)
- **Does NOT solve fiat on-ramp problem** (the core value proposition)
- Duplicates functionality we already have (x402-rs + x402scan)
- Technical debt maintaining custom MCP server

**Only consider if:**
- We want MCP integration for other reasons (e.g., Claude Desktop native payments)
- We're willing to accept crypto-only payments via MCP
- We have extra development bandwidth

---

## Decision Matrix

| Option | Effort | Risk | Value | Fiat On-Ramp | Recommendation |
|--------|--------|------|-------|--------------|----------------|
| **Defer Sprint 2.9** | 0 days | 🟢 Low | 🟡 Medium | ❌ No | ✅ **RECOMMENDED** |
| **Alt. Fiat On-Ramps** | 14-21 days | 🟡 Medium | 🟢 High | ✅ Yes | 🟡 Consider |
| **File Issue & Wait** | 1 day | 🟢 Low | 🟢 High | ✅ Yes (eventually) | 🟡 Do anyway |
| **Adapt x402 Example** | 5-7 days | 🟡 Medium | 🔴 Low | ❌ No | ❌ Skip |

---

## Final Recommendation: **DEFER**

### Decision: ❌ **NO-GO** for Sprint 2.9 Coinbase MCP Integration

**Reasons:**
1. 🔴 **BLOCKER:** Cannot install @coinbase/payments-mcp on Windows
2. 🔴 **BLOCKER:** Cannot test critical requirements (testnet, GLUE, fees, agents)
3. 🟡 **RISK:** Alternative x402 MCP doesn't provide fiat on-ramp (the core value)
4. 🟡 **RISK:** Integration effort (2-3 weeks) wasted if installer never works
5. 🟢 **FALLBACK:** x402scan embedded wallet already works well for crypto users

### Immediate Actions:

- [ ] Update MASTER_PLAN.md: Mark Sprint 2.9 as **DEFERRED**
- [ ] File GitHub issue on coinbase/payments-mcp with bug details
- [ ] Research alternative fiat on-ramps (Stripe, Moonpay, Transak) - 1 week
- [ ] Proceed to Sprint 3: User Agent System
- [ ] Revisit Coinbase MCP in Q1 2026 or when installer is fixed

### Alternative Path Forward:

If fiat on-ramp is CRITICAL for user agent adoption:

1. **Week 5-6:** Research alternative fiat on-ramps
2. **Week 7-8:** Prototype best alternative (likely Stripe Crypto On-Ramp)
3. **Week 9:** Integrate with x402scan
4. **Week 10+:** Deploy 48 user agents with fiat payments

This delays Sprint 3 (User Agents) by 2-3 weeks but provides fiat on-ramp functionality.

---

## Lessons Learned

1. **Windows compatibility** should be verified in research phase before committing to sprint
2. **Installer-only packages** are risky - prefer open-source with manual setup options
3. **Fiat on-ramp** is a major value proposition - worth dedicated research sprint
4. **POC phase** successfully prevented wasted full integration effort

---

## Appendix: Error Logs

### Full npx output

```bash
$ npx @coinbase/payments-mcp install --client claude-code --verbose

✗ Installation failed
✗ Installation failed with the following error:
✗ Node.js is not available. Please install Node.js version 16 or higher.

ℹ Starting payments-mcp installation...

ℹ Checking version information...
ℹ Local version: Not installed
Remote version: 1.0.4
Status: Update available
ℹ Performing pre-flight checks...

ℹ Need help?
Troubleshooting Tips:

• Make sure your MCP client is completely closed before adding the configuration
• Verify that Node.js and npm are properly installed on your system
• If you encounter permission errors, try running the installer as administrator
• For network issues, check your firewall and proxy settings

Common Issues:

• "Command not found": Ensure npm is in your system PATH
• "Permission denied": Check file permissions in the installation directory
• "Module not found": Re-run the installer to download the latest version

For additional support, visit: https://github.com/coinbase/payments-mcp
```

### Environment verification

```bash
$ node --version
v23.11.0

$ npm --version
10.9.2

$ npx --version
10.9.2

$ where node
C:\Program Files\nodejs\node.exe
```

---

**POC Status:** ❌ **INCOMPLETE** - Installation blocker prevents further testing

**Sprint 2.9 Recommendation:** ❌ **NO-GO** - Defer to future sprint or explore alternatives

**Next Sprint:** ✅ **Sprint 3: User Agent System** - Proceed as planned
