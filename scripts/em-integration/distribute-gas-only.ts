/**
 * Distribute ONLY native gas tokens to agent wallets on a single chain.
 * Uses sequential transfers (works on all chains).
 *
 * Usage: npx tsx distribute-gas-only.ts --chain avalanche --gas 0.005
 */
import {
  createPublicClient,
  createWalletClient,
  http,
  parseEther,
  formatEther,
  getAddress,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import { getChain, DISPERSE_ADDRESS, DISPERSE_ABI } from "./lib/chains.js";
import type { WalletManifest } from "./generate-wallets.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

const args = process.argv.slice(2);
const chainName = args.includes("--chain") ? args[args.indexOf("--chain") + 1] : "avalanche";
const gasPerWallet = args.includes("--gas") ? args[args.indexOf("--gas") + 1] : "0.005";
const dryRun = args.includes("--dry-run");

const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
if (!pk) { console.error("No key"); process.exit(1); }

const chainInfo = getChain(chainName);
const account = privateKeyToAccount(pk);
const client = createPublicClient({ chain: chainInfo.chain, transport: http(chainInfo.rpcUrl) });
const wallet = createWalletClient({ account, chain: chainInfo.chain, transport: http(chainInfo.rpcUrl) });

const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const wallets = manifest.wallets.map(w => ({ name: w.name, address: getAddress(w.address) as Address }));

const gasAmount = parseEther(gasPerWallet);
const totalGas = gasAmount * BigInt(wallets.length);
const balance = await client.getBalance({ address: account.address });

console.log(`\n=== Gas Distribution: ${chainInfo.name} ===`);
console.log(`  Funder:      ${account.address}`);
console.log(`  Balance:     ${formatEther(balance)} ${chainInfo.nativeSymbol}`);
console.log(`  Per wallet:  ${gasPerWallet} ${chainInfo.nativeSymbol}`);
console.log(`  Total need:  ${formatEther(totalGas)} ${chainInfo.nativeSymbol} (${wallets.length} wallets)`);
console.log(`  Disperse:    ${chainInfo.disperseAvailable ? "YES (batch)" : "NO (sequential)"}`);

if (balance < totalGas + parseEther("0.001")) {
  console.error(`\nINSUFFICIENT: need ~${formatEther(totalGas + parseEther("0.001"))}, have ${formatEther(balance)}`);
  process.exit(1);
}

if (dryRun) {
  console.log(`\n[DRY RUN] Would distribute ${formatEther(totalGas)} ${chainInfo.nativeSymbol}`);
  process.exit(0);
}

let confirmed = 0;

if (chainInfo.disperseAvailable) {
  // Batch via Disperse.app
  console.log(`\nDispersing ${chainInfo.nativeSymbol} via Disperse.app...`);
  const amounts = wallets.map(() => gasAmount);
  try {
    const tx = await wallet.writeContract({
      address: DISPERSE_ADDRESS,
      abi: DISPERSE_ABI,
      functionName: "disperseEther",
      args: [wallets.map(w => w.address), amounts],
      value: totalGas,
    });
    console.log(`TX: ${tx}`);
    const receipt = await client.waitForTransactionReceipt({ hash: tx, timeout: 120_000 });
    console.log(`${receipt.status === "success" ? "OK" : "REVERTED"} (block ${receipt.blockNumber}, gas ${receipt.gasUsed})`);
    if (receipt.status === "success") confirmed = wallets.length;
  } catch (err: any) {
    console.error(`FAILED: ${err.message.substring(0, 100)}`);
  }
} else {
  // Sequential transfers
  console.log(`\nSending ${chainInfo.nativeSymbol} sequentially...`);
  for (let i = 0; i < wallets.length; i++) {
    try {
      const tx = await wallet.sendTransaction({ to: wallets[i].address, value: gasAmount });
      await client.waitForTransactionReceipt({ hash: tx });
      confirmed++;
      if ((i + 1) % 6 === 0 || i === wallets.length - 1) {
        console.log(`  [${i + 1}/${wallets.length}] ${wallets[i].name} ... ${confirmed} confirmed`);
      }
    } catch (err: any) {
      console.error(`  [${i + 1}/${wallets.length}] ${wallets[i].name} FAILED: ${err.message.substring(0, 60)}`);
    }
  }
}

const finalBal = await client.getBalance({ address: account.address });
console.log(`\nDone: ${confirmed}/${wallets.length} wallets funded`);
console.log(`Remaining: ${formatEther(finalBal)} ${chainInfo.nativeSymbol}`);
