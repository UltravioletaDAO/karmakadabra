/**
 * Karma Kadabra V2 -- Sweep Funds: Recover ALL tokens from agent wallets
 *
 * Iterates every HD-derived agent wallet across all chains, reads balances
 * of every stablecoin + native gas token, and sends non-zero balances to
 * a target recovery wallet.
 *
 * The HD mnemonic is fetched from AWS Secrets Manager (kk/swarm-seed)
 * so private keys are never stored on disk.
 *
 * Usage:
 *   npx tsx kk/sweep-funds.ts --target 0xD386... --dry-run
 *   npx tsx kk/sweep-funds.ts --target 0xD386... --count 40
 *   npx tsx kk/sweep-funds.ts --target 0xD386... --chains base,polygon
 *   npx tsx kk/sweep-funds.ts --target 0xD386... --tokens-only
 */

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
import { mnemonicToAccount, privateKeyToAccount } from "viem/accounts";
import { execSync } from "child_process";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import {
  CHAINS,
  ERC20_ABI,
  getChainNames,
  getChain,
  type ChainInfo,
  type TokenInfo,
} from "./lib/chains.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SweepResult {
  wallet: string;
  walletAddress: string;
  chain: string;
  asset: string; // token symbol or "native"
  balance: string;
  tx: string | null;
  status: "sent" | "skip" | "dust" | "error" | "dry-run";
  error?: string;
}

interface WalletInfo {
  index: number;
  name: string;
  address: Address;
  privateKey: Hex;
}

// ---------------------------------------------------------------------------
// Load mnemonic from AWS Secrets Manager
// ---------------------------------------------------------------------------

function loadMnemonic(): string {
  // Allow override via env var (for testing)
  if (process.env.AGENT_MNEMONIC) {
    console.log("  Using AGENT_MNEMONIC from environment\n");
    return process.env.AGENT_MNEMONIC;
  }

  console.log("  Fetching mnemonic from AWS Secrets Manager (kk/swarm-seed)...");
  try {
    const raw = execSync(
      "aws secretsmanager get-secret-value --secret-id kk/swarm-seed --query SecretString --output text --region us-east-2",
      { encoding: "utf-8", timeout: 15_000 },
    ).trim();

    const secret = JSON.parse(raw);
    if (!secret.mnemonic) {
      throw new Error("Secret JSON missing 'mnemonic' key");
    }
    console.log("  Mnemonic loaded successfully.\n");
    return secret.mnemonic;
  } catch (err: any) {
    console.error("ERROR: Failed to load mnemonic from AWS Secrets Manager.");
    console.error(err.message);
    console.error("\nAlternative: set AGENT_MNEMONIC env var.");
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Derive wallets from mnemonic
// ---------------------------------------------------------------------------

function deriveWallets(mnemonic: string, count: number): WalletInfo[] {
  // Load wallet manifest for names (optional)
  let nameMap: Record<number, string> = {};
  try {
    const manifestPath = resolve(__dirname, "config", "wallets.json");
    const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
    for (const w of manifest.wallets) {
      nameMap[w.index] = w.name;
    }
  } catch {
    // Manifest not available — use index-based names
  }

  const wallets: WalletInfo[] = [];
  for (let i = 0; i < count; i++) {
    const account = mnemonicToAccount(mnemonic, { addressIndex: i });
    // viem's mnemonicToAccount doesn't expose the raw private key directly,
    // but we can use the account for signing. However, to create a WalletClient
    // we need the account object. We'll store the account reference differently.
    // Actually, mnemonicToAccount returns a LocalAccount which IS a signer.
    wallets.push({
      index: i,
      name: nameMap[i] || `kk-agent-${String(i).padStart(3, "0")}`,
      address: account.address,
      // We use a placeholder — the actual signing is done via the account object
      privateKey: "0x" as Hex,
    });
  }

  return wallets;
}

// ---------------------------------------------------------------------------
// Sweep a single wallet on a single chain
// ---------------------------------------------------------------------------

async function sweepWalletOnChain(
  mnemonic: string,
  wallet: WalletInfo,
  chainName: string,
  chainInfo: ChainInfo,
  targetAddress: Address,
  dryRun: boolean,
  tokensOnly: boolean,
): Promise<SweepResult[]> {
  const results: SweepResult[] = [];
  const account = mnemonicToAccount(mnemonic, { addressIndex: wallet.index });

  const publicClient = createPublicClient({
    chain: chainInfo.chain,
    transport: http(chainInfo.rpcUrl),
    batch: { multicall: true },
  });

  const walletClient = createWalletClient({
    account,
    chain: chainInfo.chain,
    transport: http(chainInfo.rpcUrl),
  });

  // --- Sweep ERC-20 tokens ---
  const tokens = Object.values(chainInfo.tokens);

  for (const token of tokens) {
    try {
      const balance = await publicClient.readContract({
        address: token.address,
        abi: ERC20_ABI,
        functionName: "balanceOf",
        args: [wallet.address],
      }) as bigint;

      const formatted = formatUnits(balance, token.decimals);

      if (balance === 0n) {
        results.push({
          wallet: wallet.name,
          walletAddress: wallet.address,
          chain: chainName,
          asset: token.symbol,
          balance: formatted,
          tx: null,
          status: "skip",
        });
        continue;
      }

      if (dryRun) {
        results.push({
          wallet: wallet.name,
          walletAddress: wallet.address,
          chain: chainName,
          asset: token.symbol,
          balance: formatted,
          tx: null,
          status: "dry-run",
        });
        continue;
      }

      // Send full balance to target
      const txHash = await walletClient.writeContract({
        address: token.address,
        abi: ERC20_ABI,
        functionName: "transfer",
        args: [targetAddress, balance],
      });

      // Wait for confirmation
      await publicClient.waitForTransactionReceipt({
        hash: txHash,
        timeout: 60_000,
      });

      results.push({
        wallet: wallet.name,
        walletAddress: wallet.address,
        chain: chainName,
        asset: token.symbol,
        balance: formatted,
        tx: txHash,
        status: "sent",
      });
    } catch (err: any) {
      results.push({
        wallet: wallet.name,
        walletAddress: wallet.address,
        chain: chainName,
        asset: token.symbol,
        balance: "?",
        tx: null,
        status: "error",
        error: err.message?.slice(0, 120),
      });
    }
  }

  // --- Sweep native gas token ---
  if (!tokensOnly) {
    try {
      const nativeBalance = await publicClient.getBalance({
        address: wallet.address,
      });

      const formatted = formatEther(nativeBalance);

      if (nativeBalance === 0n) {
        results.push({
          wallet: wallet.name,
          walletAddress: wallet.address,
          chain: chainName,
          asset: chainInfo.nativeSymbol,
          balance: formatted,
          tx: null,
          status: "skip",
        });
      } else {
        // Estimate gas cost for a simple ETH transfer
        const gasPrice = await publicClient.getGasPrice();
        const gasLimit = 21000n;
        const gasCost = gasPrice * gasLimit;

        if (nativeBalance <= gasCost) {
          results.push({
            wallet: wallet.name,
            walletAddress: wallet.address,
            chain: chainName,
            asset: chainInfo.nativeSymbol,
            balance: formatted,
            tx: null,
            status: "dust",
          });
        } else if (dryRun) {
          results.push({
            wallet: wallet.name,
            walletAddress: wallet.address,
            chain: chainName,
            asset: chainInfo.nativeSymbol,
            balance: formatted,
            tx: null,
            status: "dry-run",
          });
        } else {
          const sendAmount = nativeBalance - gasCost;
          const txHash = await walletClient.sendTransaction({
            to: targetAddress,
            value: sendAmount,
            gas: gasLimit,
          });

          await publicClient.waitForTransactionReceipt({
            hash: txHash,
            timeout: 60_000,
          });

          results.push({
            wallet: wallet.name,
            walletAddress: wallet.address,
            chain: chainName,
            asset: chainInfo.nativeSymbol,
            balance: formatted,
            tx: txHash,
            status: "sent",
          });
        }
      }
    } catch (err: any) {
      results.push({
        wallet: wallet.name,
        walletAddress: wallet.address,
        chain: chainName,
        asset: chainInfo.nativeSymbol,
        balance: "?",
        tx: null,
        status: "error",
        error: err.message?.slice(0, 120),
      });
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

function statusIcon(status: string): string {
  switch (status) {
    case "sent":
      return "[OK] sent";
    case "skip":
      return "skip (0)";
    case "dust":
      return "skip (dust < gas)";
    case "dry-run":
      return "[DRY-RUN] would send";
    case "error":
      return "[ERR]";
    default:
      return status;
  }
}

function printWalletResults(results: SweepResult[]): void {
  for (const r of results) {
    const txPart = r.tx ? ` (tx: ${r.tx.slice(0, 10)}...)` : "";
    const errPart = r.error ? ` -- ${r.error}` : "";
    const balanceStr =
      r.asset === "native" ? r.balance : `$${parseFloat(r.balance).toFixed(2)}`;

    if (r.status === "skip") {
      // Print zero balances inline
      console.log(
        `    [${r.chain}] ${r.asset}: $0.00 -> skip`,
      );
    } else {
      console.log(
        `    [${r.chain}] ${r.asset}: ${balanceStr} -> ${statusIcon(r.status)}${txPart}${errPart}`,
      );
    }
  }
}

function printSummary(allResults: SweepResult[]): void {
  console.log(`\n${"=".repeat(70)}`);
  console.log("  SWEEP SUMMARY");
  console.log(`${"=".repeat(70)}`);

  // Aggregate per-asset totals for sent + dry-run
  const tokenTotals = new Map<string, number>();
  const nativeTotals = new Map<string, number>();
  let failCount = 0;
  let dustCount = 0;
  let sentCount = 0;

  for (const r of allResults) {
    if (r.status === "error") {
      failCount++;
      continue;
    }
    if (r.status === "dust") {
      dustCount++;
      continue;
    }
    if (r.status === "skip") continue;

    // "sent" or "dry-run"
    const bal = parseFloat(r.balance);
    if (bal <= 0) continue;

    // Determine if it's a native or token asset
    // We check against known native symbols
    const knownNativeSymbols = new Set(
      Object.values(CHAINS).map((c) => c.nativeSymbol),
    );

    if (knownNativeSymbols.has(r.asset)) {
      const prev = nativeTotals.get(r.asset) ?? 0;
      nativeTotals.set(r.asset, prev + bal);
    } else {
      const prev = tokenTotals.get(r.asset) ?? 0;
      tokenTotals.set(r.asset, prev + bal);
    }

    if (r.status === "sent") sentCount++;
  }

  // Print stablecoin totals
  if (tokenTotals.size > 0) {
    for (const [symbol, total] of Array.from(tokenTotals.entries()).sort()) {
      console.log(
        `  ${symbol} recovered: $${total.toFixed(6)} across chains`,
      );
    }
  } else {
    console.log("  No stablecoins recovered.");
  }

  // Print native totals
  if (nativeTotals.size > 0) {
    for (const [symbol, total] of Array.from(nativeTotals.entries()).sort()) {
      console.log(`  ${symbol} recovered: ${total.toFixed(6)}`);
    }
  }

  console.log("");
  console.log(`  Sent: ${sentCount}`);
  console.log(`  Failed: ${failCount}`);
  console.log(`  Dust skipped: ${dustCount} (balance < gas cost)`);
  console.log(`${"=".repeat(70)}\n`);
}

// ---------------------------------------------------------------------------
// CLI Argument Parsing
// ---------------------------------------------------------------------------

function parseArgs(): {
  target: Address;
  count: number;
  chains: string[] | null;
  dryRun: boolean;
  tokensOnly: boolean;
} {
  const args = process.argv.slice(2);

  // --target (required)
  const targetIdx = args.indexOf("--target");
  if (targetIdx < 0 || !args[targetIdx + 1]) {
    console.error("ERROR: --target 0xADDRESS is required.");
    console.error("");
    console.error("Usage:");
    console.error("  npx tsx kk/sweep-funds.ts --target 0xD386... --dry-run");
    console.error("  npx tsx kk/sweep-funds.ts --target 0xD386... --count 40");
    console.error(
      "  npx tsx kk/sweep-funds.ts --target 0xD386... --chains base,polygon",
    );
    console.error("  npx tsx kk/sweep-funds.ts --target 0xD386... --tokens-only");
    process.exit(1);
  }
  const target = getAddress(args[targetIdx + 1]) as Address;

  // --count (default 24)
  const countIdx = args.indexOf("--count");
  const count = countIdx >= 0 ? parseInt(args[countIdx + 1]) : 24;
  if (isNaN(count) || count < 1 || count > 200) {
    console.error(`ERROR: --count must be 1-200, got ${args[countIdx + 1]}`);
    process.exit(1);
  }

  // --chains (optional, comma-separated)
  const chainsIdx = args.indexOf("--chains");
  let chains: string[] | null = null;
  if (chainsIdx >= 0 && args[chainsIdx + 1]) {
    chains = args[chainsIdx + 1].split(",").map((c) => c.trim());
    for (const c of chains) {
      if (!CHAINS[c]) {
        console.error(
          `ERROR: Unknown chain "${c}". Valid: ${getChainNames().join(", ")}`,
        );
        process.exit(1);
      }
    }
  }

  // --dry-run
  const dryRun = args.includes("--dry-run");

  // --tokens-only
  const tokensOnly = args.includes("--tokens-only");

  return { target, count, chains, dryRun, tokensOnly };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const { target, count, chains: chainFilter, dryRun, tokensOnly } = parseArgs();

  const chainNames = chainFilter || getChainNames();
  const modeTag = dryRun ? " [DRY-RUN]" : "";
  const tokensTag = tokensOnly ? " (tokens only, skipping native)" : "";

  console.log(`\n${"=".repeat(70)}`);
  console.log(
    `  Sweeping ${count} wallets across ${chainNames.length} chains -> ${target}${modeTag}${tokensTag}`,
  );
  console.log(`${"=".repeat(70)}\n`);

  // 1. Load mnemonic
  const mnemonic = loadMnemonic();

  // 2. Derive wallets
  const wallets = deriveWallets(mnemonic, count);

  console.log(`  Derived ${wallets.length} wallets from HD seed.\n`);

  // 3. Sweep each wallet across each chain
  const allResults: SweepResult[] = [];

  for (let wIdx = 0; wIdx < wallets.length; wIdx++) {
    const wallet = wallets[wIdx];
    console.log(
      `  Wallet ${wIdx}/${wallets.length}: ${wallet.address} (${wallet.name})`,
    );

    for (const chainName of chainNames) {
      const chainInfo = CHAINS[chainName];
      if (!chainInfo) continue;

      try {
        const results = await sweepWalletOnChain(
          mnemonic,
          wallet,
          chainName,
          chainInfo,
          target,
          dryRun,
          tokensOnly,
        );

        allResults.push(...results);

        // Only print non-skip results inline for cleaner output
        const nonSkip = results.filter((r) => r.status !== "skip");
        if (nonSkip.length > 0) {
          printWalletResults(nonSkip);
        }
      } catch (err: any) {
        console.error(`    [${chainName}] FATAL: ${err.message}`);
        allResults.push({
          wallet: wallet.name,
          walletAddress: wallet.address,
          chain: chainName,
          asset: "all",
          balance: "?",
          tx: null,
          status: "error",
          error: err.message?.slice(0, 120),
        });
      }
    }
    console.log(""); // blank line between wallets
  }

  // 4. Summary
  printSummary(allResults);
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
