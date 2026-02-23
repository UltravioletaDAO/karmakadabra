/**
 * Focused EURC + AUSD distribution on Ethereum L1
 * Sends approve + disperse with explicit nonce management and retry logic.
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

const TOKENS = [
  { symbol: "EURC", address: "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c" as Address, decimals: 6 },
  { symbol: "AUSD", address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a" as Address, decimals: 6 },
];

const AMOUNT_PER_WALLET = "0.12";
const PRIORITY_FEE = parseGwei("3");

// Use QuikNode for sending, LlamaRPC for receipt polling
const sendRpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
const pollRpc = "https://eth.llamarpc.com";

console.log("Send RPC:", sendRpc.includes("quiknode") ? "QuikNode" : sendRpc.substring(0, 40));
console.log("Poll RPC:", pollRpc.substring(0, 40));

const pk = (process.env.WALLET_PRIVATE_KEY || process.env.PRIVATE_KEY) as Hex;
if (!pk) { console.error("No WALLET_PRIVATE_KEY"); process.exit(1); }

const account = privateKeyToAccount(pk);
const sendClient = createPublicClient({ chain: mainnet, transport: http(sendRpc) });
const pollClient = createPublicClient({ chain: mainnet, transport: http(pollRpc) });
const wallet = createWalletClient({ account, chain: mainnet, transport: http(sendRpc) });

// Load wallets
const manifest: WalletManifest = JSON.parse(readFileSync(resolve(__dirname, "config/wallets.json"), "utf-8"));
const addresses = manifest.wallets.map(w => getAddress(w.address) as Address);
console.log(`Wallets: ${addresses.length}`);

// Get confirmed nonce
let nonce = await sendClient.getTransactionCount({ address: account.address });
console.log(`Starting nonce: ${nonce}`);
console.log(`ETH balance: ${formatEther(await sendClient.getBalance({ address: account.address }))}\n`);

async function waitForTx(hash: Hex, label: string, maxWait = 900): Promise<boolean> {
  console.log(`  Waiting for ${label}: ${hash}`);
  const start = Date.now();
  while ((Date.now() - start) < maxWait * 1000) {
    try {
      // Try both RPCs
      const receipt = await pollClient.getTransactionReceipt({ hash });
      if (receipt.status === "success") {
        console.log(`  CONFIRMED in block ${receipt.blockNumber} (${((Date.now() - start) / 1000).toFixed(0)}s)`);
        console.log(`  Gas used: ${receipt.gasUsed.toString()}`);
        return true;
      } else {
        console.log(`  REVERTED in block ${receipt.blockNumber}`);
        return false;
      }
    } catch {
      // Not found yet — also try send RPC
      try {
        const receipt = await sendClient.getTransactionReceipt({ hash });
        if (receipt.status === "success") {
          console.log(`  CONFIRMED (via send RPC) in block ${receipt.blockNumber} (${((Date.now() - start) / 1000).toFixed(0)}s)`);
          return true;
        }
      } catch {
        // Still pending
      }
    }
    const elapsed = ((Date.now() - start) / 1000).toFixed(0);
    if (Number(elapsed) % 30 === 0 && Number(elapsed) > 0) {
      console.log(`  ... still waiting (${elapsed}s)`);
    }
    await new Promise(r => setTimeout(r, 5000));
  }
  console.log(`  TIMEOUT after ${maxWait}s`);
  return false;
}

// Process each token
for (const token of TOKENS) {
  console.log(`\n=== ${token.symbol} ===`);

  const tokenAmount = parseUnits(AMOUNT_PER_WALLET, token.decimals);
  const totalToken = tokenAmount * BigInt(addresses.length);
  const approveAmt = totalToken + (totalToken / 10n); // 10% buffer

  const balance = await sendClient.readContract({
    address: token.address,
    abi: ERC20_ABI,
    functionName: "balanceOf",
    args: [account.address],
  }) as bigint;

  console.log(`  Balance: ${formatUnits(balance, token.decimals)}`);
  console.log(`  Need:    ${formatUnits(totalToken, token.decimals)}`);

  if (balance < totalToken) {
    console.log(`  SKIP: insufficient balance`);
    continue;
  }

  // 1. Approve with explicit nonce
  console.log(`\n  [1/2] Approve ${formatUnits(approveAmt, token.decimals)} ${token.symbol} (nonce=${nonce})...`);
  try {
    const approveTx = await wallet.writeContract({
      address: token.address,
      abi: ERC20_ABI,
      functionName: "approve",
      args: [DISPERSE_ADDRESS, approveAmt],
      nonce,
      maxPriorityFeePerGas: PRIORITY_FEE,
      gas: 60000n, // Explicit gas limit for approve
    });
    console.log(`  TX sent: ${approveTx}`);

    const ok = await waitForTx(approveTx, "approve");
    if (!ok) {
      console.log(`  Approve failed, skipping ${token.symbol}`);
      continue;
    }
    nonce++;
  } catch (err: any) {
    console.error(`  Approve error: ${err.message}`);
    continue;
  }

  // 2. Disperse
  const tokenAmounts = addresses.map(() => tokenAmount);
  console.log(`\n  [2/2] Disperse ${token.symbol} to ${addresses.length} wallets (nonce=${nonce})...`);
  try {
    const disperseTx = await wallet.writeContract({
      address: DISPERSE_ADDRESS,
      abi: DISPERSE_ABI,
      functionName: "disperseToken",
      args: [token.address, addresses, tokenAmounts],
      nonce,
      maxPriorityFeePerGas: PRIORITY_FEE,
      gas: 500000n, // Generous gas limit for 24-recipient disperse
    });
    console.log(`  TX sent: ${disperseTx}`);

    const ok = await waitForTx(disperseTx, "disperse");
    if (!ok) {
      console.log(`  Disperse failed for ${token.symbol}`);
      continue;
    }
    nonce++;
    console.log(`  ${token.symbol} DONE!`);
  } catch (err: any) {
    console.error(`  Disperse error: ${err.message}`);
    continue;
  }
}

// Final status
const finalBal = await sendClient.getBalance({ address: account.address });
console.log(`\n=== Summary ===`);
console.log(`ETH remaining: ${formatEther(finalBal)}`);
console.log(`Final nonce:   ${nonce}`);
