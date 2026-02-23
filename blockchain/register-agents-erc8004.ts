/**
 * Karma Kadabra V2 — Phase 3 Tasks 3.1 + 3.2: Bulk ERC-8004 Registration
 *
 * Two-step registration for all 24 KK agents:
 *   Step 1: Register as a worker (executor) in the EM platform database
 *   Step 2: Register ERC-8004 on-chain identity via EM API -> Facilitator (gasless)
 *
 * Supports multi-chain registration: each agent can be registered on
 * multiple ERC-8004 networks in a single run.
 *
 * Usage:
 *   npx tsx scripts/kk/register-agents-erc8004.ts                         # Base only (default)
 *   npx tsx scripts/kk/register-agents-erc8004.ts --networks base,polygon,arbitrum
 *   npx tsx scripts/kk/register-agents-erc8004.ts --agents 0,1,2          # Specific agents
 *   npx tsx scripts/kk/register-agents-erc8004.ts --dry-run               # Preview only
 *   npx tsx scripts/kk/register-agents-erc8004.ts --force                 # Re-register even if exists
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import type { WalletManifest, WalletEntry } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const EM_API_URL =
  process.env.EM_API_URL || "https://api.execution.market";
const EM_API_KEY = process.env.EM_API_KEY || "";
const DELAY_MS = 2_000; // 2s between API calls to avoid rate limiting
const IDENTITIES_FILE = resolve(__dirname, "config", "identities.json");

const SUPPORTED_NETWORKS = [
  "base",
  "polygon",
  "arbitrum",
  "avalanche",
  "celo",
  "monad",
  "optimism",
  "ethereum",
  // testnets
  "ethereum-sepolia",
  "base-sepolia",
  "polygon-amoy",
  "arbitrum-sepolia",
  "celo-sepolia",
  "avalanche-fuji",
] as const;

type Network = (typeof SUPPORTED_NETWORKS)[number];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkerRegistrationResult {
  executor_id: string | null;
  created: boolean;
  error?: string;
}

interface ERC8004RegistrationResult {
  agent_id: number | null;
  transaction: string | null;
  network: string;
  error?: string;
}

interface AgentIdentity {
  address: string;
  name: string;
  index: number;
  type: "system" | "user";
  executor_id: string | null;
  registrations: {
    [network: string]: {
      agent_id: number | null;
      transaction: string | null;
      registered_at: string;
      status: "success" | "already_registered" | "failed";
      error?: string;
    };
  };
}

interface IdentitiesFile {
  version: string;
  updated_at: string;
  api_url: string;
  agents: AgentIdentity[];
}

interface RegistrationSummary {
  workers_registered: number;
  workers_existing: number;
  workers_failed: number;
  erc8004_registered: number;
  erc8004_existing: number;
  erc8004_failed: number;
}

// ---------------------------------------------------------------------------
// CLI Argument Parsing
// ---------------------------------------------------------------------------

function parseArgs(): {
  walletsFile: string;
  networks: Network[];
  agentIndices: number[] | null;
  dryRun: boolean;
  force: boolean;
} {
  const args = process.argv.slice(2);

  // --wallets <path>
  const walletsFile = args.includes("--wallets")
    ? args[args.indexOf("--wallets") + 1]
    : resolve(__dirname, "config", "wallets.json");

  // --networks <comma-separated> (default: base)
  let networks: Network[] = ["base"];
  if (args.includes("--networks")) {
    const raw = args[args.indexOf("--networks") + 1];
    if (raw) {
      networks = raw.split(",").map((n) => n.trim()) as Network[];
      // Validate networks
      for (const n of networks) {
        if (!SUPPORTED_NETWORKS.includes(n)) {
          console.error(
            `ERROR: Unsupported network "${n}". Supported: ${SUPPORTED_NETWORKS.join(", ")}`,
          );
          process.exit(1);
        }
      }
    }
  }
  // Legacy --network <single> support
  if (args.includes("--network") && !args.includes("--networks")) {
    const single = args[args.indexOf("--network") + 1];
    if (single) {
      if (!SUPPORTED_NETWORKS.includes(single as Network)) {
        console.error(
          `ERROR: Unsupported network "${single}". Supported: ${SUPPORTED_NETWORKS.join(", ")}`,
        );
        process.exit(1);
      }
      networks = [single as Network];
    }
  }

  // --agents <comma-separated indices>
  let agentIndices: number[] | null = null;
  if (args.includes("--agents")) {
    const raw = args[args.indexOf("--agents") + 1];
    if (raw) {
      agentIndices = raw.split(",").map((s) => parseInt(s.trim(), 10));
      for (const idx of agentIndices) {
        if (isNaN(idx) || idx < 0) {
          console.error(`ERROR: Invalid agent index "${idx}". Must be >= 0.`);
          process.exit(1);
        }
      }
    }
  }

  const dryRun = args.includes("--dry-run");
  const force = args.includes("--force");

  return { walletsFile, networks, agentIndices, dryRun, force };
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

function apiHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "User-Agent": "KarmaCadabra-Bulk-Register/1.0",
  };
  if (EM_API_KEY) {
    headers["X-API-Key"] = EM_API_KEY;
  }
  return headers;
}

/**
 * Step 1: Register as a worker (executor) in the EM platform.
 * POST /api/v1/executors/register
 */
async function registerWorker(
  address: string,
  displayName: string,
): Promise<WorkerRegistrationResult> {
  const url = `${EM_API_URL}/api/v1/executors/register`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({
        wallet_address: address,
        display_name: displayName,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        executor_id: data.executor?.id || data.id || null,
        created: data.created || false,
      };
    }

    // 409 = already exists (treat as success)
    if (response.status === 409) {
      const data = await response.json().catch(() => ({}));
      return {
        executor_id: data.executor?.id || data.id || null,
        created: false,
      };
    }

    const text = await response.text();
    return {
      executor_id: null,
      created: false,
      error: `HTTP ${response.status}: ${text.slice(0, 200)}`,
    };
  } catch (err: any) {
    return {
      executor_id: null,
      created: false,
      error: `Network error: ${err.message}`,
    };
  }
}

/**
 * Step 2: Register ERC-8004 on-chain identity via the EM API.
 * POST /api/v1/reputation/register
 *
 * The EM API proxies to the Facilitator (gasless registration).
 */
async function registerERC8004(
  address: string,
  agentName: string,
  network: string,
): Promise<ERC8004RegistrationResult> {
  const url = `${EM_API_URL}/api/v1/reputation/register`;
  const agentUri = `https://execution.market/agents/${address}`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({
        network,
        agent_uri: agentUri,
        recipient: address,
        metadata: [
          { key: "name", value: `KK Agent: ${agentName}` },
          {
            key: "description",
            value: `Karma Kadabra swarm agent — ${agentName} from Ultravioleta DAO community`,
          },
          { key: "swarm", value: "karma-kadabra-v2" },
          { key: "version", value: "1.0" },
        ],
      }),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        return {
          agent_id: data.agent_id || null,
          transaction: data.transaction || null,
          network: data.network || network,
        };
      }
      // API returned 200 but success=false (e.g., already registered)
      return {
        agent_id: data.agent_id || null,
        transaction: data.transaction || null,
        network: data.network || network,
        error: data.error || undefined,
      };
    }

    const text = await response.text();
    return {
      agent_id: null,
      transaction: null,
      network,
      error: `HTTP ${response.status}: ${text.slice(0, 200)}`,
    };
  } catch (err: any) {
    return {
      agent_id: null,
      transaction: null,
      network,
      error: `Network error: ${err.message}`,
    };
  }
}

// ---------------------------------------------------------------------------
// Persistence: identities.json
// ---------------------------------------------------------------------------

function loadIdentities(): IdentitiesFile {
  if (existsSync(IDENTITIES_FILE)) {
    try {
      return JSON.parse(readFileSync(IDENTITIES_FILE, "utf-8"));
    } catch {
      // Corrupted file, start fresh
    }
  }
  return {
    version: "1.0",
    updated_at: new Date().toISOString(),
    api_url: EM_API_URL,
    agents: [],
  };
}

function saveIdentities(data: IdentitiesFile): void {
  const configDir = resolve(__dirname, "config");
  if (!existsSync(configDir)) {
    mkdirSync(configDir, { recursive: true });
  }
  data.updated_at = new Date().toISOString();
  writeFileSync(IDENTITIES_FILE, JSON.stringify(data, null, 2));
}

function upsertAgentIdentity(
  identities: IdentitiesFile,
  wallet: WalletEntry,
  executorId: string | null,
  network: string,
  erc8004Result: {
    agent_id: number | null;
    transaction: string | null;
    status: "success" | "already_registered" | "failed";
    error?: string;
  },
): void {
  let agent = identities.agents.find(
    (a) => a.address.toLowerCase() === wallet.address.toLowerCase(),
  );

  if (!agent) {
    agent = {
      address: wallet.address,
      name: wallet.name,
      index: wallet.index,
      type: wallet.type,
      executor_id: executorId,
      registrations: {},
    };
    identities.agents.push(agent);
  }

  // Update executor_id if we got a new one
  if (executorId) {
    agent.executor_id = executorId;
  }

  // Update or add network registration
  agent.registrations[network] = {
    agent_id: erc8004Result.agent_id,
    transaction: erc8004Result.transaction,
    registered_at: new Date().toISOString(),
    status: erc8004Result.status,
    ...(erc8004Result.error ? { error: erc8004Result.error } : {}),
  };
}

// ---------------------------------------------------------------------------
// Sleep utility
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const { walletsFile, networks, agentIndices, dryRun, force } = parseArgs();

  // Load wallets
  let manifest: WalletManifest;
  try {
    manifest = JSON.parse(readFileSync(walletsFile, "utf-8"));
  } catch {
    console.error(
      `ERROR: Cannot read ${walletsFile}. Run generate-wallets.ts first.`,
    );
    process.exit(1);
  }

  // Filter agents if --agents specified
  let wallets = manifest.wallets;
  if (agentIndices) {
    wallets = wallets.filter((w) => agentIndices.includes(w.index));
    if (wallets.length === 0) {
      console.error(
        `ERROR: No wallets match indices [${agentIndices.join(",")}]. Available: 0-${manifest.count - 1}`,
      );
      process.exit(1);
    }
  }

  // Banner
  console.log(`\n${"=".repeat(65)}`);
  console.log(`  Karma Kadabra V2 — Bulk ERC-8004 Registration`);
  console.log(`  API:       ${EM_API_URL}`);
  console.log(`  Networks:  ${networks.join(", ")}`);
  console.log(
    `  Agents:    ${wallets.length} of ${manifest.count}${agentIndices ? ` (filtered: ${agentIndices.join(",")})` : ""}`,
  );
  console.log(`  Auth:      ${EM_API_KEY ? "API key set" : "no API key"}`);
  if (dryRun) console.log(`  MODE:      DRY RUN — no registrations will occur`);
  if (force)
    console.log(`  MODE:      FORCE — re-register even if already exists`);
  console.log(`${"=".repeat(65)}\n`);

  // Load existing identities for incremental updates
  const identities = loadIdentities();

  const summary: RegistrationSummary = {
    workers_registered: 0,
    workers_existing: 0,
    workers_failed: 0,
    erc8004_registered: 0,
    erc8004_existing: 0,
    erc8004_failed: 0,
  };

  // =========================================================================
  // Step 1: Register all agents as workers (only once, not per-network)
  // =========================================================================

  console.log(`--- Step 1: Worker Registration (${wallets.length} agents) ---\n`);

  const executorIds = new Map<string, string | null>();

  for (const wallet of wallets) {
    const { name, address, index } = wallet;
    const displayName = name.startsWith("kk-")
      ? `KK ${name.slice(3).replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}`
      : name;

    // Check if already registered in our identities file
    const existingAgent = identities.agents.find(
      (a) => a.address.toLowerCase() === address.toLowerCase(),
    );
    if (existingAgent?.executor_id && !force) {
      console.log(
        `  [${index}] ${name}: worker already registered (executor ${existingAgent.executor_id})`,
      );
      executorIds.set(address.toLowerCase(), existingAgent.executor_id);
      summary.workers_existing++;
      continue;
    }

    if (dryRun) {
      console.log(
        `  [${index}] ${name}: would register worker "${displayName}" (${address})`,
      );
      executorIds.set(address.toLowerCase(), null);
      summary.workers_registered++;
      continue;
    }

    console.log(
      `  [${index}] ${name}: registering worker "${displayName}"...`,
    );
    const result = await registerWorker(address, displayName);

    if (result.error) {
      console.error(`         FAILED: ${result.error}`);
      executorIds.set(address.toLowerCase(), null);
      summary.workers_failed++;
    } else if (result.created) {
      console.log(`         Created executor: ${result.executor_id}`);
      executorIds.set(address.toLowerCase(), result.executor_id);
      summary.workers_registered++;
    } else {
      console.log(
        `         Already exists: ${result.executor_id || "unknown"}`,
      );
      executorIds.set(address.toLowerCase(), result.executor_id);
      summary.workers_existing++;
    }

    await sleep(DELAY_MS);
  }

  // =========================================================================
  // Step 2: ERC-8004 registration on each network
  // =========================================================================

  for (const network of networks) {
    console.log(
      `\n--- Step 2: ERC-8004 Registration on ${network} (${wallets.length} agents) ---\n`,
    );

    for (const wallet of wallets) {
      const { name, address, index } = wallet;
      const executorId =
        executorIds.get(address.toLowerCase()) || null;

      // Check if already registered on this network
      const existingAgent = identities.agents.find(
        (a) => a.address.toLowerCase() === address.toLowerCase(),
      );
      const existingReg = existingAgent?.registrations?.[network];
      if (
        existingReg?.status === "success" &&
        existingReg?.agent_id &&
        !force
      ) {
        console.log(
          `  [${index}] ${name}: already registered on ${network} (Agent #${existingReg.agent_id})`,
        );
        summary.erc8004_existing++;
        continue;
      }

      if (dryRun) {
        console.log(
          `  [${index}] ${name}: would register ERC-8004 on ${network} (${address})`,
        );
        summary.erc8004_registered++;
        continue;
      }

      console.log(
        `  [${index}] ${name}: registering ERC-8004 on ${network}...`,
      );
      const result = await registerERC8004(address, name, network);

      if (result.error) {
        // Check if the error indicates "already registered"
        const errLower = (result.error || "").toLowerCase();
        if (
          errLower.includes("already") ||
          errLower.includes("exists") ||
          errLower.includes("duplicate")
        ) {
          console.log(
            `         Already registered on ${network}: ${result.error}`,
          );
          upsertAgentIdentity(identities, wallet, executorId, network, {
            agent_id: result.agent_id,
            transaction: result.transaction,
            status: "already_registered",
            error: result.error,
          });
          summary.erc8004_existing++;
        } else {
          console.error(`         FAILED: ${result.error}`);
          upsertAgentIdentity(identities, wallet, executorId, network, {
            agent_id: null,
            transaction: null,
            status: "failed",
            error: result.error,
          });
          summary.erc8004_failed++;
        }
      } else {
        console.log(
          `         Agent #${result.agent_id} on ${network} — TX: ${result.transaction || "N/A"}`,
        );
        upsertAgentIdentity(identities, wallet, executorId, network, {
          agent_id: result.agent_id,
          transaction: result.transaction,
          status: "success",
        });
        summary.erc8004_registered++;
      }

      // Save after each registration (incremental persistence)
      saveIdentities(identities);

      await sleep(DELAY_MS);
    }
  }

  // =========================================================================
  // Final save and summary
  // =========================================================================

  if (!dryRun) {
    saveIdentities(identities);
  }

  // Also save a timestamped report
  const reportFile = resolve(
    __dirname,
    `report-erc8004-registration-${networks.join("-")}-${Date.now()}.json`,
  );
  const report = {
    timestamp: new Date().toISOString(),
    networks,
    dryRun,
    force,
    api_url: EM_API_URL,
    agents_processed: wallets.length,
    summary,
    identities: identities.agents.filter((a) =>
      wallets.some(
        (w) => w.address.toLowerCase() === a.address.toLowerCase(),
      ),
    ),
  };
  writeFileSync(reportFile, JSON.stringify(report, null, 2));

  // Print summary
  console.log(`\n${"=".repeat(65)}`);
  console.log(`  Registration Complete`);
  console.log(`${"=".repeat(65)}`);
  console.log(`  Worker Registration:`);
  console.log(`    Registered: ${summary.workers_registered}`);
  console.log(`    Existing:   ${summary.workers_existing}`);
  console.log(`    Failed:     ${summary.workers_failed}`);
  console.log(`  ERC-8004 Identity:`);
  console.log(`    Registered: ${summary.erc8004_registered}`);
  console.log(`    Existing:   ${summary.erc8004_existing}`);
  console.log(`    Failed:     ${summary.erc8004_failed}`);
  console.log(`  Networks:     ${networks.join(", ")}`);
  console.log(`  Identities:   ${IDENTITIES_FILE}`);
  console.log(`  Report:       ${reportFile}`);
  console.log(`${"=".repeat(65)}\n`);

  // Exit with error code if any failures
  if (summary.workers_failed > 0 || summary.erc8004_failed > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`\nFATAL: ${err.message}`);
  process.exit(1);
});
