/**
 * Karma Kadabra V2 — Task 12.3: Multi-Token Balance Checker
 *
 * Shows a matrix of all agent wallets across all chains with ALL stablecoin balances.
 * Uses multicall for efficient batch reads (1 RPC call per chain).
 *
 * Usage:
 *   npx tsx check-balances.ts --config config/wallets.json
 *   npx tsx check-balances.ts --config config/wallets.json --chain base
 *   npx tsx check-balances.ts --config config/wallets.json --token USDC
 *   npx tsx check-balances.ts --config config/wallets.json --json
 */

import {
  createPublicClient,
  http,
  formatUnits,
  formatEther,
  getAddress,
  type Address,
} from "viem";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import {
  CHAINS,
  ERC20_ABI,
  getChainNames,
  getTokenSymbols,
  getAllTokenSymbols,
  type TokenInfo,
} from "./lib/chains.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BalanceRow {
  name: string;
  address: string;
  chain: string;
  /** Token symbol -> formatted balance */
  tokens: Record<string, string>;
  native: string;
  funded: boolean;
}

// ---------------------------------------------------------------------------
// Balance Check
// ---------------------------------------------------------------------------

async function checkChain(
  chainName: string,
  wallets: Array<{ name: string; address: Address }>,
  tokenFilter: string | null,
): Promise<BalanceRow[]> {
  const chainInfo = CHAINS[chainName];
  if (!chainInfo) throw new Error(`Unknown chain: ${chainName}`);

  // Determine which tokens to query on this chain
  const chainTokenSymbols = getTokenSymbols(chainName);
  const symbols = tokenFilter
    ? chainTokenSymbols.filter((s) => s === tokenFilter)
    : chainTokenSymbols;

  // If token filter doesn't match any token on this chain, skip token reads
  const tokenInfos: TokenInfo[] = symbols.map(
    (s) => chainInfo.tokens[s],
  );

  const client = createPublicClient({
    chain: chainInfo.chain,
    transport: http(chainInfo.rpcUrl),
    batch: { multicall: true },
  });

  // Build all token balance reads + native balance reads
  const tokenReadPromises = tokenInfos.map((token) =>
    Promise.all(
      wallets.map((w) =>
        client.readContract({
          address: token.address,
          abi: ERC20_ABI,
          functionName: "balanceOf",
          args: [w.address],
        }),
      ),
    ),
  );

  const nativeReadPromise = Promise.all(
    wallets.map((w) => client.getBalance({ address: w.address })),
  );

  // Execute all reads in parallel (single multicall batch per chain)
  const [tokenResults, nativeBalances] = await Promise.all([
    Promise.all(tokenReadPromises),
    nativeReadPromise,
  ]);

  return wallets.map((w, walletIdx) => {
    const tokenBalances: Record<string, string> = {};
    let hasAnyToken = false;

    for (let tokenIdx = 0; tokenIdx < tokenInfos.length; tokenIdx++) {
      const token = tokenInfos[tokenIdx];
      const raw = tokenResults[tokenIdx][walletIdx];
      tokenBalances[token.symbol] = formatUnits(raw, token.decimals);
      if (raw > 0n) hasAnyToken = true;
    }

    const nativeRaw = nativeBalances[walletIdx];

    return {
      name: w.name,
      address: w.address,
      chain: chainName,
      tokens: tokenBalances,
      native: formatEther(nativeRaw),
      funded: hasAnyToken || nativeRaw > 0n,
    };
  });
}

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------

function displayTable(rows: BalanceRow[], chainName: string): void {
  const chainInfo = CHAINS[chainName];
  if (rows.length === 0) return;

  // Collect token symbols present in these rows
  const tokenSymbols = Object.keys(rows[0].tokens);
  const tokensLabel = tokenSymbols.length > 0 ? tokenSymbols.join(", ") : "none";

  console.log(`\n${"=".repeat(80)}`);
  console.log(
    `  ${chainInfo.name} (${chainInfo.chainId}) — ${chainInfo.nativeSymbol} — Tokens: ${tokensLabel}`,
  );
  console.log(`${"=".repeat(80)}`);

  const funded = rows.filter((r) => r.funded).length;
  const unfunded = rows.length - funded;

  // Column widths
  const nameWidth = 25;
  const tokenColWidth = 10;
  const nativeColWidth = 15;

  // Header
  const tokenHeaders = tokenSymbols.map((s) => s.padStart(tokenColWidth)).join(" ");
  const headerLine =
    `  ${"Name".padEnd(nameWidth)} ${tokenHeaders} ${"Native".padStart(nativeColWidth)} Status`;
  console.log(headerLine);

  const separatorLen = nameWidth + tokenSymbols.length * (tokenColWidth + 1) + nativeColWidth + 10;
  console.log(`  ${"─".repeat(separatorLen)}`);

  for (const r of rows) {
    const status = r.funded ? "[OK]" : "[--]";
    const tokenCols = tokenSymbols
      .map((s) => (r.tokens[s] ?? "—").padStart(tokenColWidth))
      .join(" ");
    const nativeStr = `${parseFloat(r.native).toFixed(4)} ${chainInfo.nativeSymbol}`;
    console.log(
      `  ${r.name.padEnd(nameWidth)} ${tokenCols} ${nativeStr.padStart(nativeColWidth)} ${status}`,
    );
  }

  console.log(`\n  Summary: ${funded} funded, ${unfunded} unfunded`);
}

// ---------------------------------------------------------------------------
// JSON Output
// ---------------------------------------------------------------------------

interface JsonWalletOutput {
  name: string;
  address: string;
  chains: Record<string, Record<string, string>>;
}

function buildJsonOutput(allRows: BalanceRow[]): { wallets: JsonWalletOutput[] } {
  const walletMap = new Map<string, JsonWalletOutput>();

  for (const row of allRows) {
    let entry = walletMap.get(row.address);
    if (!entry) {
      entry = { name: row.name, address: row.address, chains: {} };
      walletMap.set(row.address, entry);
    }
    const chainBalances: Record<string, string> = { native: row.native };
    for (const [symbol, balance] of Object.entries(row.tokens)) {
      chainBalances[symbol] = balance;
    }
    entry.chains[row.chain] = chainBalances;
  }

  return { wallets: Array.from(walletMap.values()) };
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

function displaySummary(allRows: BalanceRow[]): void {
  const totalFunded = allRows.filter((r) => r.funded).length;
  const totalSlots = allRows.length;

  // Aggregate per-token totals
  const tokenTotals = new Map<string, number>();
  for (const row of allRows) {
    for (const [symbol, balance] of Object.entries(row.tokens)) {
      const prev = tokenTotals.get(symbol) ?? 0;
      tokenTotals.set(symbol, prev + parseFloat(balance));
    }
  }

  console.log(`\n${"=".repeat(80)}`);
  console.log(`  TOTAL: ${totalFunded}/${totalSlots} wallet-chain slots funded`);

  if (tokenTotals.size > 0) {
    console.log("");
    console.log("  Token Totals (across all wallets and chains):");
    for (const [symbol, total] of Array.from(tokenTotals.entries()).sort()) {
      console.log(`    ${symbol.padEnd(8)} ${total.toFixed(6)}`);
    }
  }

  console.log(`${"=".repeat(80)}\n`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);

  const configIdx = args.indexOf("--config");
  const configFile =
    configIdx >= 0
      ? args[configIdx + 1]
      : resolve(__dirname, "config", "wallets.json");

  const chainFilter = args.includes("--chain")
    ? args[args.indexOf("--chain") + 1]
    : null;

  const tokenFilter = args.includes("--token")
    ? args[args.indexOf("--token") + 1]
    : null;

  const jsonOutput = args.includes("--json");

  // Validate token filter
  if (tokenFilter) {
    const allSymbols = getAllTokenSymbols();
    if (!allSymbols.includes(tokenFilter)) {
      console.error(
        `ERROR: Unknown token "${tokenFilter}". Valid tokens: ${allSymbols.join(", ")}`,
      );
      process.exit(1);
    }
  }

  // Load wallet manifest
  let manifest: WalletManifest;
  try {
    manifest = JSON.parse(readFileSync(configFile, "utf-8"));
  } catch {
    console.error(`ERROR: Cannot read wallet manifest at ${configFile}`);
    console.error("Run generate-wallets.ts first.");
    process.exit(1);
  }

  const wallets = manifest.wallets.map((w) => ({
    name: w.name,
    address: getAddress(w.address) as Address,
  }));

  const filterDesc = [
    chainFilter || "all chains",
    tokenFilter ? `token=${tokenFilter}` : "all tokens",
  ].join(", ");

  console.log(
    `\nChecking ${wallets.length} wallets across ${filterDesc}...\n`,
  );

  const chains = chainFilter ? [chainFilter] : getChainNames();
  const allRows: BalanceRow[] = [];

  for (const chainName of chains) {
    // Skip chain if token filter specified and chain doesn't have that token
    if (tokenFilter) {
      const chainTokens = getTokenSymbols(chainName);
      if (!chainTokens.includes(tokenFilter)) {
        continue;
      }
    }

    try {
      const rows = await checkChain(chainName, wallets, tokenFilter);
      allRows.push(...rows);

      if (!jsonOutput) {
        displayTable(rows, chainName);
      }
    } catch (err: any) {
      console.error(`  ERROR on ${chainName}: ${err.message}`);
    }
  }

  if (jsonOutput) {
    console.log(JSON.stringify(buildJsonOutput(allRows), null, 2));
  }

  // Summary
  if (!jsonOutput) {
    displaySummary(allRows);
  }
}

main().catch(console.error);
