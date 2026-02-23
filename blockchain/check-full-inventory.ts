/**
 * KK V2 — Full Multi-Token Inventory
 *
 * Checks ALL stablecoin balances + native gas on ALL 8 chains.
 * Never displays private keys.
 *
 * Usage: npx tsx kk/check-full-inventory.ts
 */
import { createPublicClient, http, formatUnits, formatEther, type Address } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { CHAINS, type TokenInfo } from "./lib/chains.js";
import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

async function main() {
  const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as `0x${string}`;
  if (!pk) { console.error("WALLET_PRIVATE_KEY or PRIVATE_KEY not set"); process.exit(1); }
  const account = privateKeyToAccount(pk);

  // SECURITY: Only show public address, never the key
  console.log("Wallet: " + account.address);
  console.log("=".repeat(90));

  const ERC20_ABI = [
    { name: "balanceOf", type: "function", stateMutability: "view",
      inputs: [{ name: "account", type: "address" }],
      outputs: [{ name: "", type: "uint256" }] },
  ] as const;

  // Collect all results for summary
  const results: Array<{
    chain: string;
    nativeSymbol: string;
    nativeBal: string;
    tokens: Array<{ symbol: string; balance: string; raw: bigint }>;
  }> = [];

  for (const [name, info] of Object.entries(CHAINS)) {
    try {
      const pub = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });

      // Get native balance
      const nativeBal = await pub.getBalance({ address: account.address });
      const nativeStr = formatEther(nativeBal);

      // Get all token balances
      const tokenEntries = Object.values(info.tokens);
      const tokenBalances: Array<{ symbol: string; balance: string; raw: bigint }> = [];

      for (const token of tokenEntries) {
        try {
          const bal = await pub.readContract({
            address: token.address,
            abi: ERC20_ABI,
            functionName: "balanceOf",
            args: [account.address],
          }) as bigint;
          tokenBalances.push({
            symbol: token.symbol,
            balance: formatUnits(bal, token.decimals),
            raw: bal,
          });
        } catch {
          tokenBalances.push({ symbol: token.symbol, balance: "ERROR", raw: 0n });
        }
      }

      results.push({
        chain: name,
        nativeSymbol: info.nativeSymbol,
        nativeBal: nativeStr,
        tokens: tokenBalances,
      });

      // Print row
      const tokenStr = tokenBalances
        .map(t => `${t.symbol}: $${t.balance}`)
        .join(" | ");
      console.log(
        `  ${info.name.padEnd(12)} | ${info.nativeSymbol.padEnd(4)} ${nativeStr.slice(0, 12).padStart(12)} | ${tokenStr}`
      );
    } catch (err: any) {
      console.log(`  ${info.name.padEnd(12)} | ERROR: ${err.message.slice(0, 60)}`);
    }
  }

  // Summary: total per token across all chains
  console.log("\n" + "=".repeat(90));
  console.log("TOTALS PER TOKEN:");
  const allSymbols = new Set<string>();
  for (const r of results) {
    for (const t of r.tokens) {
      allSymbols.add(t.symbol);
    }
  }
  for (const symbol of Array.from(allSymbols).sort()) {
    let total = 0;
    const breakdown: string[] = [];
    for (const r of results) {
      const tok = r.tokens.find(t => t.symbol === symbol);
      if (tok && tok.balance !== "ERROR") {
        const val = parseFloat(tok.balance);
        if (val > 0) {
          total += val;
          breakdown.push(`${r.chain}=$${val.toFixed(2)}`);
        }
      }
    }
    console.log(`  ${symbol.padEnd(6)}: $${total.toFixed(2)} total  [${breakdown.join(", ")}]`);
  }

  // Facilitator support matrix (for reference)
  console.log("\n" + "=".repeat(90));
  console.log("FACILITATOR TOKEN SUPPORT MATRIX:");
  console.log("  Chain        | USDC | EURC | AUSD | PYUSD | USDT |");
  console.log("  " + "-".repeat(57));

  const facilitatorSupport: Record<string, string[]> = {
    base:      ["USDC", "EURC"],
    ethereum:  ["USDC", "EURC", "AUSD", "PYUSD"],
    polygon:   ["USDC", "AUSD"],
    arbitrum:  ["USDC", "AUSD", "USDT"],
    avalanche: ["USDC", "EURC", "AUSD"],
    optimism:  ["USDC", "USDT"],
    celo:      ["USDC", "USDT"],
    monad:     ["USDC", "AUSD", "USDT"],
  };

  for (const [chain, tokens] of Object.entries(facilitatorSupport)) {
    const row = ["USDC", "EURC", "AUSD", "PYUSD", "USDT"]
      .map(t => tokens.includes(t) ? "  Y  " : "  -  ")
      .join("|");
    console.log(`  ${(CHAINS[chain]?.name || chain).padEnd(12)} | ${row} |`);
  }
}

main().catch(console.error);
