/**
 * Karma Kadabra V2 — Task 3.4: Relay Wallet Generation
 *
 * Generates relay wallet ADDRESSES for each of the 24 agents.
 * Relay wallets are used for autonomous reputation signing (giveFeedback()).
 *
 * Why relay wallets?
 *   - The main wallet owns the ERC-8004 agent NFT
 *   - Calling giveFeedback() from the NFT owner on itself causes a self-feedback revert
 *   - The relay wallet does NOT own any agent NFT, so it can call giveFeedback() freely
 *   - Relay wallets need ~0.001 ETH on Base for gas
 *
 * BIP-44 derivation:
 *   Main wallet:  m/44'/60'/0'/0/{index}       (index 0-23)
 *   Relay wallet: m/44'/60'/0'/0/{index + 100}  (index 100-123)
 *
 * Usage:
 *   AGENT_MNEMONIC="..." npx tsx scripts/kk/generate-relay-wallets.ts
 *   npx tsx scripts/kk/generate-relay-wallets.ts --wallets scripts/kk/config/wallets.json
 *
 * Security: Outputs ADDRESSES ONLY — never private keys.
 *           Private keys are derived at runtime by each agent from the shared seed.
 */

import { mnemonicToAccount } from "viem/accounts";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RELAY_INDEX_OFFSET = 100;
const DERIVATION_PATH = "m/44'/60'/0'/0/{index}";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WalletEntry {
  index: number;
  name: string;
  address: string;
  type: "system" | "user";
}

interface WalletManifest {
  version: string;
  generated: string;
  derivationPath: string;
  count: number;
  systemAgents: number;
  userAgents: number;
  wallets: WalletEntry[];
}

interface RelayWalletEntry {
  index: number;
  name: string;
  mainAddress: string;
  relayAddress: string;
  relayIndex: number;
  type: "system" | "user";
}

interface RelayWalletManifest {
  version: string;
  generated: string;
  derivationPathMain: string;
  derivationPathRelay: string;
  relayIndexOffset: number;
  count: number;
  wallets: RelayWalletEntry[];
}

interface AgentWalletEntry {
  index: number;
  name: string;
  address: string;
  personality: string;
  relay_address?: string;
  balances: Record<string, { usdc: string }>;
}

interface AgentWalletsJson {
  metadata: Record<string, unknown>;
  wallets: AgentWalletEntry[];
  funding: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Core Generation
// ---------------------------------------------------------------------------

function generateRelayWallets(
  mnemonic: string,
  wallets: WalletEntry[],
): RelayWalletManifest {
  const relayWallets: RelayWalletEntry[] = [];

  for (const wallet of wallets) {
    const relayIndex = wallet.index + RELAY_INDEX_OFFSET;
    const relayAccount = mnemonicToAccount(mnemonic, {
      addressIndex: relayIndex,
    });

    relayWallets.push({
      index: wallet.index,
      name: wallet.name,
      mainAddress: wallet.address,
      relayAddress: relayAccount.address,
      relayIndex,
      type: wallet.type,
    });
  }

  return {
    version: "1.0",
    generated: new Date().toISOString(),
    derivationPathMain: DERIVATION_PATH,
    derivationPathRelay: `m/44'/60'/0'/0/{index + ${RELAY_INDEX_OFFSET}}`,
    relayIndexOffset: RELAY_INDEX_OFFSET,
    count: relayWallets.length,
    wallets: relayWallets,
  };
}

// ---------------------------------------------------------------------------
// Update terraform/swarm/config/agent-wallets.json
// ---------------------------------------------------------------------------

function updateAgentWalletsJson(
  relayManifest: RelayWalletManifest,
  agentWalletsPath: string,
): boolean {
  if (!existsSync(agentWalletsPath)) {
    console.warn(
      `  WARNING: ${agentWalletsPath} not found, skipping agent-wallets.json update`,
    );
    return false;
  }

  const agentWallets: AgentWalletsJson = JSON.parse(
    readFileSync(agentWalletsPath, "utf-8"),
  );

  // Build relay address lookup by main address (case-insensitive)
  const relayByMainAddress = new Map<string, string>();
  for (const relay of relayManifest.wallets) {
    relayByMainAddress.set(
      relay.mainAddress.toLowerCase(),
      relay.relayAddress,
    );
  }

  let updated = 0;
  for (const wallet of agentWallets.wallets) {
    const relayAddr = relayByMainAddress.get(wallet.address.toLowerCase());
    if (relayAddr) {
      wallet.relay_address = relayAddr;
      updated++;
    }
  }

  writeFileSync(agentWalletsPath, JSON.stringify(agentWallets, null, 2) + "\n");
  console.log(
    `  Updated ${updated}/${agentWallets.wallets.length} entries in ${agentWalletsPath}`,
  );
  return true;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);

  // Parse --wallets flag for input wallet manifest
  const walletsIdx = args.indexOf("--wallets");
  const walletsFile =
    walletsIdx >= 0
      ? args[walletsIdx + 1]
      : resolve(__dirname, "config", "wallets.json");

  // Parse --output flag for relay manifest output
  const outputIdx = args.indexOf("--output");
  const outputFile =
    outputIdx >= 0
      ? args[outputIdx + 1]
      : resolve(__dirname, "config", "relay-wallets.json");

  // Agent-wallets.json in terraform/swarm/config
  const agentWalletsPath = resolve(
    __dirname,
    "../../terraform/swarm/config/agent-wallets.json",
  );

  // Get mnemonic
  const mnemonic = process.env.AGENT_MNEMONIC || process.env.KK_MNEMONIC;
  if (!mnemonic) {
    console.error("ERROR: AGENT_MNEMONIC or KK_MNEMONIC not set.");
    console.error(
      "Set it via environment variable or fetch from AWS Secrets Manager (kk/swarm-seed).",
    );
    process.exit(1);
  }

  // Load existing wallet manifest
  if (!existsSync(walletsFile)) {
    console.error(`ERROR: Wallet manifest not found: ${walletsFile}`);
    console.error("Run 'npx tsx scripts/kk/generate-wallets.ts' first.");
    process.exit(1);
  }

  const manifest: WalletManifest = JSON.parse(
    readFileSync(walletsFile, "utf-8"),
  );
  console.log(`\nLoaded ${manifest.count} wallets from ${walletsFile}`);
  console.log(`Relay index offset: +${RELAY_INDEX_OFFSET}`);
  console.log(
    `Main path:  m/44'/60'/0'/0/{0..${manifest.count - 1}}`,
  );
  console.log(
    `Relay path: m/44'/60'/0'/0/{${RELAY_INDEX_OFFSET}..${manifest.count - 1 + RELAY_INDEX_OFFSET}}\n`,
  );

  // Generate relay wallets
  const relayManifest = generateRelayWallets(mnemonic, manifest.wallets);

  // Ensure output directory exists
  const outputDir = dirname(outputFile);
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // Write relay wallet manifest
  writeFileSync(outputFile, JSON.stringify(relayManifest, null, 2) + "\n");
  console.log(`Relay wallet manifest written to: ${outputFile}`);

  // Update terraform/swarm/config/agent-wallets.json if it exists
  updateAgentWalletsJson(relayManifest, agentWalletsPath);

  // Print summary table
  console.log("\n" + "=".repeat(100));
  console.log("KarmaCadabra V2 — Relay Wallet Summary");
  console.log("=".repeat(100));
  console.log(
    `${"Type".padEnd(6)} | ${"Name".padEnd(24)} | ${"Main Address".padEnd(44)} | Relay Address`,
  );
  console.log("-".repeat(100));

  for (const relay of relayManifest.wallets) {
    const tag = relay.type === "system" ? "[SYS]" : "[USR]";
    console.log(
      `${tag.padEnd(6)} | ${relay.name.padEnd(24)} | ${relay.mainAddress.padEnd(44)} | ${relay.relayAddress}`,
    );
  }

  console.log("-".repeat(100));
  console.log(`Total: ${relayManifest.count} relay wallets generated`);
  console.log(
    `\nNOTE: Relay wallets need ~0.001 ETH on Base for gas to call giveFeedback().`,
  );
  console.log(
    `      Private keys are NOT stored — agents derive them at runtime from the HD seed.`,
  );
}

main();
