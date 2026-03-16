/**
 * Karma Kadabra V2 — Bridge Native Gas from Avalanche
 *
 * Bridges USDC on Avalanche → native tokens (ETH, POL, MON, CELO) on destination chains.
 * deBridge DLN supports cross-chain swaps: USDC → any token including native.
 *
 * Usage:
 *   PRIVATE_KEY=0x... npx tsx kk/bridge-gas.ts --dry-run          # Quote only
 *   PRIVATE_KEY=0x... npx tsx kk/bridge-gas.ts                    # Execute
 *   PRIVATE_KEY=0x... npx tsx kk/bridge-gas.ts --chains base,monad
 */

// IMPORTANT: Load .env.local BEFORE importing chains.ts (which reads RPC env vars at import time)
import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

import {
  createPublicClient,
  createWalletClient,
  http,
  formatUnits,
  formatEther,
  parseUnits,
  getAddress,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount, nonceManager } from "viem/accounts";
import { CHAINS, ERC20_ABI } from "./lib/chains.js";
import * as debridge from "./lib/debridge-client.js";

// deBridge uses zero address for native tokens
const NATIVE_TOKEN: Address = "0x0000000000000000000000000000000000000000";

// Gas amounts needed per chain (total for 24 agents + master wallet buffer).
// L2s have very cheap gas (~$0.001/TX), so agents need minimal ETH.
// Budget-optimized: ~$90 USDC available on Avalanche.
const GAS_TARGETS: Record<string, { amount: string; symbol: string }> = {
  base:     { amount: "0.005",  symbol: "ETH"  },  // 24*0.0002 + master buffer (~$12)
  ethereum: { amount: "0.004",  symbol: "ETH"  },  // 24*0.00015 + buffer (~$10) - L1 more expensive
  polygon:  { amount: "3.0",    symbol: "POL"  },  // 24*0.1 + buffer (~$1.50)
  arbitrum: { amount: "0.005",  symbol: "ETH"  },  // 24*0.0002 + buffer (~$12)
  optimism: { amount: "0.005",  symbol: "ETH"  },  // 24*0.0002 + buffer (~$12)
  celo:     { amount: "0.30",   symbol: "CELO" },  // 24*0.01 + buffer (~$0.15)
  monad:    { amount: "0.30",   symbol: "MON"  },  // 24*0.01 + buffer (~$0.50)
};

interface GasBridgeResult {
  chain: string;
  nativeAmount: string;
  symbol: string;
  usdcCost: string;
  status: "success" | "skipped" | "error" | "dry-run";
  txHash?: string;
  orderId?: string;
  error?: string;
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  const filterIdx = args.indexOf("--chains");
  const filterChains = filterIdx !== -1 ? args[filterIdx + 1].split(",").map(c => c.trim()) : null;

  const srcChain = "avalanche";
  const srcInfo = CHAINS[srcChain];

  console.log("=".repeat(70));
  console.log("  Karma Kadabra V2 — Bridge Native Gas Tokens");
  console.log("=".repeat(70));
  console.log("  Source: Avalanche (USDC → native on destination)");
  console.log("  Mode:   " + (dryRun ? "DRY RUN (quotes only)" : "LIVE"));

  const pk = (process.env.PRIVATE_KEY || process.env.WALLET_PRIVATE_KEY) as Hex;
  if (!pk && !dryRun) {
    throw new Error("PRIVATE_KEY not set");
  }

  const account = pk ? privateKeyToAccount(pk, { nonceManager }) : null;
  const publicClient = createPublicClient({ chain: srcInfo.chain, transport: http(srcInfo.rpcUrl) });

  // Check USDC balance on Avalanche
  if (account) {
    const usdcBal = await publicClient.readContract({
      address: srcInfo.usdc,
      abi: ERC20_ABI,
      functionName: "balanceOf",
      args: [account.address],
    }) as bigint;
    console.log("  Wallet: " + account.address);
    console.log("  USDC on Avalanche: $" + formatUnits(usdcBal, 6));
  }

  // Check current native balances on each destination
  console.log("\n  Current native balances & needs:");
  const chainsToProcess: Array<{ chain: string; amount: string; symbol: string; currentBal: string }> = [];

  for (const [chain, target] of Object.entries(GAS_TARGETS)) {
    if (filterChains && !filterChains.includes(chain)) continue;
    if (chain === srcChain) continue; // Skip Avalanche (already has AVAX)

    const dstInfo = CHAINS[chain];
    if (!dstInfo) continue;

    // Check if deBridge supports this chain
    if (!dstInfo.debridgeChainId) {
      console.log("    " + dstInfo.name.padEnd(10) + " | SKIP (no deBridge support)");
      continue;
    }

    let currentBal = "0";
    try {
      const dstPub = createPublicClient({ chain: dstInfo.chain, transport: http(dstInfo.rpcUrl) });
      const bal = await dstPub.getBalance({ address: account?.address || "0xD3868E1eD738CED6945A574a7c769433BeD5d474" as Address });
      currentBal = formatEther(bal);
    } catch { /* ignore */ }

    const needed = parseFloat(target.amount);
    const has = parseFloat(currentBal);
    const deficit = Math.max(0, needed - has);

    if (deficit <= 0) {
      console.log("    " + dstInfo.name.padEnd(10) + " | " + target.symbol.padEnd(4) + " has=" + currentBal.slice(0, 10).padStart(10) + " need=" + target.amount + " | OK (enough)");
      continue;
    }

    const deficitStr = deficit.toFixed(6);
    console.log("    " + dstInfo.name.padEnd(10) + " | " + target.symbol.padEnd(4) + " has=" + currentBal.slice(0, 10).padStart(10) + " need=" + target.amount + " | BRIDGE " + deficitStr);
    chainsToProcess.push({ chain, amount: deficitStr, symbol: target.symbol, currentBal });
  }

  if (chainsToProcess.length === 0) {
    console.log("\n  All chains have sufficient native gas. Nothing to bridge.");
    return;
  }

  // Get quotes for all chains
  console.log("\n" + "-".repeat(70));
  console.log("  Getting deBridge Quotes (USDC → native)");
  console.log("-".repeat(70));

  const quotes: Array<{ chain: string; amount: string; symbol: string; usdcNeeded: string; quote: debridge.DeBridgeQuote | null }> = [];
  let totalUsdcNeeded = 0;

  for (const { chain, amount, symbol } of chainsToProcess) {
    const dstInfo = CHAINS[chain];
    // Convert native amount to wei for the quote
    // deBridge quote: we specify dstChainTokenOutAmount instead of srcChainTokenInAmount
    // Actually, we need to do it differently: specify how much USDC to send to get ~X native
    // Let's estimate USDC needed based on rough prices, then let deBridge optimize

    // Rough price estimates (conservative)
    const nativePrices: Record<string, number> = {
      ETH: 2800,
      POL: 0.45,
      CELO: 0.55,
      MON: 1.00,  // estimate
    };

    const price = nativePrices[symbol] || 1;
    const usdEstimate = parseFloat(amount) * price * 1.15; // 15% buffer for slippage+fees
    const usdcAmount = Math.max(0.50, usdEstimate).toFixed(2); // minimum $0.50

    console.log("\n  " + dstInfo.name + ": need " + amount + " " + symbol + " (~$" + usdcAmount + " USDC)");

    try {
      const atomicUsdc = parseUnits(usdcAmount, 6).toString();
      const quote = await debridge.getQuote({
        srcChainId: srcInfo.debridgeChainId!,
        srcToken: srcInfo.usdc,
        dstChainId: dstInfo.debridgeChainId!,
        dstToken: NATIVE_TOKEN,
        amount: atomicUsdc,
        srcAddress: account?.address,
        dstAddress: account?.address,
      });

      const dstOut = quote.estimation?.dstChainTokenOut;
      if (dstOut) {
        const received = formatEther(BigInt(dstOut.amount));
        console.log("    Quote: send ~$" + usdcAmount + " USDC → receive ~" + received.slice(0, 12) + " " + symbol);
      }

      quotes.push({ chain, amount, symbol, usdcNeeded: usdcAmount, quote });
      totalUsdcNeeded += parseFloat(usdcAmount);
    } catch (err: any) {
      console.log("    ERROR getting quote: " + err.message.slice(0, 100));
      quotes.push({ chain, amount, symbol, usdcNeeded: usdcAmount, quote: null });
    }
  }

  console.log("\n  Total USDC needed: ~$" + totalUsdcNeeded.toFixed(2));

  if (dryRun) {
    console.log("\n  [DRY RUN] No bridges executed.");
    return;
  }

  if (!account) {
    console.error("  ERROR: No private key for live mode");
    process.exit(1);
  }

  // Execute bridges
  console.log("\n" + "-".repeat(70));
  console.log("  Executing Gas Bridges");
  console.log("-".repeat(70));

  const walletClient = createWalletClient({
    account,
    chain: srcInfo.chain,
    transport: http(srcInfo.rpcUrl),
  });

  const results: GasBridgeResult[] = [];

  for (const { chain, amount, symbol, usdcNeeded, quote } of quotes) {
    if (!quote || !quote.tx) {
      results.push({ chain, nativeAmount: amount, symbol, usdcCost: usdcNeeded, status: "error", error: "No quote available" });
      continue;
    }

    console.log("\n  Avalanche → " + CHAINS[chain].name + ": $" + usdcNeeded + " USDC → " + symbol);

    try {
      // Approve USDC
      const rawApprove = BigInt(quote.estimation?.srcChainTokenIn?.amount || parseUnits(usdcNeeded, 6).toString());
      const approveAmount = rawApprove + (rawApprove * 2n) / 100n; // 2% buffer

      console.log("    Approving " + formatUnits(approveAmount, 6) + " USDC...");
      const approveTx = await walletClient.writeContract({
        address: srcInfo.usdc,
        abi: ERC20_ABI,
        functionName: "approve",
        args: [getAddress(quote.tx.to) as Address, approveAmount],
      });
      console.log("    Approve TX: " + approveTx);
      await publicClient.waitForTransactionReceipt({ hash: approveTx });

      // Bridge TX
      console.log("    Sending bridge TX...");
      const bridgeTx = await walletClient.sendTransaction({
        to: getAddress(quote.tx.to) as Address,
        data: quote.tx.data as Hex,
        value: BigInt(quote.tx.value),
      });
      console.log("    Bridge TX: " + bridgeTx);
      console.log("    Order ID: " + quote.orderId);

      // Wait briefly for confirmation
      console.log("    Waiting for confirmation (up to 3 min)...");
      try {
        const status = await debridge.waitForOrder(quote.orderId, 180_000, 10_000);
        console.log("    Status: " + status.status);
      } catch {
        console.log("    WARNING: Confirmation timed out — order may still complete");
        console.log("    Track: https://app.debridge.finance/order?orderId=" + quote.orderId);
      }

      results.push({ chain, nativeAmount: amount, symbol, usdcCost: usdcNeeded, status: "success", txHash: bridgeTx, orderId: quote.orderId });
    } catch (err: any) {
      console.log("    ERROR: " + err.message.slice(0, 200));
      results.push({ chain, nativeAmount: amount, symbol, usdcCost: usdcNeeded, status: "error", error: err.message.slice(0, 200) });
    }
  }

  // Summary
  console.log("\n" + "=".repeat(70));
  console.log("  Gas Bridge Summary");
  console.log("=".repeat(70));
  for (const r of results) {
    const tag = r.status === "success" ? "[OK]" : "[FAIL]";
    console.log("  " + tag + " " + CHAINS[r.chain].name + ": $" + r.usdcCost + " USDC → " + r.nativeAmount + " " + r.symbol);
    if (r.txHash) console.log("       TX: " + r.txHash);
    if (r.orderId) console.log("       Order: " + r.orderId);
    if (r.error) console.log("       Error: " + r.error.slice(0, 100));
  }
  const ok = results.filter(r => r.status === "success").length;
  console.log("\n  Success: " + ok + "/" + results.length);
  console.log("=".repeat(70));
}

main().catch((err) => { console.error(err); process.exit(1); });
