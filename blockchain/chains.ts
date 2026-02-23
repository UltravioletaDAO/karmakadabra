/**
 * Karma Kadabra V2 — Chain Configuration
 *
 * Single source of truth for all 8 supported EVM chains + stablecoins.
 * Mirrors NETWORK_CONFIG from mcp_server/integrations/x402/sdk_client.py.
 *
 * IMPORTANT: This file loads .env.local at module-load time so that
 * private RPC URLs from env vars are available when CHAINS is initialized.
 * Consumer scripts do NOT need to call dotenv before importing this module.
 */

import { config } from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

// Load .env.local before anything else so rpc() picks up private RPC URLs
const __chains_dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__chains_dirname, "../../../.env.local") });

import {
  type Chain,
  type Address,
  defineChain,
} from "viem";
import {
  base,
  mainnet,
  polygon,
  arbitrum,
  celo,
  avalanche,
  optimism,
} from "viem/chains";

// Monad not in viem's built-in chains yet
export const monad: Chain = defineChain({
  id: 143,
  name: "Monad",
  nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.monad.xyz"] } },
});

// ---------------------------------------------------------------------------
// Token Info
// ---------------------------------------------------------------------------

export interface TokenInfo {
  symbol: string;
  address: Address;
  decimals: number;
  name: string;
}

// ---------------------------------------------------------------------------
// Chain Info
// ---------------------------------------------------------------------------

export interface ChainInfo {
  name: string;
  chain: Chain;
  chainId: number;
  rpcUrl: string;
  /** @deprecated Use tokens["USDC"].address instead */
  usdc: Address;
  /** All supported stablecoins on this chain */
  tokens: Record<string, TokenInfo>;
  nativeSymbol: string;
  /** Disperse.app deployed and verified on this chain */
  disperseAvailable: boolean;
  /** deBridge DLN chain ID (may differ from native, e.g. Monad = 100000030) */
  debridgeChainId: string | null;
  /** Squid supports this chain */
  squidSupported: boolean;
}

/**
 * Disperse.app — same CREATE2 address on all chains where deployed.
 * Sends tokens/ETH to N recipients in 1 TX (45% gas savings).
 */
export const DISPERSE_ADDRESS: Address =
  "0xD152f549545093347A162Dce210e7293f1452150";

export const DISPERSE_ABI = [
  {
    name: "disperseEther",
    type: "function",
    stateMutability: "payable",
    inputs: [
      { name: "recipients", type: "address[]" },
      { name: "values", type: "uint256[]" },
    ],
    outputs: [],
  },
  {
    name: "disperseToken",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "token", type: "address" },
      { name: "recipients", type: "address[]" },
      { name: "values", type: "uint256[]" },
    ],
    outputs: [],
  },
] as const;

export const ERC20_ABI = [
  {
    name: "approve",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "spender", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    name: "balanceOf",
    type: "function",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    name: "allowance",
    type: "function",
    stateMutability: "view",
    inputs: [
      { name: "owner", type: "address" },
      { name: "spender", type: "address" },
    ],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    name: "transfer",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "to", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
] as const;

// ---------------------------------------------------------------------------
// RPC Override: use private QuikNode endpoints from .env.local when available
// Env var format: {CHAIN_UPPER}_RPC_URL (e.g., AVALANCHE_RPC_URL, BASE_MAINNET_RPC_URL)
// ---------------------------------------------------------------------------

const RPC_ENV_MAP: Record<string, string> = {
  base: "BASE_MAINNET_RPC_URL",
  ethereum: "ETHEREUM_RPC_URL",
  polygon: "POLYGON_RPC_URL",
  arbitrum: "ARBITRUM_RPC_URL",
  avalanche: "AVALANCHE_RPC_URL",
  optimism: "OPTIMISM_RPC_URL",
  celo: "CELO_RPC_URL",
  monad: "MONAD_RPC_URL",
};

function rpc(chain: string, fallback: string): string {
  const envVar = RPC_ENV_MAP[chain];
  return (envVar && process.env[envVar]) || fallback;
}

// ---------------------------------------------------------------------------
// The 8 Target Chains — with full stablecoin registry
// ---------------------------------------------------------------------------

export const CHAINS: Record<string, ChainInfo> = {
  base: {
    name: "Base",
    chain: base,
    chainId: 8453,
    rpcUrl: rpc("base", "https://mainnet.base.org"),
    usdc: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        decimals: 6,
        name: "USD Coin",
      },
      EURC: {
        symbol: "EURC",
        address: "0x60a3E35Cc302bFA44Cb288Bc5a4F316Fdb1adb42",
        decimals: 6,
        name: "EURC",
      },
    },
    nativeSymbol: "ETH",
    disperseAvailable: true,
    debridgeChainId: "8453",
    squidSupported: true,
  },
  ethereum: {
    name: "Ethereum",
    chain: mainnet,
    chainId: 1,
    rpcUrl: rpc("ethereum", "https://eth.llamarpc.com"),
    usdc: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        decimals: 6,
        name: "USD Coin",
      },
      PYUSD: {
        symbol: "PYUSD",
        address: "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8",
        decimals: 6,
        name: "PayPal USD",
      },
      EURC: {
        symbol: "EURC",
        address: "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c",
        decimals: 6,
        name: "Euro Coin",
      },
      AUSD: {
        symbol: "AUSD",
        address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
        decimals: 6,
        name: "Agora Dollar",
      },
    },
    nativeSymbol: "ETH",
    disperseAvailable: true,
    debridgeChainId: "1",
    squidSupported: true,
  },
  polygon: {
    name: "Polygon",
    chain: polygon,
    chainId: 137,
    rpcUrl: rpc("polygon", "https://polygon-bor-rpc.publicnode.com"),
    usdc: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        decimals: 6,
        name: "USD Coin",
      },
      AUSD: {
        symbol: "AUSD",
        address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
        decimals: 6,
        name: "Agora Dollar",
      },
    },
    nativeSymbol: "POL",
    disperseAvailable: true,
    debridgeChainId: "137",
    squidSupported: true,
  },
  arbitrum: {
    name: "Arbitrum",
    chain: arbitrum,
    chainId: 42161,
    rpcUrl: rpc("arbitrum", "https://arb1.arbitrum.io/rpc"),
    usdc: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        decimals: 6,
        name: "USD Coin",
      },
      USDT: {
        symbol: "USDT",
        address: "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        decimals: 6,
        name: "Tether USD",
      },
      AUSD: {
        symbol: "AUSD",
        address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
        decimals: 6,
        name: "Agora Dollar",
      },
    },
    nativeSymbol: "ETH",
    disperseAvailable: true,
    debridgeChainId: "42161",
    squidSupported: true,
  },
  avalanche: {
    name: "Avalanche",
    chain: avalanche,
    chainId: 43114,
    rpcUrl: rpc("avalanche", "https://api.avax.network/ext/bc/C/rpc"),
    usdc: "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        decimals: 6,
        name: "USD Coin",
      },
      EURC: {
        symbol: "EURC",
        address: "0xC891EB4cbdEFf6e073e859e987815Ed1505c2ACD",
        decimals: 6,
        name: "Euro Coin",
      },
      AUSD: {
        symbol: "AUSD",
        address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
        decimals: 6,
        name: "Agora Dollar",
      },
    },
    nativeSymbol: "AVAX",
    disperseAvailable: false, // Disperse.app NOT deployed at 0xD152...2150 on Avalanche C-Chain
    debridgeChainId: "43114",
    squidSupported: true,
  },
  optimism: {
    name: "Optimism",
    chain: optimism,
    chainId: 10,
    rpcUrl: rpc("optimism", "https://mainnet.optimism.io"),
    usdc: "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        decimals: 6,
        name: "USD Coin",
      },
      USDT: {
        symbol: "USDT",
        address: "0x01bff41798a0bcf287b996046ca68b395dbc1071",
        decimals: 6,
        name: "Tether USD",
      },
    },
    nativeSymbol: "ETH",
    disperseAvailable: true,
    debridgeChainId: "10",
    squidSupported: true,
  },
  celo: {
    name: "Celo",
    chain: celo,
    chainId: 42220,
    rpcUrl: rpc("celo", "https://forno.celo.org"),
    usdc: "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
        decimals: 6,
        name: "USDC",
      },
      USDT: {
        symbol: "USDT",
        address: "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e",
        decimals: 6,
        name: "Tether USD",
      },
    },
    nativeSymbol: "CELO",
    disperseAvailable: false,
    debridgeChainId: null,
    squidSupported: true,
  },
  monad: {
    name: "Monad",
    chain: monad,
    chainId: 143,
    rpcUrl: rpc("monad", "https://rpc.monad.xyz"),
    usdc: "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
    tokens: {
      USDC: {
        symbol: "USDC",
        address: "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
        decimals: 6,
        name: "USDC",
      },
      AUSD: {
        symbol: "AUSD",
        address: "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
        decimals: 6,
        name: "Agora Dollar",
      },
    },
    nativeSymbol: "MON",
    disperseAvailable: false,
    debridgeChainId: "100000030",
    squidSupported: false,
  },
};

/** Default gas amounts per agent per chain (enough for ~10-20 TXs) */
export const DEFAULT_GAS_AMOUNTS: Record<string, string> = {
  base: "0.0005",      // ~$1.60 in ETH
  ethereum: "0.001",   // ~$3.20 in ETH
  polygon: "0.1",      // ~$0.04 in POL
  arbitrum: "0.0005",  // ~$1.60 in ETH
  avalanche: "0.01",   // ~$0.25 in AVAX
  optimism: "0.0005",  // ~$1.60 in ETH
  celo: "0.01",        // ~$0.005 in CELO
  monad: "0.01",       // ~$0.01 in MON
};

/** Default stablecoin amount per agent per token per chain */
export const DEFAULT_TOKEN_AMOUNT = "1.00";

/** Get chain names sorted for consistent iteration */
export function getChainNames(): string[] {
  return Object.keys(CHAINS);
}

/** Get chain info or throw */
export function getChain(name: string): ChainInfo {
  const info = CHAINS[name];
  if (!info) throw new Error(`Unknown chain: ${name}. Valid: ${getChainNames().join(", ")}`);
  return info;
}

/** Get USDC address for a chain (backward-compat helper) */
export function getUsdc(chainName: string): Address {
  return getChain(chainName).usdc;
}

/** Get all token infos for a chain */
export function getTokens(chainName: string): TokenInfo[] {
  return Object.values(getChain(chainName).tokens);
}

/** Get specific token on a chain, or null if not available */
export function getToken(chainName: string, symbol: string): TokenInfo | null {
  return getChain(chainName).tokens[symbol] ?? null;
}

/** Get token symbols available on a chain */
export function getTokenSymbols(chainName: string): string[] {
  return Object.keys(getChain(chainName).tokens);
}

/** Get all unique stablecoin symbols across all chains */
export function getAllTokenSymbols(): string[] {
  const symbols = new Set<string>();
  for (const chain of Object.values(CHAINS)) {
    for (const symbol of Object.keys(chain.tokens)) {
      symbols.add(symbol);
    }
  }
  return Array.from(symbols).sort();
}
