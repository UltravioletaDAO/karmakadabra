/**
 * Spot-check agent wallet balances across all 8 chains.
 * Checks first, middle, and last agent to verify distribution.
 */
import { createPublicClient, http, formatUnits, formatEther, type Address } from "viem";
import { CHAINS } from "./lib/chains.js";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

const ERC20_ABI = [{
  name: "balanceOf", type: "function", stateMutability: "view",
  inputs: [{ name: "account", type: "address" }],
  outputs: [{ name: "", type: "uint256" }],
}] as const;

const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const agents = manifest.wallets;

// Sample: first, middle, last
const sampleIdx = [0, Math.floor(agents.length / 2), agents.length - 1];
const samples = sampleIdx.map(i => agents[i]);

console.log(`Checking ${samples.length} agents (of ${agents.length}) across ${Object.keys(CHAINS).length} chains\n`);

for (const [chainName, info] of Object.entries(CHAINS)) {
  console.log(`--- ${info.name} ---`);
  const client = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });

  for (const agent of samples) {
    const addr = agent.address as Address;
    try {
      const nativeBal = await client.getBalance({ address: addr });
      const nativeStr = formatEther(nativeBal);

      const tokenBals: string[] = [];
      for (const token of Object.values(info.tokens)) {
        try {
          const bal = await client.readContract({
            address: token.address,
            abi: ERC20_ABI,
            functionName: "balanceOf",
            args: [addr],
          }) as bigint;
          if (bal > 0n) {
            tokenBals.push(`${token.symbol}:$${formatUnits(bal, token.decimals)}`);
          }
        } catch {}
      }

      const hasNative = parseFloat(nativeStr) > 0;
      const hasTokens = tokenBals.length > 0;
      const status = hasNative && hasTokens ? "OK" : hasTokens ? "NO GAS" : hasNative ? "NO TOKENS" : "EMPTY";

      console.log(`  ${agent.name.padEnd(20)} ${info.nativeSymbol}:${nativeStr.substring(0, 10).padEnd(12)} ${tokenBals.join(" | ") || "(none)"} [${status}]`);
    } catch (err: any) {
      console.log(`  ${agent.name.padEnd(20)} ERROR: ${err.message.substring(0, 60)}`);
    }
  }
  console.log();
}

// Summary: count how many agents have tokens on each chain (check ALL agents)
console.log("=== FULL COUNT (all agents) ===\n");
for (const [chainName, info] of Object.entries(CHAINS)) {
  const client = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });
  let withTokens = 0;
  let withGas = 0;

  for (const agent of agents) {
    try {
      const nativeBal = await client.getBalance({ address: agent.address as Address });
      if (nativeBal > 0n) withGas++;

      for (const token of Object.values(info.tokens)) {
        try {
          const bal = await client.readContract({
            address: token.address, abi: ERC20_ABI, functionName: "balanceOf",
            args: [agent.address as Address],
          }) as bigint;
          if (bal > 0n) { withTokens++; break; }
        } catch {}
      }
    } catch {}
  }

  const gasOk = withGas >= 20 ? "PASS" : withGas > 0 ? `${withGas}/24` : "NONE";
  const tokenOk = withTokens >= 20 ? "PASS" : withTokens > 0 ? `${withTokens}/24` : "NONE";
  console.log(`  ${info.name.padEnd(12)} Gas: ${gasOk.padEnd(8)} Tokens: ${tokenOk}`);
}
