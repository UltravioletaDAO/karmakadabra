/**
 * Distribute ETH gas to 24 agent wallets via Disperse.app on Ethereum L1.
 * Uses LlamaRPC (QuikNode drops large TXs) + manual polling.
 */
import {
  createPublicClient,
  createWalletClient,
  http,
  parseEther,
  parseGwei,
  formatEther,
  getAddress,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { mainnet } from "viem/chains";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import { DISPERSE_ADDRESS, DISPERSE_ABI } from "./lib/chains.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// Prefer QuikNode private RPC, fallback to LlamaRPC only if needed
const rpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
if (!pk) { console.error("No key"); process.exit(1); }

const account = privateKeyToAccount(pk);
const client = createPublicClient({ chain: mainnet, transport: http(rpc) });
const wallet = createWalletClient({ account, chain: mainnet, transport: http(rpc) });

const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const addresses = manifest.wallets.map(w => getAddress(w.address) as Address);
const gasPerWallet = parseEther("0.0003");
const totalGas = gasPerWallet * BigInt(addresses.length);
const amounts = addresses.map(() => gasPerWallet);

const balance = await client.getBalance({ address: account.address });
const nonce = await client.getTransactionCount({ address: account.address });

console.log("=== Ethereum L1 Gas Distribution (LlamaRPC) ===");
console.log(`  Wallet: ${account.address}`);
console.log(`  ETH: ${formatEther(balance)}`);
console.log(`  Need: ${formatEther(totalGas)} (${addresses.length} × 0.0003)`);
console.log(`  Nonce: ${nonce}`);

const tx = await wallet.writeContract({
  address: DISPERSE_ADDRESS,
  abi: DISPERSE_ABI,
  functionName: "disperseEther",
  args: [addresses, amounts],
  value: totalGas,
  nonce,
  maxPriorityFeePerGas: parseGwei("0.5"),
});
console.log(`\nTX: ${tx}`);

// Manual polling (12s per block)
const start = Date.now();
while (true) {
  const elapsed = Math.floor((Date.now() - start) / 1000);
  if (elapsed > 600) {
    console.log("TIMEOUT (600s)");
    const newNonce = await client.getTransactionCount({ address: account.address });
    if (newNonce > nonce) console.log("TX WAS MINED despite timeout!");
    break;
  }
  try {
    const receipt = await client.getTransactionReceipt({ hash: tx });
    console.log(`CONFIRMED: ${receipt.status} (block ${receipt.blockNumber}, gas ${receipt.gasUsed}) [${elapsed}s]`);
    break;
  } catch {
    if (elapsed > 0 && elapsed % 30 === 0) {
      const pn = await client.getTransactionCount({ address: account.address, blockTag: "pending" });
      console.log(`... waiting (${elapsed}s, pending nonce: ${pn})`);
    }
  }
  await new Promise(r => setTimeout(r, 12000));
}

const finalBal = await client.getBalance({ address: account.address });
console.log(`\nRemaining ETH: ${formatEther(finalBal)}`);
