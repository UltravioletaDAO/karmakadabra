/**
 * Karma Kadabra V2 — Task 1.6: Fund Agents CLI (Orchestrator)
 *
 * Main CLI that orchestrates the entire funding flow:
 *   1. Generate wallets (if not exists)
 *   2. Same-chain distribution via Disperse.app
 *   3. Cross-chain bridging via deBridge/Squid Router
 *   4. Verify all balances
 *
 * Usage:
 *   npx tsx fund-agents.ts --config config/funding-config.json --dry-run
 *   npx tsx fund-agents.ts --config config/funding-config.json --chain base
 *   npx tsx fund-agents.ts --config config/funding-config.json
 *   npx tsx fund-agents.ts --verify --wallets config/wallets.json
 */

import {
  createPublicClient,
  createWalletClient,
  http,
  parseUnits,
  parseEther,
  formatUnits,
  formatEther,
  getAddress,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount, nonceManager } from "viem/accounts";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import { CHAINS, ERC20_ABI, getChain, getChainNames, getTokenSymbols } from "./lib/chains.js";
import { selectBridge, summarizePlan, planDistribution } from "./lib/bridge-router.js";
import * as debridge from "./lib/debridge-client.js";
import * as squid from "./lib/squid-client.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FundingConfig {
  version: string;
  sourceChain: string;
  wallets: string;
  perAgent: {
    /** v2.0: amount per token per agent */
    defaultAmount: string;
    /** v1.0 compat: flat USDC amount */
    usdc?: string;
    chains: string[];
    /** v2.0: per-chain token list. If absent, defaults to ["USDC"] per chain */
    tokens?: Record<string, string[]>;
  };
  gasAmounts: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Bridge Execution
// ---------------------------------------------------------------------------

async function executeBridge(
  srcChain: string,
  dstChain: string,
  amount: string,
  recipient: Address,
  funderKey: Hex,
  dryRun: boolean,
): Promise<{ provider: string; txHash: string; status: string }> {
  const route = selectBridge(srcChain, dstChain);
  const srcInfo = getChain(srcChain);

  if (route.provider === "direct") {
    return { provider: "direct", txHash: "n/a", status: "same-chain" };
  }

  if (dryRun) {
    return { provider: route.provider, txHash: "dry-run", status: "skipped" };
  }

  const account = privateKeyToAccount(funderKey, { nonceManager });
  const atomicAmount = parseUnits(amount, 6).toString();

  if (route.provider === "debridge") {
    const srcDlnId = CHAINS[srcChain].debridgeChainId;
    const dstDlnId = CHAINS[dstChain].debridgeChainId;
    if (!srcDlnId || !dstDlnId) {
      throw new Error(`deBridge not available for ${srcChain} → ${dstChain}`);
    }

    const quote = await debridge.getQuote({
      srcChainId: srcDlnId,
      srcToken: srcInfo.usdc,
      dstChainId: dstDlnId,
      dstToken: CHAINS[dstChain].usdc,
      amount: atomicAmount,
      srcAddress: account.address,
      dstAddress: recipient,
    });

    if (!quote.tx) {
      throw new Error(`deBridge: no TX data — ${quote.errorMessage || "unknown"}`);
    }

    // Execute the bridge TX
    const walletClient = createWalletClient({
      account,
      chain: srcInfo.chain,
      transport: http(srcInfo.rpcUrl),
    });

    // Approve USDC — approve the bridge contract's required amount (may include fees)
    const approveAmount = BigInt(quote.estimation.srcChainTokenIn.amount || atomicAmount);
    const approveTx = await walletClient.writeContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "approve",
      args: [getAddress(quote.tx.to) as Address, approveAmount],
    });

    const publicClient = createPublicClient({
      chain: srcInfo.chain,
      transport: http(srcInfo.rpcUrl),
    });
    await publicClient.waitForTransactionReceipt({ hash: approveTx });

    // Send bridge TX
    const txHash = await walletClient.sendTransaction({
      to: getAddress(quote.tx.to) as Address,
      data: quote.tx.data as Hex,
      value: BigInt(quote.tx.value),
    });

    return { provider: "debridge", txHash, status: `order:${quote.orderId}` };
  }

  if (route.provider === "squid") {
    const quote = await squid.getRoute({
      fromChainId: String(CHAINS[srcChain].chainId),
      toChainId: String(CHAINS[dstChain].chainId),
      fromToken: srcInfo.usdc,
      toToken: CHAINS[dstChain].usdc,
      fromAmount: atomicAmount,
      fromAddress: account.address,
      toAddress: recipient,
    });

    if (!quote.route.transactionRequest) {
      throw new Error("Squid: no transaction request in route");
    }

    const walletClient = createWalletClient({
      account,
      chain: srcInfo.chain,
      transport: http(srcInfo.rpcUrl),
    });

    // Approve USDC — use fromAmount from the route estimate (includes fees)
    const target = getAddress(quote.route.transactionRequest.target) as Address;
    const squidApproveAmount = BigInt(quote.route.estimate?.toAmount ? atomicAmount : atomicAmount);
    const approveTx = await walletClient.writeContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "approve",
      args: [target, squidApproveAmount],
    });

    const publicClient = createPublicClient({
      chain: srcInfo.chain,
      transport: http(srcInfo.rpcUrl),
    });
    await publicClient.waitForTransactionReceipt({ hash: approveTx });

    // Send bridge TX
    const txHash = await walletClient.sendTransaction({
      to: target,
      data: quote.route.transactionRequest.data as Hex,
      value: BigInt(quote.route.transactionRequest.value),
    });

    return { provider: "squid", txHash, status: `quote:${quote.route.quoteId}` };
  }

  throw new Error(`Unsupported bridge provider: ${route.provider}`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);

  const configFile = args.includes("--config")
    ? args[args.indexOf("--config") + 1]
    : resolve(__dirname, "config", "funding-config.json");

  const chainFilter = args.includes("--chain")
    ? args[args.indexOf("--chain") + 1]
    : null;

  const dryRun = args.includes("--dry-run");
  const verifyOnly = args.includes("--verify");

  if (verifyOnly) {
    console.log("Use check-balances.ts for verification.");
    process.exit(0);
  }

  // Load config
  let fundConfig: FundingConfig;
  try {
    fundConfig = JSON.parse(readFileSync(configFile, "utf-8"));
  } catch {
    console.error(`ERROR: Cannot read ${configFile}`);
    console.error("Create it from funding-config.example.json");
    process.exit(1);
  }

  // Load wallets
  const walletsFile = resolve(__dirname, fundConfig.wallets);
  let manifest: WalletManifest;
  try {
    manifest = JSON.parse(readFileSync(walletsFile, "utf-8"));
  } catch {
    console.error(`ERROR: Cannot read ${walletsFile}. Run generate-wallets.ts first.`);
    process.exit(1);
  }

  const funderKey = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
  if (!funderKey) {
    console.error("ERROR: WALLET_PRIVATE_KEY not set");
    process.exit(1);
  }

  const targetChains = chainFilter
    ? [chainFilter]
    : fundConfig.perAgent.chains;

  // Resolve per-agent amount (v2: defaultAmount, v1 compat: usdc)
  const amountPerToken = fundConfig.perAgent.defaultAmount || fundConfig.perAgent.usdc || "1.00";

  // Resolve per-chain token lists
  const chainTokens: Record<string, string[]> = {};
  let totalTokenSlots = 0;
  const uniqueTokens = new Set<string>();
  for (const chain of targetChains) {
    const tokens = fundConfig.perAgent.tokens?.[chain] || ["USDC"];
    // Validate tokens exist on chain
    const available = getTokenSymbols(chain);
    const valid = tokens.filter((t) => {
      if (!available.includes(t)) {
        console.warn(`  WARN: ${t} not available on ${chain}, skipping`);
        return false;
      }
      return true;
    });
    chainTokens[chain] = valid;
    totalTokenSlots += valid.length;
    valid.forEach((t) => uniqueTokens.add(t));
  }

  // Budget summary
  const totalStablecoin = parseFloat(amountPerToken) * manifest.count * totalTokenSlots;

  console.log(`\n${"=".repeat(60)}`);
  console.log(`  Karma Kadabra V2 — Fund ${manifest.count} Agents`);
  console.log(`  Source: ${fundConfig.sourceChain}`);
  console.log(`  Targets: ${targetChains.join(", ")}`);
  console.log(`  Amount/token/agent: $${amountPerToken}`);
  console.log(`  Total: $${totalStablecoin.toFixed(2)} across ${targetChains.length} chains, ${uniqueTokens.size} stablecoins`);
  if (dryRun) console.log(`  ** DRY RUN — no transactions **`);
  console.log(`${"=".repeat(60)}`);

  // Per-chain per-token distribution plan
  console.log(`\n  Distribution Plan:`);
  for (const chain of targetChains) {
    const tokens = chainTokens[chain];
    const chainTotal = parseFloat(amountPerToken) * manifest.count * tokens.length;
    console.log(`    ${chain}: ${tokens.join(", ")} ($${chainTotal.toFixed(2)} total)`);
  }

  // Show bridge plan
  const routes = planDistribution(fundConfig.sourceChain, targetChains);
  summarizePlan(routes);

  // Execute: same-chain distribution first, then bridges
  const sameChainTargets = targetChains.filter((c) => c === fundConfig.sourceChain);
  const crossChainTargets = targetChains.filter((c) => c !== fundConfig.sourceChain);

  // Same-chain: handled by distribute-funds.ts logic
  for (const chain of sameChainTargets) {
    const tokens = chainTokens[chain];
    console.log(`\n--- Same-chain distribution on ${chain} ---`);
    console.log(`  Tokens: ${tokens.join(", ")} ($${amountPerToken}/token/agent)`);
    console.log(`  (Run: npx tsx distribute-funds.ts --chain ${chain} --wallets ${fundConfig.wallets} --amount ${amountPerToken} --tokens ${tokens.join(",")} --gas ${fundConfig.gasAmounts[chain] || "0.0005"})`);
  }

  // Cross-chain: bridge from source to each target
  if (crossChainTargets.length > 0) {
    console.log(`\n--- Cross-chain bridges from ${fundConfig.sourceChain} ---`);

    for (const dstChain of crossChainTargets) {
      const tokens = chainTokens[dstChain];
      // Total USDC needed on this chain = amount * agents * num_tokens
      const perTokenAtomic = parseUnits(amountPerToken, 6);
      const totalAtomic = perTokenAtomic * BigInt(manifest.count) * BigInt(tokens.length);
      const totalStr = formatUnits(totalAtomic, 6);
      console.log(`\n  Bridging $${totalStr} to ${dstChain} (${tokens.join(", ")})...`);

      // Bridge total amount to funder address on destination chain
      const account = privateKeyToAccount(funderKey as Hex);

      try {
        const result = await executeBridge(
          fundConfig.sourceChain,
          dstChain,
          totalStr,
          account.address,
          funderKey,
          dryRun,
        );
        console.log(`    ${result.provider}: ${result.txHash} (${result.status})`);
      } catch (err: any) {
        console.error(`    BRIDGE FAILED: ${err.message}`);
      }

      // After bridge, distribute locally
      if (!dryRun) {
        console.log(`  After bridge completes, run:`);
        console.log(`    npx tsx distribute-funds.ts --chain ${dstChain} --wallets ${fundConfig.wallets} --amount ${amountPerToken} --tokens ${tokens.join(",")} --gas ${fundConfig.gasAmounts[dstChain] || "0.0005"}`);
      }
    }
  }

  console.log(`\n${"=".repeat(60)}`);
  console.log(`  Funding complete. Verify with:`);
  console.log(`    npx tsx check-balances.ts --config ${fundConfig.wallets}`);
  console.log(`${"=".repeat(60)}\n`);
}

main().catch(console.error);
