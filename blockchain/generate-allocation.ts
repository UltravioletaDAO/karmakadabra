/**
 * Karma Kadabra V2 — Randomized Funding Allocation Generator
 *
 * Generates a randomized allocation of $200 USDC across 40 agent wallets
 * on 8 chains (Base, Ethereum, Polygon, Arbitrum, Avalanche, Optimism, Celo, Monad).
 *
 * Algorithm:
 *   1. For each chain, compute avg = chain_budget / num_agents
 *   2. Assign each agent a random multiplier in [0.3, 1.7] * avg
 *   3. Enforce minimum of $0.10 per agent per chain
 *   4. Normalize so sum per chain equals chain_budget exactly
 *   5. Round to 2 decimals (USDC precision) with remainder correction
 *
 * Usage:
 *   npx tsx generate-allocation.ts
 *   npx tsx generate-allocation.ts --output config/allocation-v2.json
 *   npx tsx generate-allocation.ts --seed 42          # reproducible randomness
 *   npx tsx generate-allocation.ts --budget 250       # override total budget
 */

import { readFileSync, writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { CHAINS, DEFAULT_GAS_AMOUNTS } from "./lib/chains.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Token registry per chain (derived from chains.ts — Facilitator source of truth)
// ---------------------------------------------------------------------------

function getAvailableTokens(chainName: string): string[] {
  const chain = CHAINS[chainName];
  return chain ? Object.keys(chain.tokens) : ["USDC"];
}

// ---------------------------------------------------------------------------
// Chain Budgets (USD) — must sum to stablecoin portion of total budget
// All 8 chains including Ethereum L1
// ---------------------------------------------------------------------------

const CHAIN_BUDGETS: Record<string, number> = {
  base: 28,
  ethereum: 24,
  polygon: 24,
  arbitrum: 24,
  avalanche: 28,
  optimism: 24,
  celo: 20,
  monad: 20,
};

const MIN_PER_AGENT_PER_CHAIN = 0.1; // $0.10 minimum
const MULTIPLIER_LOW = 0.3;
const MULTIPLIER_HIGH = 1.7;

// Gas overrides — per agent per chain (native token amounts)
// Ethereum uses 0.0003 ETH (Facilitator pays gas for x402 ops)
const GAS_OVERRIDES: Record<string, string> = {
  ethereum: "0.0003",
};

// Bridge fee estimates (USD) — conservative
const BRIDGE_FEE_ESTIMATES: Record<string, number> = {
  base: 0.80,
  ethereum: 1.50,
  polygon: 0.50,
  arbitrum: 0.80,
  optimism: 0.80,
  celo: 0.50,
  monad: 1.00,
};

// ---------------------------------------------------------------------------
// Seeded PRNG (simple mulberry32 — deterministic if seed provided)
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Allocation Algorithm
// ---------------------------------------------------------------------------

function generateChainAllocation(
  agents: string[],
  chainBudget: number,
  rng: () => number,
): Record<string, string> {
  const n = agents.length;
  const avg = chainBudget / n;

  // Step 1: Generate raw random amounts
  const raw: number[] = agents.map(() => {
    const multiplier = MULTIPLIER_LOW + rng() * (MULTIPLIER_HIGH - MULTIPLIER_LOW);
    return avg * multiplier;
  });

  // Step 2: Enforce minimum
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] < MIN_PER_AGENT_PER_CHAIN) {
      raw[i] = MIN_PER_AGENT_PER_CHAIN;
    }
  }

  // Step 3: Normalize to match chain budget exactly
  const rawSum = raw.reduce((a, b) => a + b, 0);
  const scale = chainBudget / rawSum;
  const scaled = raw.map((v) => v * scale);

  // Step 4: Re-enforce minimum after scaling (edge case)
  for (let i = 0; i < scaled.length; i++) {
    if (scaled[i] < MIN_PER_AGENT_PER_CHAIN) {
      scaled[i] = MIN_PER_AGENT_PER_CHAIN;
    }
  }

  // Step 5: Round to 2 decimals
  const rounded = scaled.map((v) => Math.round(v * 100) / 100);

  // Step 6: Correct rounding remainder — adjust the largest allocation
  const roundedSum = rounded.reduce((a, b) => a + b, 0);
  const diff = Math.round((chainBudget - roundedSum) * 100) / 100;
  if (diff !== 0) {
    // Find the agent with the largest allocation and adjust
    let maxIdx = 0;
    for (let i = 1; i < rounded.length; i++) {
      if (rounded[i] > rounded[maxIdx]) maxIdx = i;
    }
    rounded[maxIdx] = Math.round((rounded[maxIdx] + diff) * 100) / 100;
  }

  // Build result
  const result: Record<string, string> = {};
  for (let i = 0; i < agents.length; i++) {
    result[agents[i]] = rounded[i].toFixed(2);
  }

  return result;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);

  const outputFile = args.includes("--output")
    ? resolve(__dirname, args[args.indexOf("--output") + 1])
    : resolve(__dirname, "config", "allocation.json");

  const walletsFile = args.includes("--wallets")
    ? resolve(__dirname, args[args.indexOf("--wallets") + 1])
    : resolve(__dirname, "config", "wallets.json");

  const seedArg = args.includes("--seed")
    ? parseInt(args[args.indexOf("--seed") + 1], 10)
    : null;

  const budgetOverride = args.includes("--budget")
    ? parseFloat(args[args.indexOf("--budget") + 1])
    : null;

  // Load wallets
  let manifest: WalletManifest;
  try {
    manifest = JSON.parse(readFileSync(walletsFile, "utf-8"));
  } catch {
    console.error(`ERROR: Cannot read ${walletsFile}. Run generate-wallets.ts first.`);
    process.exit(1);
  }

  const addresses = manifest.wallets.map((w) => w.address);
  const agentCount = addresses.length;

  // RNG setup
  const seed = seedArg ?? Date.now();
  const rng = seedArg !== null ? mulberry32(seed) : Math.random;
  if (seedArg !== null) {
    console.log(`Using deterministic seed: ${seed}`);
  }

  // Compute budgets
  const stablecoinBudget = Object.values(CHAIN_BUDGETS).reduce((a, b) => a + b, 0);
  const chainNames = Object.keys(CHAIN_BUDGETS);

  // Gas estimates (in USD) — approximate
  const gasUsdEstimates: Record<string, number> = {
    base: 0.0005 * 3200 * agentCount,      // ETH at ~$3200
    ethereum: 0.0003 * 3200 * agentCount,   // ETH at ~$3200 (minimal, Facilitator pays x402 gas)
    polygon: 0.1 * 0.4 * agentCount,        // POL at ~$0.40
    arbitrum: 0.0005 * 3200 * agentCount,   // ETH at ~$3200
    avalanche: 0.01 * 25 * agentCount,      // AVAX at ~$25
    optimism: 0.0005 * 3200 * agentCount,   // ETH at ~$3200
    celo: 0.01 * 0.5 * agentCount,          // CELO at ~$0.50
    monad: 0.01 * 1 * agentCount,           // MON at ~$1
  };
  const totalGasUsd = Object.values(gasUsdEstimates).reduce((a, b) => a + b, 0);
  const totalBridgeFees = Object.values(BRIDGE_FEE_ESTIMATES).reduce((a, b) => a + b, 0);
  const totalBudget = budgetOverride ?? 200;

  console.log(`\nKarma Kadabra V2 — Randomized Allocation Generator`);
  console.log(`${"=".repeat(55)}`);
  console.log(`  Agents:     ${agentCount}`);
  console.log(`  Chains:     ${chainNames.length} (${chainNames.join(", ")})`);
  console.log(`  Budget:     $${totalBudget.toFixed(2)}`);
  console.log(`  Stablecoins: $${stablecoinBudget.toFixed(2)}`);
  console.log(`  Gas (est):  $${totalGasUsd.toFixed(2)}`);
  console.log(`  Bridge (est): $${totalBridgeFees.toFixed(2)}`);
  console.log(`  Min/agent/chain: $${MIN_PER_AGENT_PER_CHAIN.toFixed(2)}`);
  console.log(`  Multiplier range: ${MULTIPLIER_LOW}x - ${MULTIPLIER_HIGH}x`);

  // Generate allocations per chain (multi-token)
  const chains: Record<string, {
    total_usd: number;
    agents: Record<string, { amount: string; token: string }>;
  }> = {};
  const agentTotals: Record<string, number> = {};
  for (const addr of addresses) agentTotals[addr] = 0;

  let globalMin = Infinity;
  let globalMax = 0;

  // Token distribution stats
  const tokenStats: Record<string, { count: number; total: number }> = {};

  for (const chainName of chainNames) {
    const budget = CHAIN_BUDGETS[chainName];
    const agentAmounts = generateChainAllocation(addresses, budget, rng);
    const availableTokens = getAvailableTokens(chainName);

    // Assign random token per agent (weighted: 60% USDC, 40% other)
    const agentsWithTokens: Record<string, { amount: string; token: string }> = {};
    for (const [addr, amt] of Object.entries(agentAmounts)) {
      let token = "USDC";
      if (availableTokens.length > 1) {
        const roll = rng();
        if (roll > 0.6) {
          // Pick a non-USDC token randomly
          const others = availableTokens.filter((t) => t !== "USDC");
          token = others[Math.floor(rng() * others.length)];
        }
      }
      agentsWithTokens[addr] = { amount: amt, token };

      // Stats
      if (!tokenStats[token]) tokenStats[token] = { count: 0, total: 0 };
      tokenStats[token].count++;
      tokenStats[token].total += parseFloat(amt);
    }

    chains[chainName] = {
      total_usd: budget,
      agents: agentsWithTokens,
    };

    // Track per-agent totals and min/max
    for (const [addr, { amount }] of Object.entries(agentsWithTokens)) {
      const val = parseFloat(amount);
      agentTotals[addr] += val;
      if (val < globalMin) globalMin = val;
      if (val > globalMax) globalMax = val;
    }

    // Verify chain sum + show token breakdown
    const chainSum = Object.values(agentsWithTokens).reduce((a, b) => a + parseFloat(b.amount), 0);
    const tokenBreakdown = Object.entries(
      Object.values(agentsWithTokens).reduce((acc, { token }) => {
        acc[token] = (acc[token] || 0) + 1;
        return acc;
      }, {} as Record<string, number>),
    ).map(([t, n]) => `${t}:${n}`).join(" ");
    console.log(`  ${chainName}: $${budget.toFixed(2)} — ${tokenBreakdown}`);
  }

  // Token summary
  console.log(`\n  Token Distribution:`);
  for (const [token, stats] of Object.entries(tokenStats).sort((a, b) => b[1].total - a[1].total)) {
    console.log(`    ${token}: ${stats.count} allocations, $${stats.total.toFixed(2)}`);
  }

  // Gas amounts: use overrides first, then DEFAULT_GAS_AMOUNTS from chains.ts
  const gas: Record<string, string> = {};
  for (const chain of chainNames) {
    gas[chain] = GAS_OVERRIDES[chain] || DEFAULT_GAS_AMOUNTS[chain] || "0.001";
  }

  // Bridge plan (source = avalanche, targets = all others)
  const bridgePlan: { source: string; targets: Record<string, string> } = {
    source: "avalanche",
    targets: {},
  };
  for (const chain of chainNames) {
    if (chain !== "avalanche") {
      bridgePlan.targets[chain] = CHAIN_BUDGETS[chain].toFixed(2);
    }
  }

  // Summary stats
  const agentTotalValues = Object.values(agentTotals);
  const avgPerAgent = agentTotalValues.reduce((a, b) => a + b, 0) / agentTotalValues.length;

  const allocation = {
    version: "1.0",
    budget_usd: totalBudget,
    source_chain: "avalanche",
    generated: new Date().toISOString(),
    seed: seedArg ?? "random",
    chains,
    gas,
    bridge_plan: bridgePlan,
    summary: {
      total_stablecoins_usd: stablecoinBudget,
      total_gas_usd: Math.round(totalGasUsd * 100) / 100,
      bridge_fees_est_usd: Math.round(totalBridgeFees * 100) / 100,
      agents: agentCount,
      chains: chainNames.length,
      min_per_agent_per_chain: globalMin.toFixed(2),
      max_per_agent_per_chain: globalMax.toFixed(2),
      avg_per_agent_total: avgPerAgent.toFixed(2),
    },
  };

  writeFileSync(outputFile, JSON.stringify(allocation, null, 2) + "\n");

  console.log(`\nAllocation written to: ${outputFile}`);
  console.log(`  Total stablecoins: $${stablecoinBudget.toFixed(2)}`);
  console.log(`  Avg per agent (all chains): $${avgPerAgent.toFixed(2)}`);
  console.log(`  Min single allocation: $${globalMin.toFixed(2)}`);
  console.log(`  Max single allocation: $${globalMax.toFixed(2)}`);
}

main();
