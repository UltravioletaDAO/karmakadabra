/**
 * Karma Kadabra V2 — EIP-8128 HTTP Request Signer
 *
 * Signs HTTP requests per ERC-8128 (Signed HTTP Requests with Ethereum),
 * producing 3 headers: Content-Digest, Signature, and Signature-Input.
 *
 * Compatible with the server-side verifier at:
 *   mcp_server/integrations/erc8128/verifier.py
 *
 * References:
 *   - ERC-8128: https://eip.tools/eip/8128
 *   - RFC 9421: https://www.rfc-editor.org/rfc/rfc9421 (HTTP Message Signatures)
 *   - RFC 9530: https://www.rfc-editor.org/rfc/rfc9530 (Content-Digest)
 *   - EIP-191:  https://eips.ethereum.org/EIPS/eip-191 (personal_sign)
 *
 * Usage:
 *   import { EIP8128Signer, createSignedFetch } from "./eip8128-signer";
 *
 *   const signer = new EIP8128Signer("0xprivatekey", 8453);
 *   const headers = await signer.signRequest(
 *     "POST",
 *     "https://api.execution.market/api/v1/tasks",
 *     JSON.stringify({ title: "test" }),
 *   );
 *   // headers = { "content-digest": "...", "signature": "...", "signature-input": "..." }
 *
 *   // Or use the fetch wrapper:
 *   const signedFetch = createSignedFetch("0xprivatekey", 8453);
 *   const res = await signedFetch("https://api.execution.market/api/v1/tasks", {
 *     method: "POST",
 *     body: JSON.stringify({ title: "test" }),
 *   });
 */

import { createHash, randomBytes } from "crypto";
import {
  type Hex,
  type Address,
} from "viem";
import { type PrivateKeyAccount, privateKeyToAccount } from "viem/accounts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default signature validity window in seconds */
const DEFAULT_VALIDITY_SEC = 300;

/** Signature label used in Signature / Signature-Input headers */
const SIGNATURE_LABEL = "eth";

/** API endpoint for server-issued nonces (canonical ERC-8128 path) */
const NONCE_ENDPOINT = "/api/v1/auth/erc8128/nonce";

/** HTTP methods that carry a request body */
const BODY_METHODS = new Set(["POST", "PUT", "PATCH"]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Parsed URL components needed for signature base construction */
interface UrlComponents {
  /** Host without protocol (e.g. "api.execution.market") */
  authority: string;
  /** Path without query (e.g. "/api/v1/tasks") */
  path: string;
  /** Full origin for nonce requests (e.g. "https://api.execution.market") */
  origin: string;
}

// ---------------------------------------------------------------------------
// EIP8128Signer
// ---------------------------------------------------------------------------

/**
 * Signs HTTP requests per ERC-8128 using an Ethereum private key.
 *
 * Produces RFC 9421-compliant HTTP Message Signature headers that the
 * server-side verifier (`mcp_server/integrations/erc8128/verifier.py`)
 * can validate via EIP-191 ecrecover.
 *
 * @example
 * ```ts
 * const signer = new EIP8128Signer("0xabc123...", 8453);
 * const headers = await signer.signRequest(
 *   "POST",
 *   "https://api.execution.market/api/v1/tasks",
 *   '{"title":"Buy coffee"}',
 * );
 * ```
 */
export class EIP8128Signer {
  private readonly account: PrivateKeyAccount;
  private readonly chainId: number;
  private readonly address: Address;

  /**
   * @param privateKey - Hex-encoded private key (with or without "0x" prefix)
   * @param chainId    - EVM chain ID (default: 8453 = Base Mainnet)
   */
  constructor(privateKey: string, chainId: number = 8453) {
    const key = (privateKey.startsWith("0x") ? privateKey : `0x${privateKey}`) as Hex;
    this.account = privateKeyToAccount(key);
    this.chainId = chainId;
    this.address = this.account.address;
  }

  /** The signer's Ethereum address (checksummed) */
  get signerAddress(): Address {
    return this.address;
  }

  /**
   * Sign an HTTP request and return the ERC-8128 headers.
   *
   * For POST/PUT/PATCH with a body, returns 3 headers:
   *   - `content-digest`  — SHA-256 of the body (RFC 9530)
   *   - `signature`       — Base64-encoded 65-byte secp256k1 signature
   *   - `signature-input` — RFC 9421 structured field with covered components
   *
   * For GET/DELETE (no body), returns 2 headers (no content-digest).
   *
   * @param method - HTTP method (GET, POST, PUT, PATCH, DELETE)
   * @param url    - Full URL (e.g. "https://api.execution.market/api/v1/tasks")
   * @param body   - Request body string (required for POST/PUT/PATCH)
   * @returns Record of lowercase header names to their values
   */
  async signRequest(
    method: string,
    url: string,
    body?: string,
  ): Promise<Record<string, string>> {
    const upperMethod = method.toUpperCase();
    const { authority, path, origin } = EIP8128Signer.parseUrl(url);
    const hasBody = BODY_METHODS.has(upperMethod) && body != null && body.length > 0;

    // 1. Build Content-Digest if we have a body
    let contentDigest: string | null = null;
    if (hasBody) {
      contentDigest = computeContentDigest(body!);
    }

    // 2. Fetch nonce from server (with local fallback)
    const { nonce, ttlSeconds } = await this.fetchNonce(origin);

    // 3. Compute timestamps
    const now = Math.floor(Date.now() / 1000);
    const created = now;
    const expires = now + ttlSeconds;

    // 4. Build the keyid
    const keyid = `erc8128:${this.chainId}:${this.address.toLowerCase()}`;

    // 5. Determine covered components
    //    For body-bearing methods: include content-digest
    //    For GET/DELETE: omit content-digest
    const coveredComponents = hasBody
      ? ["@method", "@authority", "@path", "content-digest"]
      : ["@method", "@authority", "@path"];

    // 6. Build signature params string (matches verifier's _build_signature_params)
    //    Order: created, expires, nonce, keyid (then any extras sorted)
    const sigParams = buildSignatureParams(coveredComponents, {
      created,
      expires,
      nonce,
      keyid,
    });

    // 7. Build signature base (RFC 9421 Section 2.5)
    const sigBase = buildSignatureBase(
      coveredComponents,
      {
        "@method": upperMethod,
        "@authority": authority,
        "@path": path,
        "content-digest": contentDigest ?? "",
      },
      sigParams,
    );

    // 8. Sign with EIP-191 personal_sign
    const signatureBytes = await this.eip191Sign(sigBase);

    // 9. Encode signature as base64
    const signatureB64 = Buffer.from(signatureBytes).toString("base64");

    // 10. Assemble headers
    const headers: Record<string, string> = {};

    if (contentDigest) {
      headers["content-digest"] = contentDigest;
    }

    // Signature header: eth=:base64:
    headers["signature"] = `${SIGNATURE_LABEL}=:${signatureB64}:`;

    // Signature-Input header: eth=<sig-params>
    headers["signature-input"] = `${SIGNATURE_LABEL}=${sigParams}`;

    return headers;
  }

  /**
   * Fetch a nonce from the server's nonce endpoint.
   * Falls back to a locally-generated random nonce if the endpoint is unavailable.
   *
   * @param origin - Server origin (e.g. "https://api.execution.market")
   * @returns Object with nonce string and TTL in seconds
   */
  async fetchNonce(origin: string): Promise<{ nonce: string; ttlSeconds: number }> {
    const nonceUrl = `${origin}${NONCE_ENDPOINT}`;

    try {
      const response = await fetch(nonceUrl, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(5000),
      });

      if (response.ok) {
        const data = (await response.json()) as { nonce?: string; ttl_seconds?: number };
        if (data.nonce) {
          return {
            nonce: data.nonce,
            ttlSeconds: data.ttl_seconds ?? DEFAULT_VALIDITY_SEC,
          };
        }
      }

      // Non-200 or missing nonce field — fall through to local generation
    } catch {
      // Network error, timeout, or 404 — fall through to local generation
    }

    // Fallback: generate a local nonce (16 random bytes, hex-encoded)
    return {
      nonce: randomBytes(16).toString("hex"),
      ttlSeconds: DEFAULT_VALIDITY_SEC,
    };
  }

  /**
   * Parse a full URL into authority and path components.
   *
   * @param url - Full URL string (e.g. "https://api.execution.market/api/v1/tasks")
   * @returns Object with authority, path, and origin
   *
   * @example
   * ```ts
   * EIP8128Signer.parseUrl("https://api.execution.market/api/v1/tasks")
   * // { authority: "api.execution.market", path: "/api/v1/tasks", origin: "https://api.execution.market" }
   * ```
   */
  static parseUrl(url: string): UrlComponents {
    const parsed = new URL(url);

    // Authority = host (includes port only if non-standard)
    // URL.host already includes port if non-standard, which matches RFC 9421
    const authority = parsed.host;

    // Path = pathname (e.g. "/api/v1/tasks")
    const path = parsed.pathname || "/";

    // Origin = scheme + host
    const origin = parsed.origin;

    return { authority, path, origin };
  }

  /**
   * Sign a message using EIP-191 personal_sign.
   *
   * Applies the prefix: `\x19Ethereum Signed Message:\n` + length + message
   * then signs with secp256k1 via viem.
   *
   * @param message - The signature base string to sign
   * @returns 65-byte signature (r[32] + s[32] + v[1])
   */
  private async eip191Sign(message: string): Promise<Uint8Array> {
    // viem's signMessage applies EIP-191 prefix internally
    const signature = await this.account.signMessage({ message });

    // Convert hex signature to bytes (remove "0x" prefix)
    return hexToBytes(signature);
  }
}

// ---------------------------------------------------------------------------
// Signature Base Construction (RFC 9421)
// ---------------------------------------------------------------------------

/**
 * Build the RFC 9421 signature base string.
 *
 * Format (lines joined with "\n", no trailing newline):
 * ```
 * "@method": POST
 * "@authority": api.execution.market
 * "@path": /api/v1/tasks
 * "content-digest": sha-256=:X48E...=:
 * "@signature-params": ("@method" "@authority" "@path" "content-digest");created=...;keyid="..."
 * ```
 *
 * Must exactly match the verifier's `_build_signature_base()` output.
 */
function buildSignatureBase(
  coveredComponents: string[],
  componentValues: Record<string, string>,
  sigParams: string,
): string {
  const lines: string[] = [];

  for (const component of coveredComponents) {
    const value = componentValues[component] ?? "";
    lines.push(`"${component}": ${value}`);
  }

  lines.push(`"@signature-params": ${sigParams}`);

  return lines.join("\n");
}

/**
 * Build the @signature-params value for the Signature-Input header.
 *
 * Matches the verifier's `_build_signature_params()`:
 *   - Components in parentheses: ("@method" "@authority" ...)
 *   - Parameters in fixed order: created, expires, nonce, keyid
 *   - Integer values are bare, string values are quoted
 *   - Joined with semicolons
 *
 * @example
 * ```
 * ("@method" "@authority" "@path" "content-digest");created=1700000000;expires=1700000300;nonce="abc123";keyid="erc8128:8453:0x857f..."
 * ```
 */
function buildSignatureParams(
  coveredComponents: string[],
  params: { created: number; expires: number; nonce: string; keyid: string },
): string {
  const compStr = coveredComponents.map((c) => `"${c}"`).join(" ");
  const parts = [`(${compStr})`];

  // Fixed order matching the verifier: created, expires, nonce, keyid
  parts.push(`created=${params.created}`);
  parts.push(`expires=${params.expires}`);
  parts.push(`nonce="${params.nonce}"`);
  parts.push(`keyid="${params.keyid}"`);

  return parts.join(";");
}

// ---------------------------------------------------------------------------
// Content-Digest (RFC 9530)
// ---------------------------------------------------------------------------

/**
 * Compute the Content-Digest header value for a request body.
 *
 * Format: `sha-256=:base64(sha256(body)):`
 *
 * @param body - The request body as a UTF-8 string
 * @returns Content-Digest header value
 */
function computeContentDigest(body: string): string {
  const hash = createHash("sha256").update(body, "utf8").digest("base64");
  return `sha-256=:${hash}:`;
}

// ---------------------------------------------------------------------------
// Hex / Byte utilities
// ---------------------------------------------------------------------------

/**
 * Convert a hex string (with "0x" prefix) to a Uint8Array.
 *
 * @param hex - Hex string like "0xabcdef..."
 * @returns Uint8Array of raw bytes
 */
function hexToBytes(hex: string): Uint8Array {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(clean.substring(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// Signed Fetch Wrapper
// ---------------------------------------------------------------------------

/** Options for the signed fetch helper (extends standard RequestInit) */
interface SignedFetchOptions extends RequestInit {
  /** Override the body for signing (if body is a non-string type) */
  bodyString?: string;
}

/**
 * Create a fetch wrapper that automatically signs requests with ERC-8128 headers.
 *
 * The returned function has the same signature as `fetch()` but injects
 * Content-Digest, Signature, and Signature-Input headers into every request.
 *
 * @param privateKey - Hex-encoded private key
 * @param chainId    - EVM chain ID (default: 8453 = Base)
 * @returns An async function with the same interface as `fetch()`
 *
 * @example
 * ```ts
 * const signedFetch = createSignedFetch("0xprivatekey", 8453);
 *
 * // POST with body — 3 ERC-8128 headers added
 * const res = await signedFetch("https://api.execution.market/api/v1/tasks", {
 *   method: "POST",
 *   headers: { "Content-Type": "application/json" },
 *   body: JSON.stringify({ title: "Buy coffee", bounty_usdc: "0.10" }),
 * });
 *
 * // GET — 2 ERC-8128 headers added (no content-digest)
 * const tasks = await signedFetch("https://api.execution.market/api/v1/tasks");
 * ```
 */
export function createSignedFetch(
  privateKey: string,
  chainId: number = 8453,
): (url: string, init?: SignedFetchOptions) => Promise<Response> {
  const signer = new EIP8128Signer(privateKey, chainId);

  return async (url: string, init?: SignedFetchOptions): Promise<Response> => {
    const method = (init?.method ?? "GET").toUpperCase();

    // Resolve the body string for signing
    let bodyString: string | undefined = init?.bodyString;
    if (bodyString == null && init?.body != null) {
      if (typeof init.body === "string") {
        bodyString = init.body;
      } else {
        // For non-string bodies (ArrayBuffer, ReadableStream, etc.),
        // caller should provide bodyString explicitly
        throw new Error(
          "EIP-8128 signed fetch requires a string body. " +
            "Pass the body as a string or use the bodyString option.",
        );
      }
    }

    // Sign the request
    const sigHeaders = await signer.signRequest(method, url, bodyString);

    // Merge signature headers with any existing headers
    const existingHeaders = new Headers(init?.headers as HeadersInit | undefined);
    for (const [key, value] of Object.entries(sigHeaders)) {
      existingHeaders.set(key, value);
    }

    // Execute the fetch with merged headers
    return fetch(url, {
      ...init,
      method,
      headers: existingHeaders,
    });
  };
}
