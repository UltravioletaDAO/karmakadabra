/**
 * Check Ethereum L1: nonce status, stuck TXs, and pending approve TX receipts
 */
import { createPublicClient, http, formatEther } from "viem";
import { mainnet } from "viem/chains";
import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

const rpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
const client = createPublicClient({ chain: mainnet, transport: http(rpc) });

const addr = "0xD3868E1eD738CED6945A574a7c769433BeD5d474" as `0x${string}`;

const confirmed = await client.getTransactionCount({ address: addr });
const pending = await client.getTransactionCount({ address: addr, blockTag: "pending" });
const bal = await client.getBalance({ address: addr });

console.log("Confirmed nonce:", confirmed);
console.log("Pending nonce:  ", pending);
console.log("Stuck TXs:      ", pending - confirmed);
console.log("ETH balance:    ", formatEther(bal));

// Check known pending TX hashes
const txHashes = [
  "0x198593e3ca0a49aef93fd93bba0ef9ed2b170c453160b574b407b93955e16a13", // 1st EURC approve attempt
  "0x5298c731d4a7216a7d6c390acba8528278f16962d8c850e40f14d497b61f2988", // 2nd EURC approve attempt
] as `0x${string}`[];

for (const hash of txHashes) {
  try {
    const receipt = await client.getTransactionReceipt({ hash });
    console.log(`TX ${hash.slice(0, 10)}...: ${receipt.status} (block ${receipt.blockNumber})`);
  } catch {
    // Check if TX exists but unconfirmed
    try {
      const tx = await client.getTransaction({ hash });
      console.log(`TX ${hash.slice(0, 10)}...: PENDING (nonce=${tx.nonce}, maxPriorityFee=${tx.maxPriorityFeePerGas})`);
    } catch {
      console.log(`TX ${hash.slice(0, 10)}...: NOT FOUND (dropped from mempool)`);
    }
  }
}

// Check current gas
const gasPrice = await client.getGasPrice();
const block = await client.getBlock();
console.log("\nCurrent gas:");
console.log("  Gas price:  ", Number(gasPrice) / 1e9, "gwei");
console.log("  Base fee:   ", block.baseFeePerGas ? Number(block.baseFeePerGas) / 1e9 : "N/A", "gwei");
