# GitHub Issue: Windows Node.js Detection Bug

**Repository:** https://github.com/coinbase/payments-mcp/issues

**Issue Title:** Installation fails on Windows: "Node.js is not available" despite Node.js v23.11.0 being installed

---

## Description

The `@coinbase/payments-mcp` installer fails on Windows with the error "Node.js is not available. Please install Node.js version 16 or higher" despite Node.js being properly installed and functional.

## Environment

- **OS:** Windows 10/11
- **Node.js:** v23.11.0 (verified with `node --version`)
- **npm:** 10.9.2 (verified with `npm --version`)
- **npx:** 10.9.2 (verified with `npx --version`)
- **Node.js Path:** `C:\Program Files\nodejs\node.exe`
- **Package Version:** @coinbase/payments-mcp v1.0.4 (remote version)

## Steps to Reproduce

1. Verify Node.js is installed and functional:
   ```bash
   node --version
   # Output: v23.11.0

   npm --version
   # Output: 10.9.2

   where node
   # Output: C:\Program Files\nodejs\node.exe
   ```

2. Attempt to install Coinbase Payments MCP:
   ```bash
   npx @coinbase/payments-mcp install --client claude-code --verbose
   ```

3. Observe installation failure

## Expected Behavior

The installer should detect Node.js v23.11.0 (which exceeds the minimum v16+ requirement) and proceed with installation.

## Actual Behavior

Installation fails with the following error:

```
✗ Installation failed
✗ Installation failed with the following error:
✗ Node.js is not available. Please install Node.js version 16 or higher.

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

## Root Cause Analysis

The installer's pre-flight check reports "Node.js is not available" despite Node.js being clearly installed and functional. This appears to be a bug in the installer's Node.js detection logic on Windows.

**Hypothesis:** The installer likely uses a command like `node --version` in its pre-flight check, but the command may fail in the installer's execution context due to:
- Windows PATH environment variable issues in the spawned process
- Different shell environment than the user's terminal
- Permissions or execution policy restrictions

## Attempted Workarounds

### 1. Install without --client flag
```bash
npx @coinbase/payments-mcp install --no-auto-config --verbose
```
**Result:** Same error

### 2. Check installation status first
```bash
npx @coinbase/payments-mcp status --verbose
```
**Result:** Confirmed not installed (expected)

### 3. Verify installation directory
```bash
cd ~ && ls -la .payments-mcp
```
**Result:** Directory not found (installation did not succeed)

## Impact

This bug prevents Windows users from:
1. Installing Coinbase Payments MCP
2. Testing the fiat on-ramp feature
3. Integrating payments-mcp with AI agents on Windows development environments

## Related Context

- I am attempting to integrate Coinbase Payments MCP with an AI agent microeconomy system (Karmacadabra) that uses x402 protocol
- The Windows installation blocker prevents POC testing to validate compatibility with:
  - Avalanche Fuji testnet (currently using Avalanche Fuji Chain ID 43113)
  - Custom ERC-20 tokens (GLUE token)
  - Programmatic agent access (48 AI agents planned)

## Suggested Fix

1. **Improve Node.js detection logic** - Use more robust detection methods that work across different Windows execution contexts
2. **Provide manual installation method** - Document how to install without the npx installer for cases where automated detection fails
3. **Better error messaging** - If Node.js detection fails, provide specific troubleshooting steps for Windows (e.g., full path specification)
4. **Add debug mode** - Include a `--debug` flag that shows exactly what command is being used for Node.js detection and its output

## Workaround Request

Since the automated installer is blocked, could you provide:
1. Manual installation instructions for Windows
2. Direct download link for the MCP server binary/package
3. Configuration file template for Claude Code integration

## Additional Information

Full environment details:
```bash
$ node --version
v23.11.0

$ npm --version
10.9.2

$ npx --version
10.9.2

$ where node
C:\Program Files\nodejs\node.exe

$ echo $env:PATH | Select-String nodejs
# Node.js is in system PATH
```

## References

- Full POC test results: [internal documentation]
- Related repository: https://github.com/coinbase/x402 (x402 MCP example)
- Use case: AI agent micropayments using x402 protocol + EIP-3009 gasless transfers

---

**Priority:** High - This blocks Windows developers from adopting Coinbase Payments MCP

**Labels:** `bug`, `windows`, `installation`, `node-detection`
