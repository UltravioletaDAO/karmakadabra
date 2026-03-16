/**
 * Karma Kadabra V2 — deBridge DLN REST API Client
 *
 * Pure REST API — no SDK needed.
 * Docs: https://docs.debridge.com/api-reference/dln/
 *
 * Coverage: 7/8 chains (all except Celo).
 * Monad uses DLN chain ID 100000030 (not 143).
 */

import type { Address } from "viem";

const DLN_API = "https://dln.debridge.finance/v1.0";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DeBridgeQuote {
  orderId: string;
  estimation: {
    srcChainTokenIn: { amount: string; approximateUsdValue: number };
    srcChainTokenOut: { amount: string; approximateUsdValue: number };
    dstChainTokenOut: { amount: string; approximateUsdValue: number };
    recommendedSlippage: number;
  };
  tx?: {
    to: string;
    data: string;
    value: string;
  };
  protocolFee?: { amount: string };
  fixFee?: string;
  errorMessage?: string;
}

export interface DeBridgeStatus {
  orderId: string;
  status: "None" | "Created" | "Fulfilled" | "SentUnlock" | "ClaimedUnlock" | "Cancelled";
  srcChainTxHash?: string;
  dstChainTxHash?: string;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export async function getQuote(params: {
  srcChainId: string;
  srcToken: Address;
  dstChainId: string;
  dstToken: Address;
  amount: string;
  srcAddress?: Address;
  dstAddress?: Address;
}): Promise<DeBridgeQuote> {
  const query = new URLSearchParams({
    srcChainId: params.srcChainId,
    srcChainTokenIn: params.srcToken,
    srcChainTokenInAmount: params.amount,
    dstChainId: params.dstChainId,
    dstChainTokenOut: params.dstToken,
    dstChainTokenOutAmount: "auto",
    prependOperatingExpenses: "true",
  });

  if (params.srcAddress) {
    query.set("srcChainOrderAuthorityAddress", params.srcAddress);
  }
  if (params.dstAddress) {
    query.set("dstChainTokenOutRecipient", params.dstAddress);
    query.set("dstChainOrderAuthorityAddress", params.dstAddress);
  }

  const resp = await fetch(`${DLN_API}/dln/order/create-tx?${query}`);
  if (!resp.ok) {
    throw new Error(`deBridge API error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

export async function getOrderStatus(orderId: string): Promise<DeBridgeStatus> {
  const resp = await fetch(`${DLN_API}/dln/order/${orderId}/status`);
  if (!resp.ok) {
    throw new Error(`deBridge status error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

/**
 * Wait for an order to reach a terminal state.
 * Returns final status or throws on timeout.
 */
export async function waitForOrder(
  orderId: string,
  timeoutMs: number = 300_000,
  pollMs: number = 5_000,
): Promise<DeBridgeStatus> {
  const start = Date.now();
  const terminal = new Set(["Fulfilled", "ClaimedUnlock", "Cancelled"]);

  while (Date.now() - start < timeoutMs) {
    const status = await getOrderStatus(orderId);
    if (terminal.has(status.status)) return status;
    await new Promise((r) => setTimeout(r, pollMs));
  }

  throw new Error(`deBridge order ${orderId} timed out after ${timeoutMs}ms`);
}
