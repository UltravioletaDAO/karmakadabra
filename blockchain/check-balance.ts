/**
 * Quick balance checker for master wallet across chains.
 * Usage: PRIVATE_KEY=0x... npx tsx kk/check-balance.ts [chain]
 */
import { createPublicClient, http, formatUnits } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { CHAINS, ERC20_ABI, type ChainInfo } from "./lib/chains.js";

async function main() {
  const chain = process.argv[2] || "monad";
  const info: ChainInfo = CHAINS[chain];
  if (!info) {
    console.error("Unknown chain: " + chain + ". Valid: " + Object.keys(CHAINS).join(", "));
    process.exit(1);
  }

  const account = privateKeyToAccount(process.env.PRIVATE_KEY as `0x${string}`);
  const pub = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });

  const balance = await pub.readContract({
    address: info.usdc,
    abi: ERC20_ABI,
    functionName: "balanceOf",
    args: [account.address],
  });

  console.log(info.name + " USDC: $" + formatUnits(balance as bigint, 6));
}

main().catch((err) => { console.error(err.message); process.exit(1); });
