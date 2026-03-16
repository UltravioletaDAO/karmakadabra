/**
 * Distribute AUSD on Ethereum L1 — approve + disperse with low priority fee
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

const rpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
if (!pk) { console.error("No key"); process.exit(1); }

const account = privateKeyToAccount(pk);
const client = createPublicClient({ chain: mainnet, transport: http(rpc) });
const wallet = createWalletClient({ account, chain: mainnet, transport: http(rpc) });

const AUSD: Address = "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a";
const PRIORITY = parseGwei("0.1"); // Minimal tip — base fee is ~0.05 gwei

const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const addresses = manifest.wallets.map(w => getAddress(w.address) as Address);
const amt = parseUnits("0.12", 6);
const amounts = addresses.map(() => amt);
const total = amt * BigInt(addresses.length);
const approveAmt = total + (total / 10n);

let nonce = await client.getTransactionCount({ address: account.address });
const bal = await client.getBalance({ address: account.address });
console.log(`Nonce: ${nonce}, ETH: ${formatEther(bal)}`);

const ausdBal = await client.readContract({ address: AUSD, abi: ERC20_ABI, functionName: "balanceOf", args: [account.address] }) as bigint;
console.log(`AUSD: ${formatUnits(ausdBal, 6)}, Need: ${formatUnits(total, 6)}\n`);

// 1. Approve
console.log(`[1/2] Approve ${formatUnits(approveAmt, 6)} AUSD (nonce=${nonce})...`);
const approveTx = await wallet.writeContract({
  address: AUSD,
  abi: ERC20_ABI,
  functionName: "approve",
  args: [DISPERSE_ADDRESS, approveAmt],
  nonce,
  maxPriorityFeePerGas: PRIORITY,
});
console.log(`TX: ${approveTx}`);
const approveReceipt = await client.waitForTransactionReceipt({ hash: approveTx, timeout: 900_000 });
console.log(`Approve: ${approveReceipt.status} (block ${approveReceipt.blockNumber}, gas ${approveReceipt.gasUsed})`);
nonce++;

// 2. Disperse
console.log(`\n[2/2] Disperse AUSD to ${addresses.length} wallets (nonce=${nonce})...`);
const disperseTx = await wallet.writeContract({
  address: DISPERSE_ADDRESS,
  abi: DISPERSE_ABI,
  functionName: "disperseToken",
  args: [AUSD, addresses, amounts],
  nonce,
  maxPriorityFeePerGas: PRIORITY,
});
console.log(`TX: ${disperseTx}`);
const disperseReceipt = await client.waitForTransactionReceipt({ hash: disperseTx, timeout: 900_000 });
console.log(`Disperse: ${disperseReceipt.status} (block ${disperseReceipt.blockNumber}, gas ${disperseReceipt.gasUsed})`);

console.log(`\nFinal ETH: ${formatEther(await client.getBalance({ address: account.address }))}`);
console.log("AUSD DONE!");
