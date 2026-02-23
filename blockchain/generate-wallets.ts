/**
 * Karma Kadabra V2 — Task 1.1: HD Wallet Generation
 *
 * Generates N deterministic wallets from a BIP-44 mnemonic.
 * Path: m/44'/60'/0'/0/{index}
 *   - Index 0-4: System agents (coordinator, karma-hello, skill-extractor, voice-extractor, validator)
 *   - Index 5+:  User agents (from Twitch chat top-N)
 *
 * Usage:
 *   npx tsx generate-wallets.ts --count 55
 *   npx tsx generate-wallets.ts --count 34 --output wallets-34.json
 *   AGENT_MNEMONIC="word1 word2 ..." npx tsx generate-wallets.ts --count 55
 *
 * Security: Mnemonic should be in AWS Secrets Manager (kk/swarm-seed).
 *           This script outputs ADDRESSES ONLY — never private keys.
 */

import { mnemonicToAccount } from "viem/accounts";
import { writeFileSync, readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// System Agent Names (indices 0-4)
// ---------------------------------------------------------------------------

const SYSTEM_AGENTS = [
  "kk-coordinator",
  "kk-karma-hello",
  "kk-skill-extractor",
  "kk-voice-extractor",
  "kk-validator",
  "kk-soul-extractor",
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WalletEntry {
  index: number;
  name: string;
  address: string;
  type: "system" | "user";
}

export interface WalletManifest {
  version: string;
  generated: string;
  derivationPath: string;
  count: number;
  systemAgents: number;
  userAgents: number;
  wallets: WalletEntry[];
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

function generateWallets(
  mnemonic: string,
  count: number,
  userNames?: string[],
): WalletManifest {
  const wallets: WalletEntry[] = [];

  for (let i = 0; i < count; i++) {
    const account = mnemonicToAccount(mnemonic, { addressIndex: i });

    let name: string;
    let type: "system" | "user";

    if (i < SYSTEM_AGENTS.length) {
      name = SYSTEM_AGENTS[i];
      type = "system";
    } else {
      const userIndex = i - SYSTEM_AGENTS.length;
      name = userNames && userNames[userIndex]
        ? `kk-${userNames[userIndex]}`
        : `kk-agent-${String(i).padStart(3, "0")}`;
      type = "user";
    }

    wallets.push({
      index: i,
      name,
      address: account.address,
      type,
    });
  }

  return {
    version: "1.0",
    generated: new Date().toISOString(),
    derivationPath: "m/44'/60'/0'/0/{index}",
    count,
    systemAgents: Math.min(count, SYSTEM_AGENTS.length),
    userAgents: Math.max(0, count - SYSTEM_AGENTS.length),
    wallets,
  };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);

  const countIdx = args.indexOf("--count");
  const count = countIdx >= 0 ? parseInt(args[countIdx + 1]) : 55;

  const outputIdx = args.indexOf("--output");
  const outputFile = outputIdx >= 0
    ? args[outputIdx + 1]
    : resolve(__dirname, "config", "wallets.json");

  const statsIdx = args.indexOf("--stats");
  const statsFile = statsIdx >= 0
    ? args[statsIdx + 1]
    : resolve(__dirname, "data", "user-stats.json");

  const mnemonic = process.env.AGENT_MNEMONIC;
  if (!mnemonic) {
    console.error("ERROR: AGENT_MNEMONIC not set.");
    console.error("Set it via environment variable or AWS Secrets Manager (kk/swarm-seed).");
    console.error("");
    console.error("To generate a new mnemonic:");
    console.error('  node -e "console.log(require(\'@scure/bip39\').generateMnemonic(require(\'@scure/bip39/wordlists/english\').wordlist))"');
    process.exit(1);
  }

  // Load user names from stats file if available
  let userNames: string[] | undefined;
  if (existsSync(statsFile)) {
    try {
      const stats = JSON.parse(readFileSync(statsFile, "utf-8"));
      userNames = stats.ranking.map((u: { username: string }) => u.username);
      console.log(`Loaded ${userNames!.length} user names from ${statsFile}`);
    } catch (e) {
      console.warn(`Warning: Could not parse stats file: ${statsFile}`);
    }
  }

  if (count < 1 || count > 200) {
    console.error(`ERROR: Count must be 1-200, got ${count}`);
    process.exit(1);
  }

  console.log(`\nGenerating ${count} HD wallets...`);
  console.log(`Path: m/44'/60'/0'/0/{0..${count - 1}}\n`);

  const manifest = generateWallets(mnemonic, count, userNames);

  writeFileSync(outputFile, JSON.stringify(manifest, null, 2));
  console.log(`Manifest written to: ${outputFile}`);
  console.log(`  System agents: ${manifest.systemAgents}`);
  console.log(`  User agents:   ${manifest.userAgents}`);
  console.log("");

  // Print first 10
  const preview = manifest.wallets.slice(0, 10);
  for (const w of preview) {
    const tag = w.type === "system" ? "[SYS]" : "[USR]";
    console.log(`  ${tag} [${w.index}] ${w.name}: ${w.address}`);
  }
  if (count > 10) {
    console.log(`  ... and ${count - 10} more`);
  }
}

main();
