/**
 * Quick check: Ethereum L1 TX status + wallet nonce + balance
 */
import { createPublicClient, http, formatEther, formatUnits } from "viem";
import { mainnet } from "viem/chains";
import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../../.env.local") });

const rpc = process.env.ETHEREUM_RPC_URL || "https://eth.llamarpc.com";
console.log("RPC:", rpc.includes("quiknode") ? "QuikNode (private)" : rpc.substring(0, 40));

const client = createPublicClient({ chain: mainnet, transport: http(rpc) });

// Check pending TX
const txHash = "0x2d654b51bb97fcb8f5a37609ae4e385d5288985ba8a20237f0de2d7fc7ad8aea" as `0x${string}`;
try {
  const receipt = await client.getTransactionReceipt({ hash: txHash });
  console.log("USDC Approve TX:", receipt.status === "success" ? "SUCCESS" : "REVERTED");
  console.log("  Block:", receipt.blockNumber.toString());
} catch {
  console.log("USDC Approve TX: NOT FOUND (dropped or pending)");
}

// Nonce
const addr = "0xD3868E1eD738CED6945A574a7c769433BeD5d474" as `0x${string}`;
const nonce = await client.getTransactionCount({ address: addr });
console.log("Confirmed nonce:", nonce);

// ETH balance
const ethBal = await client.getBalance({ address: addr });
console.log("ETH balance:", formatEther(ethBal));

// Token balances
const ERC20_ABI = [{ name: "balanceOf", type: "function", stateMutability: "view", inputs: [{ name: "account", type: "address" }], outputs: [{ name: "", type: "uint256" }] }] as const;

const tokens = [
  { symbol: "USDC", address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" as `0x${string}`, decimals: 6 },
  { symbol: "EURC", address: "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c" as `0x${string}`, decimals: 6 },
  { symbol: "AUSD", address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a" as `0x${string}`, decimals: 6 },
  { symbol: "PYUSD", address: "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8" as `0x${string}`, decimals: 6 },
];

for (const t of tokens) {
  const bal = await client.readContract({ address: t.address, abi: ERC20_ABI, functionName: "balanceOf", args: [addr] }) as bigint;
  console.log(`${t.symbol}: $${formatUnits(bal, t.decimals)}`);
}
