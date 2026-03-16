/**
 * Check master wallet balances across all 8 chains — native + USDC.
 * Usage: PRIVATE_KEY=0x... npx tsx kk/check-all-balances.ts
 */
import { createPublicClient, http, formatUnits, formatEther } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { CHAINS, ERC20_ABI } from "./lib/chains.js";
import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

async function main() {
  const pk = (process.env.PRIVATE_KEY || process.env.WALLET_PRIVATE_KEY) as `0x${string}`;
  if (!pk) { console.error("PRIVATE_KEY not set"); process.exit(1); }
  const account = privateKeyToAccount(pk);
  console.log("Master wallet: " + account.address);
  console.log("=".repeat(70));

  const gasNeeded: Record<string, string> = {
    base: "0.012",       // 24 * 0.0005 = 0.012 ETH
    ethereum: "0.0072",  // 24 * 0.0003 = 0.0072 ETH
    polygon: "2.4",      // 24 * 0.1 = 2.4 POL
    arbitrum: "0.012",   // 24 * 0.0005 = 0.012 ETH
    avalanche: "0.24",   // 24 * 0.01 = 0.24 AVAX
    optimism: "0.012",   // 24 * 0.0005 = 0.012 ETH
    celo: "0.24",        // 24 * 0.01 = 0.24 CELO
    monad: "0.24",       // 24 * 0.01 = 0.24 MON
  };

  for (const [name, info] of Object.entries(CHAINS)) {
    try {
      const pub = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });
      const [nativeBal, usdcBal] = await Promise.all([
        pub.getBalance({ address: account.address }),
        pub.readContract({ address: info.usdc, abi: ERC20_ABI, functionName: "balanceOf", args: [account.address] }) as Promise<bigint>,
      ]);
      const nativeStr = formatEther(nativeBal);
      const usdcStr = formatUnits(usdcBal, 6);
      const needed = gasNeeded[name] || "?";
      const hasEnough = parseFloat(nativeStr) >= parseFloat(needed);
      const status = hasEnough ? "OK" : "NEED GAS";
      console.log(
        `  ${info.name.padEnd(12)} | ${info.nativeSymbol.padEnd(4)} ${nativeStr.slice(0, 12).padStart(12)} | USDC $${usdcStr.padStart(10)} | gas need: ${needed} | ${status}`
      );
    } catch (err: any) {
      console.log(`  ${info.name.padEnd(12)} | ERROR: ${err.message.slice(0, 60)}`);
    }
  }
}

main().catch(console.error);
