/**
 * Unstick Ethereum nonce by sending a 0-value self-transfer at the stuck nonce
 * with a higher priority fee to replace any pending TXs.
 * Then retry EURC disperse + AUSD distribute.
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

const confirmed = await client.getTransactionCount({ address: account.address });
const pending = await client.getTransactionCount({ address: account.address, blockTag: "pending" });
const bal = await client.getBalance({ address: account.address });

console.log("Confirmed nonce:", confirmed);
console.log("Pending nonce:  ", pending);
console.log("Stuck TXs:      ", pending - confirmed);
console.log("ETH:            ", formatEther(bal));

if (pending > confirmed) {
  console.log(`\nClearing ${pending - confirmed} stuck nonce(s)...`);
  for (let n = confirmed; n < pending; n++) {
    console.log(`  Sending cancel TX at nonce=${n} with 10 gwei tip...`);
    try {
      const tx = await wallet.sendTransaction({
        to: account.address,
        value: 0n,
        nonce: n,
        maxPriorityFeePerGas: parseGwei("10"),
        gas: 21000n,
      });
      console.log(`  TX: ${tx}`);
      const receipt = await client.waitForTransactionReceipt({
        hash: tx,
        timeout: 120_000,
      });
      console.log(`  ${receipt.status === "success" ? "OK" : "REVERTED"} (block ${receipt.blockNumber})`);
    } catch (err: any) {
      console.error(`  Error: ${err.message}`);
    }
  }
} else {
  console.log("\nNo stuck nonces. Ready to proceed.");
}

// Re-check
const newNonce = await client.getTransactionCount({ address: account.address });
const newBal = await client.getBalance({ address: account.address });
console.log("\nAfter cleanup:");
console.log("Nonce:", newNonce);
console.log("ETH:  ", formatEther(newBal));

// Now do EURC disperse (approve already confirmed at nonce 6!)
// Check if allowance is still set
const EURC: Address = "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c";
const allowance = await client.readContract({
  address: EURC,
  abi: ERC20_ABI,
  functionName: "allowance",
  args: [account.address, DISPERSE_ADDRESS],
}) as bigint;
console.log("\nEURC allowance for Disperse:", formatUnits(allowance, 6));

if (allowance > 0n) {
  console.log("Allowance still active! Proceeding directly to disperse...");

  const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
  const addresses = manifest.wallets.map(w => getAddress(w.address) as Address);
  const amt = parseUnits("0.12", 6);
  const amounts = addresses.map(() => amt);
  const total = amt * BigInt(addresses.length);

  if (allowance >= total) {
    console.log(`\nDispersing ${formatUnits(total, 6)} EURC to ${addresses.length} wallets...`);

    // Use minimal priority fee (0.1 gwei) to save ETH
    // Base fee is 0.05 gwei so total = 0.15 gwei, still very attractive
    const disperseNonce = newNonce;
    try {
      const tx = await wallet.writeContract({
        address: DISPERSE_ADDRESS,
        abi: DISPERSE_ABI,
        functionName: "disperseToken",
        args: [EURC, addresses, amounts],
        nonce: disperseNonce,
        maxPriorityFeePerGas: parseGwei("0.1"),
        // Let viem estimate gas (don't hardcode)
      });
      console.log(`TX sent: ${tx}`);
      console.log("Waiting for confirmation (up to 15 min)...");

      const receipt = await client.waitForTransactionReceipt({
        hash: tx,
        timeout: 900_000,
      });
      console.log(`EURC disperse: ${receipt.status} (block ${receipt.blockNumber}, gas: ${receipt.gasUsed})`);
    } catch (err: any) {
      console.error(`Disperse error: ${err.message}`);
    }
  }
}

console.log("\nFinal ETH:", formatEther(await client.getBalance({ address: account.address })));
