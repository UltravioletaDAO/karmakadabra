/**
 * Retry AUSD disperse on Ethereum L1 using LlamaRPC for both send and poll.
 * AUSD approve already confirmed (allowance should be set).
 */
import {
  createPublicClient,
  createWalletClient,
  http,
  parseUnits,
  parseGwei,
  formatUnits,
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
import { DISPERSE_ADDRESS, DISPERSE_ABI, ERC20_ABI } from "./lib/chains.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

// Prefer QuikNode private RPC, fallback to LlamaRPC for large TX drop issues
const rpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
console.log("Using LlamaRPC for send + poll");

const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
if (!pk) { console.error("No key"); process.exit(1); }

const account = privateKeyToAccount(pk);
const client = createPublicClient({ chain: mainnet, transport: http(rpc) });
const wallet = createWalletClient({ account, chain: mainnet, transport: http(rpc) });

const AUSD: Address = "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a";

const nonce = await client.getTransactionCount({ address: account.address });
console.log(`Nonce: ${nonce}`);
console.log(`ETH: ${formatEther(await client.getBalance({ address: account.address }))}`);

// Check allowance
const allowance = await client.readContract({
  address: AUSD,
  abi: ERC20_ABI,
  functionName: "allowance",
  args: [account.address, DISPERSE_ADDRESS],
}) as bigint;
console.log(`AUSD allowance: ${formatUnits(allowance, 6)}`);

const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const addresses = manifest.wallets.map(w => getAddress(w.address) as Address);
const amt = parseUnits("0.12", 6);
const amounts = addresses.map(() => amt);
const total = amt * BigInt(addresses.length);

if (allowance < total) {
  console.log("Need new approve...");
  const approveTx = await wallet.writeContract({
    address: AUSD,
    abi: ERC20_ABI,
    functionName: "approve",
    args: [DISPERSE_ADDRESS, total + (total / 10n)],
    nonce,
    maxPriorityFeePerGas: parseGwei("0.5"),
  });
  console.log(`Approve TX: ${approveTx}`);
  const receipt = await client.waitForTransactionReceipt({ hash: approveTx, timeout: 600_000 });
  console.log(`Approve: ${receipt.status} (block ${receipt.blockNumber})`);
}

const disperseNonce = allowance >= total ? nonce : nonce + 1;
console.log(`\nDispersing ${formatUnits(total, 6)} AUSD to ${addresses.length} wallets (nonce=${disperseNonce})...`);

const tx = await wallet.writeContract({
  address: DISPERSE_ADDRESS,
  abi: DISPERSE_ABI,
  functionName: "disperseToken",
  args: [AUSD, addresses, amounts],
  nonce: disperseNonce,
  maxPriorityFeePerGas: parseGwei("0.5"),
});
console.log(`TX: ${tx}`);

// Manual polling loop with detailed status
const start = Date.now();
while (true) {
  const elapsed = Math.floor((Date.now() - start) / 1000);
  if (elapsed > 900) {
    console.log("TIMEOUT after 900s");
    // Check if TX was actually mined
    const newNonce = await client.getTransactionCount({ address: account.address });
    const ausdBal = await client.readContract({ address: AUSD, abi: ERC20_ABI, functionName: "balanceOf", args: [account.address] }) as bigint;
    console.log(`Nonce now: ${newNonce}, AUSD bal: ${formatUnits(ausdBal, 6)}`);
    if (newNonce > disperseNonce) {
      console.log("TX WAS MINED despite timeout!");
    }
    break;
  }

  try {
    const receipt = await client.getTransactionReceipt({ hash: tx });
    console.log(`CONFIRMED: ${receipt.status} (block ${receipt.blockNumber}, gas ${receipt.gasUsed}) [${elapsed}s]`);
    break;
  } catch {
    if (elapsed > 0 && elapsed % 60 === 0) {
      // Check pending nonce
      const pn = await client.getTransactionCount({ address: account.address, blockTag: "pending" });
      console.log(`... waiting (${elapsed}s, pending nonce: ${pn})`);
    }
  }
  await new Promise(r => setTimeout(r, 12000)); // Poll every block
}

console.log(`\nFinal ETH: ${formatEther(await client.getBalance({ address: account.address }))}`);
