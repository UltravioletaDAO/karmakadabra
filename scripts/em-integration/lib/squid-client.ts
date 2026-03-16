/**
 * Karma Kadabra V2 — Squid Router REST API Client
 *
 * Pure REST API — no @0xsquid/sdk needed.
 * Docs: https://docs.squidrouter.com/api-and-sdk-integration/api/
 *
 * Coverage: 7/8 chains (all except Monad).
 * Requires SQUID_INTEGRATOR_ID env var (free, apply at squidrouter.com).
 */

import type { Address } from "viem";

const SQUID_API = "https://v2.api.squidrouter.com/v2";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SquidQuote {
  route: {
    quoteId: string;
    estimate: {
      toAmount: string;
      toAmountMin: string;
      estimatedRouteDuration: number;
      feeCosts: Array<{ amount: string; name: string }>;
      gasCosts: Array<{ amount: string; token: { symbol: string } }>;
    };
    transactionRequest?: {
      target: string;
      data: string;
      value: string;
      gasLimit: string;
    };
  };
  requestId: string;
  integratorId: string;
}

export interface SquidStatus {
  squidTransactionStatus: string;
  fromChain?: { transactionId: string };
  toChain?: { transactionId: string };
  error?: string;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

function getIntegratorId(): string {
  const id = process.env.SQUID_INTEGRATOR_ID;
  if (!id) {
    throw new Error(
      "SQUID_INTEGRATOR_ID not set. Apply for free at https://docs.squidrouter.com/getting-started/integrator-quickstart",
    );
  }
  return id;
}

export async function getRoute(params: {
  fromChainId: string;
  toChainId: string;
  fromToken: Address;
  toToken: Address;
  fromAmount: string;
  fromAddress: Address;
  toAddress: Address;
  quoteOnly?: boolean;
}): Promise<SquidQuote> {
  const integratorId = getIntegratorId();

  const body = {
    fromChain: params.fromChainId,
    toChain: params.toChainId,
    fromToken: params.fromToken,
    toToken: params.toToken,
    fromAmount: params.fromAmount,
    fromAddress: params.fromAddress,
    toAddress: params.toAddress,
    slippage: 1,
    quoteOnly: params.quoteOnly ?? false,
  };

  const resp = await fetch(`${SQUID_API}/route`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-integrator-id": integratorId,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw new Error(`Squid API error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

export async function getStatus(params: {
  txHash: string;
  quoteId: string;
  requestId?: string;
}): Promise<SquidStatus> {
  const integratorId = getIntegratorId();

  const query = new URLSearchParams({
    transactionId: params.txHash,
    quoteId: params.quoteId,
  });
  if (params.requestId) query.set("requestId", params.requestId);

  const resp = await fetch(`${SQUID_API}/status?${query}`, {
    headers: { "x-integrator-id": integratorId },
  });

  if (!resp.ok) {
    throw new Error(`Squid status error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

/**
 * Wait for a Squid transaction to complete.
 */
export async function waitForTransaction(
  params: { txHash: string; quoteId: string; requestId?: string },
  timeoutMs: number = 300_000,
  pollMs: number = 10_000,
): Promise<SquidStatus> {
  const start = Date.now();
  // not_found is NOT terminal — Squid may take time to index the TX
  const terminal = new Set(["success", "partial_success", "needs_gas", "refund"]);

  while (Date.now() - start < timeoutMs) {
    try {
      const status = await getStatus(params);
      if (terminal.has(status.squidTransactionStatus)) return status;
    } catch (err: any) {
      if (err?.message?.includes("404")) {
        // Not indexed yet, keep polling
      } else {
        throw err;
      }
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }

  throw new Error(`Squid TX ${params.txHash} timed out after ${timeoutMs}ms`);
}
