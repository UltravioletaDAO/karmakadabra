/**
 * Karma Kadabra V2 -- Bridge USDC from Source Chain to Target Chains
 *
 * Reads allocation.json bridge_plan and executes cross-chain USDC bridges
 * via deBridge DLN (7/8 chains) or Squid Router (Celo fallback).
 *
 * Usage:
 *   npx tsx kk/bridge-from-source.ts --dry-run
 *   npx tsx kk/bridge-from-source.ts --chains base,polygon
 *   npx tsx kk/bridge-from-source.ts --source avalanche --allocation config/allocation.json
 *   npx tsx kk/bridge-from-source.ts                          # execute all
 */

import {
  createPublicClient,
  createWalletClient,
  http,
  parseUnits,
  formatUnits,
  getAddress,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount, nonceManager } from "viem/accounts";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import { CHAINS, ERC20_ABI, getChain } from "./lib/chains.js";
import { selectBridge } from "./lib/bridge-router.js";
import * as debridge from "./lib/debridge-client.js";
import * as squid from "./lib/squid-client.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AllocationJson {
  bridge_plan: {
    source: string;
    targets: Record<string, string>;
  };
  [key: string]: unknown;
}

interface BridgeResult {
  chain: string;
  amount: string;
  provider: string;
  approveTx: string | null;
  bridgeTx: string | null;
  orderId: string | null;
  status: "success" | "skipped" | "error" | "dry-run";
  error?: string;
}

// ---------------------------------------------------------------------------
// CLI Argument Parsing
// ---------------------------------------------------------------------------

function parseArgs(): {
  dryRun: boolean;
  source: string;
  allocationPath: string;
  filterChains: string[] | null;
  amountOverride: string | null;
} {
  const args = process.argv.slice(2);

  const dryRun = args.includes("--dry-run");

  let source = "avalanche";
  const srcIdx = args.indexOf("--source");
  if (srcIdx !== -1 && args[srcIdx + 1]) {
    source = args[srcIdx + 1];
  }

  let allocationPath = resolve(__dirname, "config/allocation.json");
  const allocIdx = args.indexOf("--allocation");
  if (allocIdx !== -1 && args[allocIdx + 1]) {
    allocationPath = resolve(args[allocIdx + 1]);
  }

  let filterChains: string[] | null = null;
  const chainsIdx = args.indexOf("--chains");
  if (chainsIdx !== -1 && args[chainsIdx + 1]) {
    filterChains = args[chainsIdx + 1].split(",").map((c) => c.trim());
  }

  let amountOverride: string | null = null;
  const amtIdx = args.indexOf("--amount");
  if (amtIdx !== -1 && args[amtIdx + 1]) {
    amountOverride = args[amtIdx + 1];
  }

  return { dryRun, source, allocationPath, filterChains, amountOverride };
}

// ---------------------------------------------------------------------------
// Bridge Execution (single chain)
// ---------------------------------------------------------------------------

async function bridgeToChain(
  srcChain: string,
  dstChain: string,
  amountUsd: string,
  account: ReturnType<typeof privateKeyToAccount>,
  dryRun: boolean,
): Promise<BridgeResult> {
  const srcInfo = getChain(srcChain);
  const dstInfo = getChain(dstChain);
  const route = selectBridge(srcChain, dstChain);
  const atomicAmount = parseUnits(amountUsd, 6).toString();

  console.log(
    "\n  " + srcInfo.name + " -> " + dstInfo.name + ": $" + amountUsd + " USDC [" + route.provider + "]",
  );

  if (route.provider === "direct") {
    console.log("    SKIP: same chain, no bridge needed");
    return {
      chain: dstChain,
      amount: amountUsd,
      provider: "direct",
      approveTx: null,
      bridgeTx: null,
      orderId: null,
      status: "skipped",
    };
  }

  if (dryRun) {
    console.log("    DRY RUN: would bridge $" + amountUsd + " via " + route.provider);
    console.log(
      "    Fee est: ~" + route.estimatedFeePercent + "%, time est: ~" + route.estimatedTimeSec + "s",
    );
    return {
      chain: dstChain,
      amount: amountUsd,
      provider: route.provider,
      approveTx: null,
      bridgeTx: null,
      orderId: null,
      status: "dry-run",
    };
  }

  const walletClient = createWalletClient({
    account,
    chain: srcInfo.chain,
    transport: http(srcInfo.rpcUrl),
  });

  const publicClient = createPublicClient({
    chain: srcInfo.chain,
    transport: http(srcInfo.rpcUrl),
  });

  // --- deBridge route ---
  if (route.provider === "debridge") {
    const srcDlnId = CHAINS[srcChain].debridgeChainId;
    const dstDlnId = CHAINS[dstChain].debridgeChainId;
    if (!srcDlnId || !dstDlnId) {
      const msg = "deBridge not available: src=" + srcDlnId + ", dst=" + dstDlnId;
      console.log("    ERROR: " + msg);
      return {
        chain: dstChain,
        amount: amountUsd,
        provider: "debridge",
        approveTx: null,
        bridgeTx: null,
        orderId: null,
        status: "error",
        error: msg,
      };
    }

    console.log("    Requesting deBridge quote...");
    const quote = await debridge.getQuote({
      srcChainId: srcDlnId,
      srcToken: srcInfo.usdc,
      dstChainId: dstDlnId,
      dstToken: dstInfo.usdc,
      amount: atomicAmount,
      srcAddress: account.address,
      dstAddress: account.address,
    });

    if (!quote.tx) {
      const msg = "deBridge: no TX data -- " + (quote.errorMessage || "unknown error");
      console.log("    ERROR: " + msg);
      return {
        chain: dstChain,
        amount: amountUsd,
        provider: "debridge",
        approveTx: null,
        bridgeTx: null,
        orderId: quote.orderId || null,
        status: "error",
        error: msg,
      };
    }

    const dstOut = quote.estimation?.dstChainTokenOut;
    if (dstOut) {
      console.log(
        "    Quote: receive ~" +
          formatUnits(BigInt(dstOut.amount), 6) +
          " USDC (~$" +
          dstOut.approximateUsdValue +
          ")",
      );
    }

    // Step 1: Approve USDC to deBridge contract
    // Add 2% buffer — deBridge execution fee can vary between quote and TX
    const rawApprove = BigInt(
      quote.estimation?.srcChainTokenIn?.amount || atomicAmount,
    );
    const approveAmount = rawApprove + (rawApprove * 2n) / 100n;
    console.log(
      "    Approving " + formatUnits(approveAmount, 6) + " USDC to " + quote.tx.to + "...",
    );
    const approveTx = await walletClient.writeContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "approve",
      args: [getAddress(quote.tx.to) as Address, approveAmount],
    });
    console.log("    Approve TX: " + approveTx);
    await publicClient.waitForTransactionReceipt({ hash: approveTx });

    // Step 2: Send bridge TX
    console.log("    Sending bridge TX...");
    const bridgeTx = await walletClient.sendTransaction({
      to: getAddress(quote.tx.to) as Address,
      data: quote.tx.data as Hex,
      value: BigInt(quote.tx.value),
    });
    console.log("    Bridge TX: " + bridgeTx);
    console.log("    Order ID: " + quote.orderId);

    // Step 3: Wait for bridge confirmation
    console.log("    Waiting for bridge confirmation (up to 5 min)...");
    try {
      const status = await debridge.waitForOrder(quote.orderId, 300_000, 10_000);
      console.log("    Bridge status: " + status.status);
      if (status.dstChainTxHash) {
        console.log("    Dst TX: " + status.dstChainTxHash);
      }
    } catch (_err: any) {
      console.log(
        "    WARNING: Bridge confirmation timed out -- order may still complete",
      );
      console.log(
        "    Track at: https://app.debridge.finance/order?orderId=" + quote.orderId,
      );
    }

    return {
      chain: dstChain,
      amount: amountUsd,
      provider: "debridge",
      approveTx,
      bridgeTx,
      orderId: quote.orderId,
      status: "success",
    };
  }

  // --- Squid route (Celo) ---
  if (route.provider === "squid") {
    console.log("    Requesting Squid quote...");
    const quote = await squid.getRoute({
      fromChainId: String(srcInfo.chainId),
      toChainId: String(dstInfo.chainId),
      fromToken: srcInfo.usdc,
      toToken: dstInfo.usdc,
      fromAmount: atomicAmount,
      fromAddress: account.address,
      toAddress: account.address,
    });

    if (!quote.route.transactionRequest) {
      const msg = "Squid: no transaction request in route";
      console.log("    ERROR: " + msg);
      return {
        chain: dstChain,
        amount: amountUsd,
        provider: "squid",
        approveTx: null,
        bridgeTx: null,
        orderId: quote.route.quoteId || null,
        status: "error",
        error: msg,
      };
    }

    const target = getAddress(quote.route.transactionRequest.target) as Address;

    // Step 1: Approve USDC
    console.log("    Approving " + amountUsd + " USDC to " + target + "...");
    const approveTx = await walletClient.writeContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "approve",
      args: [target, BigInt(atomicAmount)],
    });
    console.log("    Approve TX: " + approveTx);
    await publicClient.waitForTransactionReceipt({ hash: approveTx });

    // Step 2: Send bridge TX
    console.log("    Sending Squid bridge TX...");
    const bridgeTx = await walletClient.sendTransaction({
      to: target,
      data: quote.route.transactionRequest.data as Hex,
      value: BigInt(quote.route.transactionRequest.value),
    });
    console.log("    Bridge TX: " + bridgeTx);

    // Step 3: Wait for bridge confirmation
    console.log("    Waiting for Squid confirmation (up to 5 min)...");
    try {
      const status = await squid.waitForTransaction(
        {
          txHash: bridgeTx,
          quoteId: quote.route.quoteId,
          requestId: quote.requestId,
        },
        300_000,
        10_000,
      );
      console.log("    Squid status: " + status.squidTransactionStatus);
    } catch (_err: any) {
      console.log(
        "    WARNING: Squid confirmation timed out -- TX may still complete",
      );
    }

    return {
      chain: dstChain,
      amount: amountUsd,
      provider: "squid",
      approveTx,
      bridgeTx,
      orderId: quote.route.quoteId,
      status: "success",
    };
  }

  return {
    chain: dstChain,
    amount: amountUsd,
    provider: route.provider,
    approveTx: null,
    bridgeTx: null,
    orderId: null,
    status: "error",
    error: "Unsupported bridge provider: " + route.provider,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const { dryRun, source, allocationPath, filterChains, amountOverride } = parseArgs();

  console.log("=".repeat(70));
  console.log("  Karma Kadabra V2 -- Bridge from Source Chain");
  console.log("=".repeat(70));
  console.log("  Source chain:  " + source);
  console.log("  Allocation:    " + allocationPath);
  console.log("  Mode:          " + (dryRun ? "DRY RUN" : "LIVE"));
  if (filterChains) {
    console.log("  Filter chains: " + filterChains.join(", "));
  }
  if (amountOverride) {
    console.log("  Amount override: $" + amountOverride);
  }

  // Load allocation
  const allocationRaw = readFileSync(allocationPath, "utf-8");
  const allocation: AllocationJson = JSON.parse(allocationRaw);

  if (!allocation.bridge_plan) {
    throw new Error("allocation.json missing bridge_plan section");
  }

  const { source: planSource, targets } = allocation.bridge_plan;
  const effectiveSource = source || planSource;

  if (!CHAINS[effectiveSource]) {
    throw new Error(
      "Unknown source chain: " +
        effectiveSource +
        ". Valid: " +
        Object.keys(CHAINS).join(", "),
    );
  }

  // Determine which chains to bridge to
  // --amount + --chains allows ad-hoc bridges not in allocation (e.g., reverse bridges)
  let targetChains: [string, string][];
  if (amountOverride && filterChains) {
    targetChains = filterChains.map((c) => [c, amountOverride]);
  } else {
    targetChains = Object.entries(targets);
    if (filterChains) {
      targetChains = targetChains.filter(([chain]) => filterChains.includes(chain));
    }
  }

  // Skip source chain (no bridge needed)
  targetChains = targetChains.filter(([chain]) => chain !== effectiveSource);

  console.log("\n  Targets (" + targetChains.length + "):");
  let totalBridge = 0;
  for (const [chain, amount] of targetChains) {
    const route = selectBridge(effectiveSource, chain);
    const bridgeNote = route.provider === "squid" ? " (via Squid)" : "";
    console.log("    " + chain + ": $" + amount + " USDC" + bridgeNote);
    totalBridge += parseFloat(amount);
  }
  console.log("\n  Total to bridge: $" + totalBridge.toFixed(2) + " USDC");

  // Check source balance
  const srcInfo = getChain(effectiveSource);
  const publicClient = createPublicClient({
    chain: srcInfo.chain,
    transport: http(srcInfo.rpcUrl),
  });

  // Get private key
  const privateKey = process.env.PRIVATE_KEY;
  if (!privateKey && !dryRun) {
    throw new Error("PRIVATE_KEY env var not set. Set it or use --dry-run");
  }

  const account = privateKey
    ? privateKeyToAccount(privateKey as Hex, { nonceManager })
    : null;

  if (account) {
    const balance = await publicClient.readContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "balanceOf",
      args: [account.address],
    });
    const balanceFormatted = formatUnits(balance as bigint, 6);
    console.log("\n  Master wallet: " + account.address);
    console.log("  USDC balance on " + srcInfo.name + ": $" + balanceFormatted);

    if (parseFloat(balanceFormatted) < totalBridge) {
      throw new Error(
        "Insufficient USDC on " +
          srcInfo.name +
          ": have $" +
          balanceFormatted +
          ", need $" +
          totalBridge.toFixed(2),
      );
    }
  } else {
    console.log("\n  Master wallet: (dry-run, no key loaded)");
  }

  // Execute bridges sequentially (avoid nonce issues)
  console.log("\n" + "-".repeat(70));
  console.log("  Executing Bridges");
  console.log("-".repeat(70));

  const results: BridgeResult[] = [];

  for (const [chain, amount] of targetChains) {
    try {
      const result = await bridgeToChain(
        effectiveSource,
        chain,
        amount,
        account!,
        dryRun,
      );
      results.push(result);
    } catch (err: any) {
      console.log("\n  ERROR bridging to " + chain + ": " + err.message);
      results.push({
        chain,
        amount,
        provider: "unknown",
        approveTx: null,
        bridgeTx: null,
        orderId: null,
        status: "error",
        error: err.message,
      });
    }
  }

  // Summary
  console.log("\n" + "=".repeat(70));
  console.log("  Bridge Summary");
  console.log("=".repeat(70));

  const successful = results.filter((r) => r.status === "success");
  const skipped = results.filter(
    (r) => r.status === "skipped" || r.status === "dry-run",
  );
  const errors = results.filter((r) => r.status === "error");

  for (const r of results) {
    const icon =
      r.status === "success"
        ? "[OK]"
        : r.status === "error"
          ? "[FAIL]"
          : "[SKIP]";
    console.log(
      "  " +
        icon +
        " " +
        r.chain +
        ": $" +
        r.amount +
        " via " +
        r.provider +
        " -- " +
        r.status,
    );
    if (r.bridgeTx) console.log("       TX: " + r.bridgeTx);
    if (r.orderId) console.log("       Order: " + r.orderId);
    if (r.error) console.log("       Error: " + r.error);
  }

  console.log("\n  Totals:");
  console.log("    Success: " + successful.length);
  console.log("    Skipped: " + skipped.length);
  console.log("    Errors:  " + errors.length);
  console.log("=".repeat(70));

  if (errors.length > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("\nFATAL: " + err.message);
  process.exit(1);
});
