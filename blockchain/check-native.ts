/**
 * Check native token balance on a chain.
 * Usage: npx tsx kk/check-native.ts <chain> <address>
 */
import { createPublicClient, http, formatEther } from "viem";
import { CHAINS } from "./lib/chains.js";

async function main() {
  const chain = process.argv[2] || "monad";
  const address = process.argv[3] || "0xD3868E1eD738CED6945A574a7c769433BeD5d474";
  const info = CHAINS[chain];
  if (!info) {
    console.error("Unknown chain: " + chain);
    process.exit(1);
  }
  const pub = createPublicClient({ chain: info.chain, transport: http(info.rpcUrl) });
  const bal = await pub.getBalance({ address: address as `0x${string}` });
  console.log(info.nativeSymbol + " on " + info.name + ": " + formatEther(bal));
}

main().catch((err) => { console.error(err.message); process.exit(1); });
