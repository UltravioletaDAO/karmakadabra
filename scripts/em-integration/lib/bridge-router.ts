/**
 * Karma Kadabra V2 — Smart Bridge Router
 *
 * Picks the optimal bridge for each cross-chain transfer based on:
 *   1. Chain coverage (not all bridges support all chains)
 *   2. Fees (prefer cheapest)
 *   3. Availability
 *
 * Priority:
 *   - deBridge DLN: 7/8 chains (all except Celo), fees ~0.04-0.1%, fastest
 *   - Squid Router: 7/8 chains (all except Monad), fees ~0.1-0.3%, CCTP for USDC
 *   - NEAR Intents: future integration (TODO — payment flexibility wrapper)
 *
 * Together they cover ALL 8 chains:
 *   - deBridge for: Base, ETH, Polygon, Arbitrum, Avalanche, Optimism, Monad
 *   - Squid for: Celo (only bridge that covers it)
 */

import type { Address } from "viem";
import { CHAINS, type ChainInfo } from "./chains.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BridgeProvider = "debridge" | "squid" | "near-intents" | "direct";

export interface BridgeRoute {
  provider: BridgeProvider;
  srcChain: string;
  dstChain: string;
  srcToken: Address;
  dstToken: Address;
  estimatedFeePercent: number;
  estimatedTimeSec: number;
  available: boolean;
  reason?: string;
}

// ---------------------------------------------------------------------------
// Router Logic
// ---------------------------------------------------------------------------

/**
 * Determine the best bridge provider for a given src→dst chain pair.
 *
 * Rules:
 * 1. Same chain → "direct" (no bridge needed)
 * 2. Dst = Celo → "squid" (deBridge doesn't support Celo)
 * 3. Dst = Monad → "debridge" (Squid doesn't support Monad)
 * 4. Otherwise → "debridge" (lower fees, faster)
 */
export function selectBridge(srcChain: string, dstChain: string): BridgeRoute {
  const src = CHAINS[srcChain];
  const dst = CHAINS[dstChain];

  if (!src) throw new Error(`Unknown source chain: ${srcChain}`);
  if (!dst) throw new Error(`Unknown destination chain: ${dstChain}`);

  // Same chain — direct ERC-20 transfer
  if (srcChain === dstChain) {
    return {
      provider: "direct",
      srcChain,
      dstChain,
      srcToken: src.usdc,
      dstToken: dst.usdc,
      estimatedFeePercent: 0,
      estimatedTimeSec: 3,
      available: true,
    };
  }

  // Celo destination — must use Squid (deBridge doesn't support Celo)
  if (dstChain === "celo") {
    return {
      provider: "squid",
      srcChain,
      dstChain,
      srcToken: src.usdc,
      dstToken: dst.usdc,
      estimatedFeePercent: 0.15,
      estimatedTimeSec: 30,
      available: true,
    };
  }

  // Celo source — must use Squid (deBridge doesn't support Celo)
  if (srcChain === "celo") {
    return {
      provider: "squid",
      srcChain,
      dstChain,
      srcToken: src.usdc,
      dstToken: dst.usdc,
      estimatedFeePercent: 0.15,
      estimatedTimeSec: 30,
      available: true,
    };
  }

  // Monad — must use deBridge (Squid doesn't support Monad)
  if (dstChain === "monad" || srcChain === "monad") {
    return {
      provider: "debridge",
      srcChain,
      dstChain,
      srcToken: src.usdc,
      dstToken: dst.usdc,
      estimatedFeePercent: 0.08,
      estimatedTimeSec: 10,
      available: true,
    };
  }

  // Default: deBridge (lower fees than Squid for most routes)
  return {
    provider: "debridge",
    srcChain,
    dstChain,
    srcToken: src.usdc,
    dstToken: dst.usdc,
    estimatedFeePercent: 0.08,
    estimatedTimeSec: 10,
    available: true,
  };
}

/**
 * Generate a bridge plan for distributing from one source chain to multiple destinations.
 */
export function planDistribution(
  srcChain: string,
  dstChains: string[],
): BridgeRoute[] {
  return dstChains.map((dst) => selectBridge(srcChain, dst));
}

/**
 * Summarize a distribution plan.
 */
export function summarizePlan(routes: BridgeRoute[]): void {
  const byProvider = new Map<BridgeProvider, number>();
  for (const r of routes) {
    byProvider.set(r.provider, (byProvider.get(r.provider) || 0) + 1);
  }

  console.log("\nBridge Distribution Plan:");
  console.log("─".repeat(60));
  for (const r of routes) {
    const tag = r.provider === "direct" ? "[DIRECT]" : `[${r.provider.toUpperCase()}]`;
    console.log(`  ${tag} ${r.srcChain} → ${r.dstChain} (~${r.estimatedFeePercent}%, ~${r.estimatedTimeSec}s)`);
  }
  console.log("─".repeat(60));
  for (const [provider, count] of byProvider) {
    console.log(`  ${provider}: ${count} routes`);
  }
}

// ---------------------------------------------------------------------------
// TODO: NEAR Intents Bridge Wrapper (Future — Payment Flexibility)
// ---------------------------------------------------------------------------
// When a worker wants to receive payment on a different chain than the payer
// sends (e.g., paid in USDC on Ethereum, receive on Avalanche), use NEAR
// Intents as a transparent bridge wrapper:
//
//   1. Payer signs payment on source chain
//   2. Platform detects worker's preferred receive chain
//   3. If different from source → route through NEAR Intents 1Click API
//   4. Worker receives USDC on their preferred chain
//
// API: https://1click.chaindefuser.com/v0/
// MCP: @iqai/mcp-near-intent-swaps (5 tools)
// Fees: ~0.01-0.05% (cheapest of all 3 bridges)
// Speed: 5-15 seconds
//
// This is NOT in scope for KK v2 Phase 1 but is the planned solution for
// cross-chain payment flexibility in Phase 4+.
