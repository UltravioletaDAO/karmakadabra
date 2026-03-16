/**
 * Karma Kadabra V2 — Task 3.7: Reputation Leaderboard Query
 *
 * Queries reputation scores for all KK agents and outputs a sorted leaderboard.
 *
 * Data sources:
 *   1. Agent wallets from terraform/swarm/config/agent-wallets.json (swarm agents)
 *      OR scripts/kk/config/wallets.json (KK agents)
 *   2. Reputation scores from EM API: GET /api/v1/reputation/agents/{agent_id}
 *   3. Agent identity lookup: GET /api/v1/reputation/agents/{agent_id}/identity
 *
 * Since the API uses ERC-8004 agent IDs (not wallet addresses), we:
 *   - First check executors table for erc8004_agent_id (via EM API)
 *   - Fall back to iterating known agent IDs if wallet lookup unavailable
 *
 * Usage:
 *   npx tsx scripts/kk/lib/reputation-query.ts
 *   npx tsx scripts/kk/lib/reputation-query.ts --api https://api.execution.market
 *   npx tsx scripts/kk/lib/reputation-query.ts --wallets scripts/kk/config/wallets.json
 *   npx tsx scripts/kk/lib/reputation-query.ts --json  # Machine-readable output
 *
 * Output:
 *   Formatted leaderboard table sorted by reputation score (descending).
 */

import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../../.env.local") });

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_API_BASE = "https://api.execution.market";
const REPUTATION_TIERS = [
  { name: "Diamante", min: 81, max: 100 },
  { name: "Oro", min: 61, max: 80 },
  { name: "Plata", min: 31, max: 60 },
  { name: "Bronce", min: 0, max: 30 },
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WalletEntry {
  index: number;
  name: string;
  address: string;
  type?: "system" | "user";
  personality?: string;
}

interface ReputationResult {
  name: string;
  address: string;
  agentId: number | null;
  score: number;
  count: number;
  tier: string;
  network: string;
  error?: string;
}

interface AgentWalletsJson {
  metadata: Record<string, unknown>;
  wallets: Array<{
    index: number;
    name: string;
    address: string;
    personality: string;
    relay_address?: string;
    balances: Record<string, { usdc: string }>;
  }>;
  funding: Record<string, unknown>;
}

interface KKWalletsJson {
  version: string;
  wallets: WalletEntry[];
}

// ---------------------------------------------------------------------------
// Tier Resolution
// ---------------------------------------------------------------------------

function getTier(score: number): string {
  for (const tier of REPUTATION_TIERS) {
    if (score >= tier.min && score <= tier.max) {
      return tier.name;
    }
  }
  return "Bronce";
}

// ---------------------------------------------------------------------------
// Load Wallets
// ---------------------------------------------------------------------------

function loadWallets(walletsPath: string): WalletEntry[] {
  if (!existsSync(walletsPath)) {
    console.error(`ERROR: Wallet file not found: ${walletsPath}`);
    process.exit(1);
  }

  const raw = readFileSync(walletsPath, "utf-8");
  const data = JSON.parse(raw);

  // Handle terraform/swarm/config/agent-wallets.json format
  if (data.metadata && Array.isArray(data.wallets) && data.wallets[0]?.personality) {
    const agentData = data as AgentWalletsJson;
    return agentData.wallets.map((w) => ({
      index: w.index,
      name: w.name,
      address: w.address,
      personality: w.personality,
    }));
  }

  // Handle scripts/kk/config/wallets.json format
  if (data.version && Array.isArray(data.wallets)) {
    const kkData = data as KKWalletsJson;
    return kkData.wallets.map((w) => ({
      index: w.index,
      name: w.name,
      address: w.address,
      type: w.type,
    }));
  }

  console.error("ERROR: Unrecognized wallet file format");
  process.exit(1);
}

// ---------------------------------------------------------------------------
// API Queries
// ---------------------------------------------------------------------------

async function queryReputationByAgentId(
  apiBase: string,
  agentId: number,
): Promise<{ score: number; count: number; network: string } | null> {
  try {
    const url = `${apiBase}/api/v1/reputation/agents/${agentId}`;
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(10000),
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    return {
      score: data.score ?? 0,
      count: data.count ?? 0,
      network: data.network ?? "base",
    };
  } catch {
    return null;
  }
}

async function lookupAgentIdByWallet(
  apiBase: string,
  walletAddress: string,
): Promise<number | null> {
  // Try to find the agent's ERC-8004 ID via the executors table
  // The EM API doesn't have a direct wallet->agent_id endpoint,
  // so we query the workers endpoint which includes erc8004_agent_id
  try {
    const url = `${apiBase}/api/v1/workers?wallet_address=${walletAddress}`;
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) return null;

    const data = await response.json();
    // Response may be array or object with results
    const workers = Array.isArray(data) ? data : data.results || data.workers || [];
    for (const worker of workers) {
      if (
        worker.erc8004_agent_id &&
        worker.wallet_address?.toLowerCase() === walletAddress.toLowerCase()
      ) {
        return Number(worker.erc8004_agent_id);
      }
    }
    return null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Main Leaderboard Query
// ---------------------------------------------------------------------------

async function queryLeaderboard(
  wallets: WalletEntry[],
  apiBase: string,
): Promise<ReputationResult[]> {
  const results: ReputationResult[] = [];

  console.log(`Querying reputation for ${wallets.length} agents...`);
  console.log(`API: ${apiBase}\n`);

  // Query in batches of 5 to avoid overwhelming the API
  const BATCH_SIZE = 5;

  for (let i = 0; i < wallets.length; i += BATCH_SIZE) {
    const batch = wallets.slice(i, i + BATCH_SIZE);
    const batchPromises = batch.map(async (wallet) => {
      // Step 1: Try to resolve agent ID from wallet address
      const agentId = await lookupAgentIdByWallet(apiBase, wallet.address);

      // Step 2: Query reputation if we have an agent ID
      let reputation: { score: number; count: number; network: string } | null =
        null;
      if (agentId) {
        reputation = await queryReputationByAgentId(apiBase, agentId);
      }

      const score = reputation?.score ?? 0;

      const result: ReputationResult = {
        name: wallet.name,
        address: wallet.address,
        agentId,
        score,
        count: reputation?.count ?? 0,
        tier: getTier(score),
        network: reputation?.network ?? "base",
      };

      if (!agentId) {
        result.error = "No ERC-8004 ID";
      } else if (!reputation) {
        result.error = "No reputation data";
      }

      return result;
    });

    const batchResults = await Promise.all(batchPromises);
    results.push(...batchResults);

    // Progress indicator
    const processed = Math.min(i + BATCH_SIZE, wallets.length);
    process.stdout.write(`  Progress: ${processed}/${wallets.length}\r`);
  }

  console.log(""); // Clear progress line

  // Sort by score descending, then by name ascending for ties
  results.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.name.localeCompare(b.name);
  });

  return results;
}

// ---------------------------------------------------------------------------
// Output Formatting
// ---------------------------------------------------------------------------

function printLeaderboard(results: ReputationResult[]): void {
  console.log("");
  console.log("=".repeat(105));
  console.log("# KarmaCadabra V2 -- Reputation Leaderboard");
  console.log("=".repeat(105));
  console.log(
    `${"Rank".padEnd(6)}| ${"Agent Name".padEnd(26)}| ${"Address".padEnd(14)}| ${"Agent ID".padEnd(10)}| ${"Score".padEnd(7)}| ${"Count".padEnd(7)}| Tier`,
  );
  console.log("-".repeat(105));

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const rank = `#${i + 1}`;
    const addrShort = `${r.address.slice(0, 6)}...${r.address.slice(-4)}`;
    const agentIdStr = r.agentId ? String(r.agentId) : "-";
    const scoreStr = r.error ? `${r.score} (*)` : String(r.score);

    console.log(
      `${rank.padEnd(6)}| ${r.name.padEnd(26)}| ${addrShort.padEnd(14)}| ${agentIdStr.padEnd(10)}| ${scoreStr.padEnd(7)}| ${String(r.count).padEnd(7)}| ${r.tier}`,
    );
  }

  console.log("-".repeat(105));

  // Tier distribution
  const tierCounts: Record<string, number> = {};
  for (const r of results) {
    tierCounts[r.tier] = (tierCounts[r.tier] || 0) + 1;
  }

  console.log("\nTier Distribution:");
  for (const tier of REPUTATION_TIERS) {
    const count = tierCounts[tier.name] || 0;
    console.log(`  ${tier.name.padEnd(10)} (${tier.min}-${tier.max}): ${count} agents`);
  }

  // Agents with errors
  const withErrors = results.filter((r) => r.error);
  if (withErrors.length > 0) {
    console.log(`\n(*) ${withErrors.length} agents with issues:`);
    for (const r of withErrors) {
      console.log(`  - ${r.name}: ${r.error}`);
    }
  }

  // Stats
  const scored = results.filter((r) => !r.error);
  if (scored.length > 0) {
    const avgScore =
      scored.reduce((sum, r) => sum + r.score, 0) / scored.length;
    const maxScore = Math.max(...scored.map((r) => r.score));
    const minScore = Math.min(...scored.map((r) => r.score));
    console.log(`\nStats (${scored.length} agents with data):`);
    console.log(`  Average score: ${avgScore.toFixed(1)}`);
    console.log(`  Highest score: ${maxScore}`);
    console.log(`  Lowest score:  ${minScore}`);
  }

  console.log(`\nTotal agents: ${results.length}`);
  console.log(`Generated: ${new Date().toISOString()}`);
}

function printJson(results: ReputationResult[]): void {
  const output = {
    generated: new Date().toISOString(),
    totalAgents: results.length,
    leaderboard: results.map((r, i) => ({
      rank: i + 1,
      ...r,
    })),
    tierDistribution: Object.fromEntries(
      REPUTATION_TIERS.map((t) => [
        t.name,
        results.filter((r) => r.score >= t.min && r.score <= t.max).length,
      ]),
    ),
  };

  console.log(JSON.stringify(output, null, 2));
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);

  // Parse flags
  const apiIdx = args.indexOf("--api");
  const apiBase = apiIdx >= 0 ? args[apiIdx + 1] : DEFAULT_API_BASE;

  const walletsIdx = args.indexOf("--wallets");
  const walletsFile =
    walletsIdx >= 0
      ? args[walletsIdx + 1]
      : resolve(__dirname, "../../../terraform/swarm/config/agent-wallets.json");

  const jsonOutput = args.includes("--json");

  // Also try KK wallets if swarm wallets not found
  let finalWalletsFile = walletsFile;
  if (!existsSync(finalWalletsFile)) {
    const kkWallets = resolve(__dirname, "../config/wallets.json");
    if (existsSync(kkWallets)) {
      finalWalletsFile = kkWallets;
      if (!jsonOutput) {
        console.log(
          `Swarm wallets not found, using KK wallets: ${kkWallets}`,
        );
      }
    }
  }

  const wallets = loadWallets(finalWalletsFile);

  if (!jsonOutput) {
    console.log(`\nLoaded ${wallets.length} agents from ${finalWalletsFile}`);
  }

  const results = await queryLeaderboard(wallets, apiBase);

  if (jsonOutput) {
    printJson(results);
  } else {
    printLeaderboard(results);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
