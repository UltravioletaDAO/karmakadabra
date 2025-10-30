# RPC Endpoint Resilience Master Plan

**Project**: x402 Facilitator Frontend RPC Resilience
**Owner**: Karmacadabra Core Team
**Status**: Draft
**Created**: 2025-10-30
**Target Completion**: TBD

---

## Executive Summary

### Objective
Implement enterprise-grade RPC endpoint resilience for the x402 facilitator frontend, enabling:
1. Private QuickNode RPC endpoints stored in AWS Secrets Manager
2. Automatic failover to public RPCs if private endpoints fail
3. Zero frontend exposure of private credentials
4. Seamless migration path with zero downtime

### Current State
- **Frontend**: Hardcoded public RPC endpoints in `x402-rs/static/index.html` (lines 1196-1247)
- **Backend**: Provider cache system (`provider_cache.rs`) loads RPCs from environment variables
- **Networks**: 7 mainnets + 7 testnets (Avalanche, Base, Celo, HyperEVM, Polygon, Solana, Optimism)
- **Architecture**: Static HTML frontend + Rust Axum backend + AWS Secrets Manager

### Proposed Architecture
```
Frontend (JavaScript)
    |
    | GET /api/rpc-config?network=avalanche-mainnet
    v
Backend (Rust Axum)
    |
    | Load from AWS Secrets Manager (with caching)
    v
AWS Secrets Manager
    |
    | Secrets: karmacadabra-rpc-endpoints
    v
Return: { primary: "https://quicknode...", fallback: "https://publicnode..." }
    |
    | If primary fails (timeout/error)
    v
Frontend Failover to fallback RPC
```

### Success Criteria
- Frontend can fetch balances even if AWS Secrets Manager is unavailable (fallback to public RPCs)
- Zero downtime when switching from public to private RPCs
- Secrets update without backend redeployment (or minimal restart with health check)
- Clear monitoring/logging for RPC failovers
- All 7 mainnets + 7 testnets supported

### Cost Impact
- AWS Secrets Manager: $0.40/month per secret + $0.05 per 10,000 API calls
- Estimated: ~$1-2/month for RPC config secret with caching
- No impact on current $81-96/month ECS Fargate cost

---

## Phase 1: AWS Secrets Manager Structure

### 1.1 Secret Schema Design

**Decision: Single Secret with All RPCs**

Rationale:
- Simpler access control (one secret ARN)
- Atomic updates (all networks updated together)
- Easier to audit and rotate
- Matches existing pattern (`karmacadabra-facilitator-testnet` already exists)

**Secret Name**: `karmacadabra-rpc-endpoints`

**JSON Structure**:
```json
{
  "version": "1.0",
  "last_updated": "2025-10-30T12:00:00Z",
  "networks": {
    "avalanche-mainnet": {
      "primary": "https://avalanche-c-chain-rpc.publicnode.com",
      "fallback": "https://api.avax.network/ext/bc/C/rpc"
    },
    "base-mainnet": {
      "primary": "https://mainnet.base.org",
      "fallback": "https://base.gateway.tenderly.co"
    },
    "celo-mainnet": {
      "primary": "https://rpc.celocolombia.org",
      "fallback": "https://rpc.ankr.com/celo"
    },
    "hyperevm-mainnet": {
      "primary": "https://rpc.hyperliquid.xyz/evm",
      "fallback": "https://rpc.hyperliquid.xyz/evm"
    },
    "polygon-mainnet": {
      "primary": "https://polygon.drpc.org",
      "fallback": "https://polygon-rpc.com"
    },
    "solana-mainnet": {
      "primary": "https://mainnet.helius-rpc.com/?api-key=f6fc10fb-cd9d-42e4-be78-900dde381d4a",
      "fallback": "https://api.mainnet-beta.solana.com"
    },
    "optimism-mainnet": {
      "primary": "https://mainnet.optimism.io",
      "fallback": "https://public-op-mainnet.fastnode.io"
    },
    "avalanche-fuji": {
      "primary": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
      "fallback": "https://api.avax-test.network/ext/bc/C/rpc"
    },
    "base-sepolia": {
      "primary": "https://sepolia.base.org",
      "fallback": "https://base-sepolia.gateway.tenderly.co"
    },
    "celo-sepolia": {
      "primary": "https://rpc.ankr.com/celo_sepolia",
      "fallback": "https://alfajores-forno.celo-testnet.org"
    },
    "polygon-amoy": {
      "primary": "https://rpc-amoy.polygon.technology",
      "fallback": "https://polygon-amoy.drpc.org"
    },
    "optimism-sepolia": {
      "primary": "https://sepolia.optimism.io",
      "fallback": "https://optimism-sepolia.gateway.tenderly.co"
    }
  }
}
```

**Notes**:
- `primary`: Private QuickNode RPC (user replaces after Phase 1 deployment)
- `fallback`: Public RPC (always available, rate-limited)
- `version`: For future schema changes
- `last_updated`: Audit trail

### 1.2 IAM Permissions

**Task 1.2.1: Update ECS Task Execution Role**

File: `terraform/ecs-fargate/iam.tf` (create if doesn't exist, or add to main.tf)

```hcl
# Add to existing ecs_task_execution role policy
resource "aws_iam_role_policy" "ecs_rpc_secrets_access" {
  name = "rpc-secrets-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:karmacadabra-rpc-endpoints-*"
        ]
      }
    ]
  })
}
```

**Task 1.2.2: Create Secret in AWS**

```bash
# Run from repository root
cd terraform/ecs-fargate

# Create initial secret with public RPCs (Option 4 per user requirement)
aws secretsmanager create-secret \
  --name karmacadabra-rpc-endpoints \
  --description "RPC endpoints for x402 facilitator frontend (primary + fallback)" \
  --secret-string file://../../x402-rs/rpc-endpoints-initial.json \
  --region us-east-1 \
  --tags Key=Project,Value=Karmacadabra Key=Environment,Value=Production
```

**Task 1.2.3: Create Initial RPC Config File**

File: `x402-rs/rpc-endpoints-initial.json` (gitignored)

```json
{
  "version": "1.0",
  "last_updated": "2025-10-30T12:00:00Z",
  "networks": {
    "avalanche-mainnet": {
      "primary": "https://avalanche-c-chain-rpc.publicnode.com",
      "fallback": "https://api.avax.network/ext/bc/C/rpc"
    },
    "base-mainnet": {
      "primary": "https://mainnet.base.org",
      "fallback": "https://base.gateway.tenderly.co"
    },
    "celo-mainnet": {
      "primary": "https://rpc.celocolombia.org",
      "fallback": "https://rpc.ankr.com/celo"
    },
    "hyperevm-mainnet": {
      "primary": "https://rpc.hyperliquid.xyz/evm",
      "fallback": "https://rpc.hyperliquid.xyz/evm"
    },
    "polygon-mainnet": {
      "primary": "https://polygon.drpc.org",
      "fallback": "https://polygon-rpc.com"
    },
    "solana-mainnet": {
      "primary": "https://mainnet.helius-rpc.com/?api-key=f6fc10fb-cd9d-42e4-be78-900dde381d4a",
      "fallback": "https://api.mainnet-beta.solana.com"
    },
    "optimism-mainnet": {
      "primary": "https://mainnet.optimism.io",
      "fallback": "https://public-op-mainnet.fastnode.io"
    },
    "avalanche-fuji": {
      "primary": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
      "fallback": "https://api.avax-test.network/ext/bc/C/rpc"
    },
    "base-sepolia": {
      "primary": "https://sepolia.base.org",
      "fallback": "https://base-sepolia.gateway.tenderly.co"
    },
    "celo-sepolia": {
      "primary": "https://rpc.ankr.com/celo_sepolia",
      "fallback": "https://alfajores-forno.celo-testnet.org"
    },
    "polygon-amoy": {
      "primary": "https://rpc-amoy.polygon.technology",
      "fallback": "https://polygon-amoy.drpc.org"
    },
    "optimism-sepolia": {
      "primary": "https://sepolia.optimism.io",
      "fallback": "https://optimism-sepolia.gateway.tenderly.co"
    }
  }
}
```

### 1.3 Add to .gitignore

File: `x402-rs/.gitignore` (append)

```
# RPC endpoint configuration (may contain private URLs)
rpc-endpoints-initial.json
rpc-endpoints-*.json
```

### Phase 1 Checklist

- [ ] Create `x402-rs/rpc-endpoints-initial.json` with current public RPCs
- [ ] Create AWS secret: `karmacadabra-rpc-endpoints`
- [ ] Update Terraform IAM policy for secret access
- [ ] Apply Terraform changes: `terraform apply`
- [ ] Verify secret access from ECS task (test with AWS CLI in container)
- [ ] Document migration path for user to replace with QuickNode URLs

**Testing Phase 1**:
```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --region us-east-1

# Test retrieval
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-rpc-endpoints \
  --region us-east-1 | jq -r '.SecretString | fromjson'
```

**Estimated Time**: 2-3 hours

---

## Phase 2: Backend API for RPC Endpoints

### 2.1 Architecture Decisions

**Decision: Backend Proxy Approach**

Rationale:
- Frontend cannot directly access AWS Secrets Manager (no AWS credentials in browser)
- Backend already has IAM role with secret access
- Allows caching to avoid AWS API rate limits
- Enables future features (rate limiting, RPC health checks)

**Caching Strategy**:
- In-memory cache with TTL (5 minutes)
- Refresh on cache miss or TTL expiry
- Background refresh every 5 minutes to keep cache warm
- Emergency fallback: Hardcoded public RPCs if AWS fails

### 2.2 Add AWS SDK to Rust Backend

**Task 2.2.1: Update Cargo.toml**

File: `x402-rs/Cargo.toml`

Add after line 49 (OpenTelemetry dependencies):

```toml
# AWS Secrets Manager
aws-config = { version = "1.5.5", features = ["behavior-version-latest"] }
aws-sdk-secretsmanager = { version = "1.47.0" }
```

### 2.3 Create RPC Configuration Module

**Task 2.3.1: Create `x402-rs/src/rpc_config.rs`**

File: `x402-rs/src/rpc_config.rs`

```rust
//! RPC endpoint configuration from AWS Secrets Manager with failover support.
//!
//! This module loads RPC endpoints from AWS Secrets Manager and provides
//! automatic failover to public RPCs if private endpoints fail.
//!
//! Caching strategy:
//! - In-memory cache with 5-minute TTL
//! - Background refresh every 5 minutes
//! - Fallback to hardcoded public RPCs if AWS is unavailable

use aws_config::BehaviorVersion;
use aws_sdk_secretsmanager::Client as SecretsManagerClient;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{Duration, Instant};

const SECRET_NAME: &str = "karmacadabra-rpc-endpoints";
const CACHE_TTL: Duration = Duration::from_secs(300); // 5 minutes

/// RPC endpoint configuration for a single network
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcEndpoints {
    /// Primary RPC endpoint (private QuickNode or similar)
    pub primary: String,
    /// Fallback RPC endpoint (public, always available)
    pub fallback: String,
}

/// Complete RPC configuration from AWS Secrets Manager
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcConfig {
    pub version: String,
    pub last_updated: String,
    pub networks: std::collections::HashMap<String, RpcEndpoints>,
}

/// Cached entry with expiry timestamp
struct CachedConfig {
    config: Arc<RpcConfig>,
    expires_at: Instant,
}

/// RPC configuration manager with caching
pub struct RpcConfigManager {
    secrets_client: SecretsManagerClient,
    cache: Arc<DashMap<String, CachedConfig>>,
    fallback_config: Arc<RpcConfig>,
}

impl RpcConfigManager {
    /// Create a new RPC configuration manager
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let aws_config = aws_config::load_defaults(BehaviorVersion::latest()).await;
        let secrets_client = SecretsManagerClient::new(&aws_config);

        let fallback_config = Arc::new(Self::hardcoded_fallback_config());

        Ok(Self {
            secrets_client,
            cache: Arc::new(DashMap::new()),
            fallback_config,
        })
    }

    /// Get RPC endpoints for a specific network
    pub async fn get_endpoints(&self, network: &str) -> RpcEndpoints {
        let config = self.get_config().await;

        config
            .networks
            .get(network)
            .cloned()
            .unwrap_or_else(|| {
                tracing::warn!("Network {} not found in RPC config, using fallback", network);
                self.fallback_config
                    .networks
                    .get(network)
                    .cloned()
                    .unwrap_or_else(|| RpcEndpoints {
                        primary: "".to_string(),
                        fallback: "".to_string(),
                    })
            })
    }

    /// Get full RPC configuration (with caching)
    async fn get_config(&self) -> Arc<RpcConfig> {
        const CACHE_KEY: &str = "global";

        // Check cache
        if let Some(cached) = self.cache.get(CACHE_KEY) {
            if Instant::now() < cached.expires_at {
                tracing::debug!("RPC config cache hit");
                return cached.config.clone();
            } else {
                tracing::debug!("RPC config cache expired");
            }
        }

        // Fetch from AWS Secrets Manager
        match self.fetch_from_aws().await {
            Ok(config) => {
                let config = Arc::new(config);
                self.cache.insert(
                    CACHE_KEY.to_string(),
                    CachedConfig {
                        config: config.clone(),
                        expires_at: Instant::now() + CACHE_TTL,
                    },
                );
                tracing::info!("RPC config loaded from AWS Secrets Manager");
                config
            }
            Err(e) => {
                tracing::error!("Failed to load RPC config from AWS: {}", e);
                tracing::warn!("Using hardcoded fallback RPC config");
                self.fallback_config.clone()
            }
        }
    }

    /// Fetch RPC configuration from AWS Secrets Manager
    async fn fetch_from_aws(&self) -> Result<RpcConfig, Box<dyn std::error::Error>> {
        let response = self
            .secrets_client
            .get_secret_value()
            .secret_id(SECRET_NAME)
            .send()
            .await?;

        let secret_string = response
            .secret_string()
            .ok_or("Secret string is empty")?;

        let config: RpcConfig = serde_json::from_str(secret_string)?;
        Ok(config)
    }

    /// Hardcoded fallback configuration (current public RPCs)
    fn hardcoded_fallback_config() -> RpcConfig {
        RpcConfig {
            version: "1.0".to_string(),
            last_updated: "2025-10-30T00:00:00Z".to_string(),
            networks: [
                (
                    "avalanche-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://avalanche-c-chain-rpc.publicnode.com".to_string(),
                        fallback: "https://api.avax.network/ext/bc/C/rpc".to_string(),
                    },
                ),
                (
                    "base-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://mainnet.base.org".to_string(),
                        fallback: "https://base.gateway.tenderly.co".to_string(),
                    },
                ),
                (
                    "celo-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://rpc.celocolombia.org".to_string(),
                        fallback: "https://rpc.ankr.com/celo".to_string(),
                    },
                ),
                (
                    "hyperevm-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://rpc.hyperliquid.xyz/evm".to_string(),
                        fallback: "https://rpc.hyperliquid.xyz/evm".to_string(),
                    },
                ),
                (
                    "polygon-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://polygon.drpc.org".to_string(),
                        fallback: "https://polygon-rpc.com".to_string(),
                    },
                ),
                (
                    "solana-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://mainnet.helius-rpc.com/?api-key=f6fc10fb-cd9d-42e4-be78-900dde381d4a".to_string(),
                        fallback: "https://api.mainnet-beta.solana.com".to_string(),
                    },
                ),
                (
                    "optimism-mainnet".to_string(),
                    RpcEndpoints {
                        primary: "https://mainnet.optimism.io".to_string(),
                        fallback: "https://public-op-mainnet.fastnode.io".to_string(),
                    },
                ),
                (
                    "avalanche-fuji".to_string(),
                    RpcEndpoints {
                        primary: "https://avalanche-fuji-c-chain-rpc.publicnode.com".to_string(),
                        fallback: "https://api.avax-test.network/ext/bc/C/rpc".to_string(),
                    },
                ),
                (
                    "base-sepolia".to_string(),
                    RpcEndpoints {
                        primary: "https://sepolia.base.org".to_string(),
                        fallback: "https://base-sepolia.gateway.tenderly.co".to_string(),
                    },
                ),
                (
                    "celo-sepolia".to_string(),
                    RpcEndpoints {
                        primary: "https://rpc.ankr.com/celo_sepolia".to_string(),
                        fallback: "https://alfajores-forno.celo-testnet.org".to_string(),
                    },
                ),
                (
                    "polygon-amoy".to_string(),
                    RpcEndpoints {
                        primary: "https://rpc-amoy.polygon.technology".to_string(),
                        fallback: "https://polygon-amoy.drpc.org".to_string(),
                    },
                ),
                (
                    "optimism-sepolia".to_string(),
                    RpcEndpoints {
                        primary: "https://sepolia.optimism.io".to_string(),
                        fallback: "https://optimism-sepolia.gateway.tenderly.co".to_string(),
                    },
                ),
            ]
            .into_iter()
            .collect(),
        }
    }

    /// Invalidate cache (for testing or manual refresh)
    pub fn invalidate_cache(&self) {
        self.cache.clear();
        tracing::info!("RPC config cache invalidated");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardcoded_fallback_config() {
        let config = RpcConfigManager::hardcoded_fallback_config();
        assert_eq!(config.version, "1.0");
        assert!(config.networks.contains_key("avalanche-mainnet"));
        assert!(config.networks.contains_key("base-mainnet"));

        let avalanche = config.networks.get("avalanche-mainnet").unwrap();
        assert!(!avalanche.primary.is_empty());
        assert!(!avalanche.fallback.is_empty());
    }

    #[tokio::test]
    async fn test_get_endpoints_fallback() {
        // This test doesn't require AWS credentials
        let manager = RpcConfigManager::new().await.unwrap();
        let endpoints = manager.get_endpoints("avalanche-mainnet").await;
        assert!(!endpoints.primary.is_empty());
        assert!(!endpoints.fallback.is_empty());
    }
}
```

### 2.4 Create API Handler

**Task 2.4.1: Create `x402-rs/src/handlers/rpc_config.rs`**

File: `x402-rs/src/handlers/rpc_config.rs`

```rust
//! HTTP handlers for RPC configuration endpoints

use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Json};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::rpc_config::{RpcConfigManager, RpcEndpoints};

/// Query parameters for RPC config endpoint
#[derive(Debug, Deserialize)]
pub struct RpcConfigQuery {
    /// Network name (e.g., "avalanche-mainnet", "base-sepolia")
    pub network: Option<String>,
}

/// Response for RPC config endpoint
#[derive(Debug, Serialize)]
pub struct RpcConfigResponse {
    /// Network name
    pub network: String,
    /// Primary RPC endpoint
    pub primary: String,
    /// Fallback RPC endpoint
    pub fallback: String,
}

/// GET /api/rpc-config?network={network}
///
/// Returns RPC endpoints for a specific network.
/// If no network is specified, returns all networks.
pub async fn get_rpc_config(
    State(rpc_manager): State<Arc<RpcConfigManager>>,
    Query(params): Query<RpcConfigQuery>,
) -> impl IntoResponse {
    if let Some(network) = params.network {
        // Return single network
        let endpoints = rpc_manager.get_endpoints(&network).await;

        let response = RpcConfigResponse {
            network: network.clone(),
            primary: endpoints.primary,
            fallback: endpoints.fallback,
        };

        (StatusCode::OK, Json(response)).into_response()
    } else {
        // Return all networks
        let networks = vec![
            "avalanche-mainnet",
            "base-mainnet",
            "celo-mainnet",
            "hyperevm-mainnet",
            "polygon-mainnet",
            "solana-mainnet",
            "optimism-mainnet",
            "avalanche-fuji",
            "base-sepolia",
            "celo-sepolia",
            "polygon-amoy",
            "optimism-sepolia",
        ];

        let mut responses = Vec::new();
        for network in networks {
            let endpoints = rpc_manager.get_endpoints(network).await;
            responses.push(RpcConfigResponse {
                network: network.to_string(),
                primary: endpoints.primary,
                fallback: endpoints.fallback,
            });
        }

        (StatusCode::OK, Json(responses)).into_response()
    }
}

/// POST /api/rpc-config/invalidate-cache
///
/// Invalidate RPC config cache (admin endpoint, for testing)
pub async fn invalidate_rpc_cache(
    State(rpc_manager): State<Arc<RpcConfigManager>>,
) -> impl IntoResponse {
    rpc_manager.invalidate_cache();
    (StatusCode::OK, Json(serde_json::json!({
        "message": "RPC config cache invalidated"
    }))).into_response()
}
```

### 2.5 Update Main Application

**Task 2.5.1: Modify `x402-rs/src/main.rs`**

Add after line 46 (after existing mod declarations):

```rust
mod rpc_config;
```

Add after line 65 (after telemetry registration):

```rust
    let rpc_config_manager = match rpc_config::RpcConfigManager::new().await {
        Ok(manager) => Arc::new(manager),
        Err(e) => {
            tracing::warn!("Failed to initialize RPC config manager: {}", e);
            tracing::warn!("Frontend will use hardcoded fallback RPCs");
            Arc::new(rpc_config::RpcConfigManager::new().await.unwrap()) // Always succeeds with fallback
        }
    };
```

Add after line 91 (after /health route):

```rust
        .route("/api/rpc-config", get(handlers::rpc_config::get_rpc_config))
        .route("/api/rpc-config/invalidate-cache", post(handlers::rpc_config::invalidate_rpc_cache))
```

Add before `.with_state(facilitator)` (line 92):

```rust
        .with_state(rpc_config_manager.clone())
```

**Note**: This requires converting the app to support multiple states. We'll use Axum's layered state approach.

**Updated State Structure**:

```rust
#[derive(Clone)]
pub struct AppState {
    pub facilitator: FacilitatorLocal,
    pub rpc_config_manager: Arc<RpcConfigManager>,
}
```

### 2.6 Update Handlers Module

**Task 2.6.1: Modify `x402-rs/src/handlers.rs`** (add at end)

```rust
pub mod rpc_config;
```

### Phase 2 Checklist

- [ ] Update `Cargo.toml` with AWS SDK dependencies
- [ ] Create `x402-rs/src/rpc_config.rs` module
- [ ] Create `x402-rs/src/handlers/rpc_config.rs` handler
- [ ] Update `x402-rs/src/main.rs` to initialize RPC config manager
- [ ] Add `/api/rpc-config` and `/api/rpc-config/invalidate-cache` routes
- [ ] Build and test locally: `cargo build && cargo run`
- [ ] Test endpoints:
  - `curl http://localhost:8080/api/rpc-config?network=avalanche-mainnet`
  - `curl http://localhost:8080/api/rpc-config` (all networks)
  - `curl -X POST http://localhost:8080/api/rpc-config/invalidate-cache`

**Testing Phase 2**:
```bash
cd x402-rs

# Build
cargo build

# Run locally
cargo run

# Test single network
curl http://localhost:8080/api/rpc-config?network=avalanche-mainnet | jq

# Test all networks
curl http://localhost:8080/api/rpc-config | jq

# Test cache invalidation
curl -X POST http://localhost:8080/api/rpc-config/invalidate-cache | jq
```

**Expected Output**:
```json
{
  "network": "avalanche-mainnet",
  "primary": "https://avalanche-c-chain-rpc.publicnode.com",
  "fallback": "https://api.avax.network/ext/bc/C/rpc"
}
```

**Estimated Time**: 4-6 hours

---

## Phase 3: Frontend Failover Logic

### 3.1 Architecture Overview

**Current Frontend Flow** (lines 1190-1312 in index.html):
```javascript
fetchWalletBalances()
  → Hardcoded RPC URLs
  → fetch(rpc, { method: 'POST', body: eth_getBalance })
  → Update UI
```

**New Frontend Flow**:
```javascript
fetchWalletBalances()
  → fetchRpcConfig(network)
    → GET /api/rpc-config?network=avalanche-mainnet
    → Cache in localStorage (5 min TTL)
  → tryFetchBalance(primary_rpc)
    → If fails → tryFetchBalance(fallback_rpc)
    → If both fail → Show error
  → Update UI + show RPC status indicator
```

### 3.2 Create RPC Config Client Library

**Task 3.2.1: Add to `x402-rs/static/index.html`** (before fetchWalletBalances function, line 1190)

```javascript
        // ============================================================================
        // RPC Configuration Management
        // ============================================================================

        /**
         * RPC configuration cache with TTL
         */
        class RpcConfigCache {
            constructor(ttlMinutes = 5) {
                this.ttl = ttlMinutes * 60 * 1000; // Convert to milliseconds
                this.storageKey = 'rpc_config_cache';
            }

            /**
             * Get cached RPC config for a network
             * @param {string} network - Network name (e.g., "avalanche-mainnet")
             * @returns {Object|null} - { primary, fallback } or null if cache miss
             */
            get(network) {
                try {
                    const cached = localStorage.getItem(this.storageKey);
                    if (!cached) return null;

                    const data = JSON.parse(cached);
                    const entry = data[network];

                    if (!entry) return null;

                    // Check if expired
                    const now = Date.now();
                    if (now > entry.expires_at) {
                        console.log(`RPC config cache expired for ${network}`);
                        return null;
                    }

                    console.log(`RPC config cache hit for ${network}`);
                    return { primary: entry.primary, fallback: entry.fallback };
                } catch (e) {
                    console.error('Failed to read RPC config cache:', e);
                    return null;
                }
            }

            /**
             * Set cached RPC config for a network
             * @param {string} network - Network name
             * @param {string} primary - Primary RPC URL
             * @param {string} fallback - Fallback RPC URL
             */
            set(network, primary, fallback) {
                try {
                    const cached = localStorage.getItem(this.storageKey);
                    const data = cached ? JSON.parse(cached) : {};

                    data[network] = {
                        primary,
                        fallback,
                        expires_at: Date.now() + this.ttl
                    };

                    localStorage.setItem(this.storageKey, JSON.stringify(data));
                    console.log(`RPC config cached for ${network}`);
                } catch (e) {
                    console.error('Failed to write RPC config cache:', e);
                }
            }

            /**
             * Clear all cached RPC configs
             */
            clear() {
                localStorage.removeItem(this.storageKey);
                console.log('RPC config cache cleared');
            }
        }

        // Global RPC config cache instance
        const rpcConfigCache = new RpcConfigCache(5); // 5 minute TTL

        /**
         * Fetch RPC configuration from backend API
         * @param {string} network - Network name (e.g., "avalanche-mainnet")
         * @returns {Promise<Object>} - { primary, fallback }
         */
        async function fetchRpcConfig(network) {
            // Check cache first
            const cached = rpcConfigCache.get(network);
            if (cached) {
                return cached;
            }

            try {
                const response = await fetch(`/api/rpc-config?network=${network}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                // Cache the result
                rpcConfigCache.set(network, data.primary, data.fallback);

                return { primary: data.primary, fallback: data.fallback };
            } catch (error) {
                console.error(`Failed to fetch RPC config for ${network}:`, error);

                // Return hardcoded fallback
                return getHardcodedFallback(network);
            }
        }

        /**
         * Hardcoded fallback RPC configs (emergency use only)
         * @param {string} network - Network name
         * @returns {Object} - { primary, fallback }
         */
        function getHardcodedFallback(network) {
            const fallbacks = {
                'avalanche-mainnet': {
                    primary: 'https://avalanche-c-chain-rpc.publicnode.com',
                    fallback: 'https://api.avax.network/ext/bc/C/rpc'
                },
                'base-mainnet': {
                    primary: 'https://mainnet.base.org',
                    fallback: 'https://base.gateway.tenderly.co'
                },
                'celo-mainnet': {
                    primary: 'https://rpc.celocolombia.org',
                    fallback: 'https://rpc.ankr.com/celo'
                },
                'hyperevm-mainnet': {
                    primary: 'https://rpc.hyperliquid.xyz/evm',
                    fallback: 'https://rpc.hyperliquid.xyz/evm'
                },
                'polygon-mainnet': {
                    primary: 'https://polygon.drpc.org',
                    fallback: 'https://polygon-rpc.com'
                },
                'solana-mainnet': {
                    primary: 'https://mainnet.helius-rpc.com/?api-key=f6fc10fb-cd9d-42e4-be78-900dde381d4a',
                    fallback: 'https://api.mainnet-beta.solana.com'
                },
                'optimism-mainnet': {
                    primary: 'https://mainnet.optimism.io',
                    fallback: 'https://public-op-mainnet.fastnode.io'
                },
                'avalanche-fuji': {
                    primary: 'https://avalanche-fuji-c-chain-rpc.publicnode.com',
                    fallback: 'https://api.avax-test.network/ext/bc/C/rpc'
                },
                'base-sepolia': {
                    primary: 'https://sepolia.base.org',
                    fallback: 'https://base-sepolia.gateway.tenderly.co'
                },
                'celo-sepolia': {
                    primary: 'https://rpc.ankr.com/celo_sepolia',
                    fallback: 'https://alfajores-forno.celo-testnet.org'
                },
                'polygon-amoy': {
                    primary: 'https://rpc-amoy.polygon.technology',
                    fallback: 'https://polygon-amoy.drpc.org'
                },
                'optimism-sepolia': {
                    primary: 'https://sepolia.optimism.io',
                    fallback: 'https://optimism-sepolia.gateway.tenderly.co'
                }
            };

            console.warn(`Using hardcoded fallback RPC for ${network}`);
            return fallbacks[network] || { primary: '', fallback: '' };
        }

        /**
         * Try to fetch data from RPC with timeout
         * @param {string} rpc - RPC URL
         * @param {Object} body - Request body
         * @param {number} timeoutMs - Timeout in milliseconds
         * @returns {Promise<Object>} - RPC response
         */
        async function fetchWithTimeout(rpc, body, timeoutMs = 5000) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

            try {
                const response = await fetch(rpc, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                return await response.json();
            } catch (error) {
                clearTimeout(timeoutId);
                throw error;
            }
        }

        /**
         * Fetch balance with automatic failover
         * @param {string} network - Network name
         * @param {string} address - Wallet address
         * @param {boolean} isSolana - Whether this is a Solana network
         * @returns {Promise<string>} - Formatted balance string
         */
        async function fetchBalanceWithFailover(network, address, isSolana = false) {
            const rpcConfig = await fetchRpcConfig(network);

            // Try primary RPC first
            try {
                console.log(`Fetching balance for ${network} from primary RPC`);
                const balance = await tryFetchBalance(
                    rpcConfig.primary,
                    address,
                    isSolana
                );
                return balance;
            } catch (primaryError) {
                console.warn(`Primary RPC failed for ${network}:`, primaryError);

                // Fallback to secondary RPC
                try {
                    console.log(`Fetching balance for ${network} from fallback RPC`);
                    const balance = await tryFetchBalance(
                        rpcConfig.fallback,
                        address,
                        isSolana
                    );

                    // Show warning indicator (non-blocking)
                    showRpcFailoverWarning(network, 'primary');

                    return balance;
                } catch (fallbackError) {
                    console.error(`Both RPCs failed for ${network}:`, fallbackError);

                    // Show error indicator
                    showRpcFailoverWarning(network, 'both');

                    throw new Error(`All RPCs failed for ${network}`);
                }
            }
        }

        /**
         * Try to fetch balance from a single RPC
         * @param {string} rpc - RPC URL
         * @param {string} address - Wallet address
         * @param {boolean} isSolana - Whether this is a Solana network
         * @returns {Promise<string>} - Formatted balance string
         */
        async function tryFetchBalance(rpc, address, isSolana = false) {
            if (isSolana) {
                // Solana uses different RPC method
                const data = await fetchWithTimeout(rpc, {
                    jsonrpc: '2.0',
                    method: 'getBalance',
                    params: [address],
                    id: 1
                }, 5000);

                if (data.result && data.result.value !== undefined) {
                    const balanceLamports = data.result.value;
                    const balanceSOL = balanceLamports / 1e9;
                    return balanceSOL.toFixed(4);
                } else {
                    throw new Error('Invalid Solana balance response');
                }
            } else {
                // EVM networks
                const data = await fetchWithTimeout(rpc, {
                    jsonrpc: '2.0',
                    method: 'eth_getBalance',
                    params: [address, 'latest'],
                    id: 1
                }, 5000);

                if (data.result) {
                    const balanceWei = BigInt(data.result);
                    const balanceEther = Number(balanceWei) / 1e18;
                    return balanceEther.toFixed(4);
                } else {
                    throw new Error('Invalid EVM balance response');
                }
            }
        }

        /**
         * Show RPC failover warning in UI
         * @param {string} network - Network name
         * @param {string} level - 'primary' or 'both'
         */
        function showRpcFailoverWarning(network, level) {
            // Store failover state for visual indicator
            if (!window.rpcFailoverState) {
                window.rpcFailoverState = {};
            }
            window.rpcFailoverState[network] = level;

            // Add visual indicator to network badge (optional enhancement)
            const badge = document.querySelector(`[data-balance="${network}"]`)?.closest('.network-badge');
            if (badge) {
                if (level === 'primary') {
                    badge.style.borderColor = '#f59e0b'; // Orange for fallback
                    badge.title = 'Using fallback RPC';
                } else {
                    badge.style.borderColor = '#ef4444'; // Red for error
                    badge.title = 'All RPCs failed';
                }
            }
        }
```

### 3.3 Replace fetchWalletBalances Function

**Task 3.3.1: Replace lines 1190-1312 in `x402-rs/static/index.html`**

Find the existing `fetchWalletBalances` function and replace with:

```javascript
        // Fetch wallet balances for both mainnet and testnet wallets
        async function fetchWalletBalances() {
            // Hardcoded wallet addresses
            const MAINNET_ADDRESS = '0x103040545AC5031A11E8C03dd11324C7333a13C7';
            const TESTNET_ADDRESS = '0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8';

            // Network configurations
            const networks = {
                'avalanche-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'base-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'celo-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'hyperevm-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'polygon-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'solana-mainnet': {
                    address: 'F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq',
                    isSolana: true
                },
                'optimism-mainnet': {
                    address: MAINNET_ADDRESS,
                    isSolana: false
                },
                'avalanche-testnet': {
                    address: TESTNET_ADDRESS,
                    isSolana: false
                },
                'base-testnet': {
                    address: TESTNET_ADDRESS,
                    isSolana: false
                },
                'celo-testnet': {
                    address: TESTNET_ADDRESS,
                    isSolana: false
                },
                'polygon-testnet': {
                    address: TESTNET_ADDRESS,
                    isSolana: false
                },
                'optimism-testnet': {
                    address: TESTNET_ADDRESS,
                    isSolana: false
                }
            };

            // Fetch balances for each network in parallel
            const balancePromises = Object.entries(networks).map(async ([network, config]) => {
                const balanceEl = document.querySelector(`[data-balance="${network}"]`);
                if (!balanceEl) return;

                try {
                    const balance = await fetchBalanceWithFailover(
                        network,
                        config.address,
                        config.isSolana
                    );
                    balanceEl.textContent = balance;
                } catch (error) {
                    console.error(`Error fetching ${network} balance:`, error);
                    balanceEl.textContent = 'Error';
                }
            });

            await Promise.allSettled(balancePromises);
        }
```

### 3.4 Add Cache Clear Button (Optional Enhancement)

**Task 3.4.1: Add cache management UI** (optional, for debugging)

Add after language switcher in header (line 774):

```html
                <button
                    class="lang-btn"
                    onclick="clearRpcCache()"
                    title="Clear RPC cache (for debugging)"
                    style="margin-left: 1rem; opacity: 0.5;">
                    Clear Cache
                </button>
```

Add JavaScript function:

```javascript
        function clearRpcCache() {
            rpcConfigCache.clear();
            alert('RPC cache cleared. Refresh the page to reload.');
        }
```

### Phase 3 Checklist

- [ ] Add RPC configuration classes to frontend (before line 1190)
- [ ] Replace `fetchWalletBalances` function with failover version
- [ ] Test in browser developer console
- [ ] Verify localStorage caching works
- [ ] Test failover behavior (simulate RPC failure with network throttling)
- [ ] Add visual indicators for RPC failover state (optional)
- [ ] Test on mobile devices (responsive behavior)

**Testing Phase 3**:

1. **Test Primary RPC**:
```javascript
// Open browser console on https://facilitator.ultravioletadao.xyz
fetchRpcConfig('avalanche-mainnet').then(console.log);
// Expected: { primary: "https://...", fallback: "https://..." }
```

2. **Test Cache**:
```javascript
// Check localStorage
localStorage.getItem('rpc_config_cache');
// Should show cached data with expires_at timestamp
```

3. **Test Failover** (simulate primary failure):
```javascript
// Modify fetchWithTimeout to always fail on primary
// Or use browser DevTools Network throttling
```

4. **Test Balance Fetching**:
```javascript
fetchBalanceWithFailover('avalanche-mainnet', '0x103040545AC5031A11E8C03dd11324C7333a13C7', false)
    .then(console.log);
// Expected: "1.2345" (balance)
```

5. **Visual Test**:
- Open https://facilitator.ultravioletadao.xyz
- Check all network badges show balances
- Block primary RPC in DevTools (Network tab → Block request URL)
- Refresh page, verify fallback works
- Check network badge shows orange/red indicator

**Estimated Time**: 3-4 hours

---

## Phase 4: Testing and Validation

### 4.1 Unit Tests

**Task 4.1.1: Add Rust tests**

File: `x402-rs/src/rpc_config.rs` (tests already included in Phase 2 code)

Run tests:
```bash
cd x402-rs
cargo test rpc_config
```

**Task 4.1.2: Add integration tests**

File: `x402-rs/tests/integration/rpc_config_test.rs` (create)

```rust
use x402_rs::rpc_config::RpcConfigManager;

#[tokio::test]
async fn test_rpc_config_manager_initialization() {
    let manager = RpcConfigManager::new().await.unwrap();
    let endpoints = manager.get_endpoints("avalanche-mainnet").await;
    assert!(!endpoints.primary.is_empty());
    assert!(!endpoints.fallback.is_empty());
}

#[tokio::test]
async fn test_rpc_config_cache_invalidation() {
    let manager = RpcConfigManager::new().await.unwrap();

    // First fetch (cache miss)
    let endpoints1 = manager.get_endpoints("avalanche-mainnet").await;

    // Second fetch (cache hit)
    let endpoints2 = manager.get_endpoints("avalanche-mainnet").await;

    assert_eq!(endpoints1.primary, endpoints2.primary);

    // Invalidate cache
    manager.invalidate_cache();

    // Third fetch (cache miss again)
    let endpoints3 = manager.get_endpoints("avalanche-mainnet").await;
    assert_eq!(endpoints1.primary, endpoints3.primary);
}
```

### 4.2 End-to-End Testing Scenarios

**Scenario 1: Normal Operation (Both RPCs Working)**

Steps:
1. Open https://facilitator.ultravioletadao.xyz
2. Verify all network badges show balances within 5 seconds
3. Check browser console for "RPC config cache hit" logs
4. Verify no error indicators on network badges

Expected Result:
- All balances load successfully
- Primary RPC used for all requests
- No failover warnings

**Scenario 2: Primary RPC Failure**

Steps:
1. Update AWS Secrets Manager primary RPC to invalid URL:
   ```bash
   aws secretsmanager update-secret \
     --secret-id karmacadabra-rpc-endpoints \
     --secret-string '{"version":"1.0","networks":{"avalanche-mainnet":{"primary":"https://invalid-rpc-url.com","fallback":"https://avalanche-c-chain-rpc.publicnode.com"}}}'
   ```
2. Clear frontend cache: `localStorage.removeItem('rpc_config_cache')`
3. Refresh page
4. Verify balances still load (using fallback)
5. Check browser console for "Primary RPC failed" warnings
6. Verify orange border on network badge

Expected Result:
- Balances load successfully via fallback
- Warning indicator shows on affected networks
- Console logs show failover behavior

**Scenario 3: AWS Secrets Manager Failure**

Steps:
1. Temporarily revoke IAM permissions for RPC secrets access
2. Clear frontend cache
3. Refresh page
4. Verify balances still load (using hardcoded fallback)

Expected Result:
- Backend logs show "Failed to load RPC config from AWS"
- Backend logs show "Using hardcoded fallback RPC config"
- Frontend still loads balances
- No user-facing errors

**Scenario 4: All RPCs Fail**

Steps:
1. Update AWS Secrets Manager with two invalid RPCs
2. Clear frontend cache
3. Refresh page
4. Verify error handling

Expected Result:
- Balance shows "Error" text
- Red border on network badge
- Console logs show "All RPCs failed"
- No JavaScript crashes

### 4.3 Performance Testing

**Test 1: Cache Performance**

Metric: Time to load RPC config with cache hit vs cache miss

```bash
# Measure backend response time
time curl -w '\nTotal: %{time_total}s\n' \
  http://localhost:8080/api/rpc-config?network=avalanche-mainnet

# Expected:
# - Cache miss: <100ms (AWS Secrets Manager API call)
# - Cache hit: <10ms (in-memory lookup)
```

**Test 2: Failover Latency**

Metric: Time to failover from primary to fallback RPC

Expected: <6 seconds total (5s primary timeout + 1s fallback fetch)

**Test 3: Concurrent Requests**

Test: 100 concurrent balance fetch requests

```bash
# Use Apache Bench or similar
ab -n 100 -c 10 http://localhost:8080/api/rpc-config?network=avalanche-mainnet
```

Expected: All requests succeed, cache hit rate >90%

### 4.4 Monitoring and Alerting

**Task 4.4.1: Add CloudWatch Metrics**

Metrics to track:
- `rpc_config_cache_hits` (Counter)
- `rpc_config_cache_misses` (Counter)
- `rpc_failover_events` (Counter, by network and level)
- `rpc_config_fetch_duration` (Histogram)

**Task 4.4.2: Add Logging**

Key log events:
- "RPC config loaded from AWS Secrets Manager"
- "RPC config cache hit/miss"
- "Primary RPC failed for {network}, using fallback"
- "All RPCs failed for {network}"

### Phase 4 Checklist

- [ ] Run Rust unit tests: `cargo test`
- [ ] Run integration tests
- [ ] Execute all 4 end-to-end scenarios
- [ ] Verify no regressions in existing functionality
- [ ] Test on multiple browsers (Chrome, Firefox, Safari, Edge)
- [ ] Test on mobile devices (iOS Safari, Android Chrome)
- [ ] Performance test: cache hit rate >90%
- [ ] Performance test: failover latency <6s
- [ ] Add CloudWatch metrics (optional)
- [ ] Document known issues and limitations

**Testing Checklist Template**:

```markdown
## Test Results - Phase 4

Date: _______
Tester: _______

### Scenario 1: Normal Operation
- [ ] All balances load: PASS/FAIL
- [ ] Primary RPC used: PASS/FAIL
- [ ] No warnings: PASS/FAIL

### Scenario 2: Primary RPC Failure
- [ ] Failover to fallback: PASS/FAIL
- [ ] Orange indicator shown: PASS/FAIL
- [ ] Console logs correct: PASS/FAIL

### Scenario 3: AWS Failure
- [ ] Hardcoded fallback works: PASS/FAIL
- [ ] No user errors: PASS/FAIL
- [ ] Backend logs correct: PASS/FAIL

### Scenario 4: All RPCs Fail
- [ ] Error handling works: PASS/FAIL
- [ ] Red indicator shown: PASS/FAIL
- [ ] No crashes: PASS/FAIL

### Performance
- [ ] Cache hit rate >90%: PASS/FAIL
- [ ] Failover latency <6s: PASS/FAIL
- [ ] 100 concurrent requests: PASS/FAIL

### Browser Compatibility
- [ ] Chrome: PASS/FAIL
- [ ] Firefox: PASS/FAIL
- [ ] Safari: PASS/FAIL
- [ ] Edge: PASS/FAIL
- [ ] Mobile (iOS): PASS/FAIL
- [ ] Mobile (Android): PASS/FAIL
```

**Estimated Time**: 4-6 hours

---

## Phase 5: Migration to Private QuickNode RPCs

### 5.1 Pre-Migration Checklist

Before replacing public RPCs with private QuickNode URLs:

- [ ] All Phase 1-4 tests passing
- [ ] Zero downtime migration plan approved
- [ ] QuickNode accounts created for all networks
- [ ] Backup plan documented
- [ ] Rollback procedure tested

### 5.2 QuickNode Setup

**Task 5.2.1: Create QuickNode Endpoints**

Required endpoints:
1. Avalanche Mainnet (C-Chain)
2. Base Mainnet
3. Celo Mainnet
4. Polygon Mainnet
5. Optimism Mainnet
6. Avalanche Fuji Testnet
7. Base Sepolia Testnet
8. Celo Sepolia Testnet (if available)
9. Polygon Amoy Testnet
10. Optimism Sepolia Testnet

**Note**: HyperEVM and Solana may not be available on QuickNode. Keep public RPCs for these.

**QuickNode Pricing** (estimate):
- Free tier: 5M monthly requests per endpoint
- Build tier: $49/month, 15M requests
- Scale tier: $99/month, 50M requests

For facilitator frontend (wallet balance fetching), free tier should suffice.

### 5.3 Update AWS Secrets Manager

**Task 5.3.1: Prepare New Secret Values**

Create `x402-rs/rpc-endpoints-quicknode.json` (gitignored):

```json
{
  "version": "1.0",
  "last_updated": "2025-10-30T12:00:00Z",
  "networks": {
    "avalanche-mainnet": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/ext/bc/C/rpc",
      "fallback": "https://avalanche-c-chain-rpc.publicnode.com"
    },
    "base-mainnet": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://mainnet.base.org"
    },
    "celo-mainnet": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://rpc.celocolombia.org"
    },
    "hyperevm-mainnet": {
      "primary": "https://rpc.hyperliquid.xyz/evm",
      "fallback": "https://rpc.hyperliquid.xyz/evm"
    },
    "polygon-mainnet": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://polygon.drpc.org"
    },
    "solana-mainnet": {
      "primary": "https://mainnet.helius-rpc.com/?api-key=f6fc10fb-cd9d-42e4-be78-900dde381d4a",
      "fallback": "https://api.mainnet-beta.solana.com"
    },
    "optimism-mainnet": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://mainnet.optimism.io"
    },
    "avalanche-fuji": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/ext/bc/C/rpc",
      "fallback": "https://avalanche-fuji-c-chain-rpc.publicnode.com"
    },
    "base-sepolia": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://sepolia.base.org"
    },
    "celo-sepolia": {
      "primary": "https://rpc.ankr.com/celo_sepolia",
      "fallback": "https://alfajores-forno.celo-testnet.org"
    },
    "polygon-amoy": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://rpc-amoy.polygon.technology"
    },
    "optimism-sepolia": {
      "primary": "https://[YOUR-QUICKNODE-ENDPOINT].quiknode.pro/[API-KEY]/",
      "fallback": "https://sepolia.optimism.io"
    }
  }
}
```

**Task 5.3.2: Update Secret (Blue-Green Approach)**

Strategy: Update secret during low-traffic period, monitor for 24 hours

```bash
# Step 1: Backup current secret
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-rpc-endpoints \
  --region us-east-1 \
  --output json > rpc-endpoints-backup.json

# Step 2: Update secret with QuickNode URLs
aws secretsmanager update-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --secret-string file://rpc-endpoints-quicknode.json \
  --region us-east-1

# Step 3: Invalidate cache (force immediate refresh)
curl -X POST https://facilitator.ultravioletadao.xyz/api/rpc-config/invalidate-cache

# Step 4: Verify new config
curl https://facilitator.ultravioletadao.xyz/api/rpc-config?network=avalanche-mainnet | jq
```

### 5.4 Monitoring Post-Migration

**Task 5.4.1: Monitor QuickNode Dashboard**

Check:
- Request count (should increase)
- Error rate (should stay <1%)
- Latency (should improve)

**Task 5.4.2: Monitor Application Logs**

Watch for:
- No "Primary RPC failed" warnings
- Cache hit rate remains >90%
- Balance fetch latency improves

**Task 5.4.3: Alert on Anomalies**

Set up CloudWatch alarms:
- Alert if RPC failover rate >5% for 5 minutes
- Alert if balance fetch latency >10s (99th percentile)
- Alert if QuickNode request count drops suddenly (indicates config issue)

### 5.5 Rollback Procedure

If issues detected within 24 hours:

```bash
# Restore backup secret
aws secretsmanager update-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --secret-string file://rpc-endpoints-backup.json \
  --region us-east-1

# Invalidate cache
curl -X POST https://facilitator.ultravioletadao.xyz/api/rpc-config/invalidate-cache

# Verify rollback
curl https://facilitator.ultravioletadao.xyz/api/rpc-config?network=avalanche-mainnet | jq
```

### Phase 5 Checklist

- [ ] QuickNode endpoints created for all supported networks
- [ ] Test each QuickNode endpoint individually (curl test)
- [ ] Prepare `rpc-endpoints-quicknode.json` with real URLs
- [ ] Backup current AWS secret
- [ ] Schedule migration during low-traffic window
- [ ] Update AWS secret
- [ ] Invalidate cache
- [ ] Monitor for 1 hour (immediate issues)
- [ ] Monitor for 24 hours (sustained performance)
- [ ] Document QuickNode API key rotation procedure
- [ ] Update team runbooks with new RPC management process

**Migration Timeline**:

```
Day 0 (Preparation):
- Create QuickNode endpoints
- Test each endpoint
- Document API keys securely

Day 1 (Migration):
- 00:00 UTC: Backup current secret
- 00:05 UTC: Update secret with QuickNode URLs
- 00:10 UTC: Invalidate cache
- 00:15 UTC: Verify new config in production
- 00:30 UTC: First monitoring check
- 01:00 UTC: Hourly monitoring begins

Day 2-7 (Monitoring):
- Daily checks of QuickNode dashboard
- Daily checks of application logs
- Daily checks of CloudWatch metrics

Day 8 (Confirmation):
- Mark migration as successful
- Remove backup secret file
- Update documentation
```

**Estimated Time**: 4-6 hours preparation, 24 hours monitoring

---

## Phase 6: Documentation and Training

### 6.1 Technical Documentation

**Task 6.1.1: Update README.md**

Add section: "RPC Endpoint Management"

```markdown
### RPC Endpoint Management

The x402 facilitator frontend uses a resilient RPC configuration system with automatic failover.

**Architecture**:
- RPC endpoints stored in AWS Secrets Manager: `karmacadabra-rpc-endpoints`
- Backend API: `/api/rpc-config?network={network}`
- Frontend cache: 5-minute TTL in localStorage
- Automatic failover: Primary → Fallback → Hardcoded emergency RPCs

**Updating RPCs**:
```bash
# 1. Update AWS secret
aws secretsmanager update-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --secret-string file://rpc-endpoints-new.json \
  --region us-east-1

# 2. Invalidate cache (optional, expires in 5 min)
curl -X POST https://facilitator.ultravioletadao.xyz/api/rpc-config/invalidate-cache
```

**Monitoring**:
- Check QuickNode dashboard for request count
- Monitor CloudWatch logs for "RPC failover" warnings
- Check frontend for orange/red network badges
```

**Task 6.1.2: Create Operations Runbook**

File: `docs/runbooks/RPC_ENDPOINT_OPERATIONS.md`

```markdown
# RPC Endpoint Operations Runbook

## Overview
This runbook covers operational procedures for managing RPC endpoints in the x402 facilitator.

## Common Tasks

### 1. Add New Network
1. Update AWS secret with new network config
2. Add network to hardcoded fallback in `rpc_config.rs`
3. Add network to frontend fallback in `index.html`
4. Deploy backend + frontend
5. Test new network

### 2. Rotate QuickNode API Keys
1. Generate new API keys on QuickNode dashboard
2. Update `rpc-endpoints.json` with new keys
3. Update AWS secret
4. Invalidate cache
5. Monitor for 1 hour
6. Revoke old API keys

### 3. Debug RPC Issues
**Symptom**: Orange border on network badge

**Diagnosis**:
```bash
# Check backend logs
aws logs tail /aws/ecs/karmacadabra-prod-facilitator --follow

# Test primary RPC directly
curl -X POST https://[QUICKNODE-URL] \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Check AWS secret
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-rpc-endpoints \
  --region us-east-1 | jq -r '.SecretString'
```

**Resolution**:
- If QuickNode rate limited: Upgrade plan or switch to fallback
- If QuickNode down: Temporarily use public RPC
- If AWS Secrets Manager down: Backend automatically uses hardcoded fallback

### 4. Emergency Rollback
If all RPCs failing for a network:

1. Quick fix (use public RPC):
```bash
aws secretsmanager update-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --secret-string '{"version":"1.0","networks":{"avalanche-mainnet":{"primary":"https://avalanche-c-chain-rpc.publicnode.com","fallback":"https://api.avax.network/ext/bc/C/rpc"}}}'
```

2. Invalidate cache: `curl -X POST .../invalidate-cache`
3. Verify: `curl .../api/rpc-config?network=avalanche-mainnet`

## Alerts and Responses

### Alert: High RPC Failover Rate
**Trigger**: >5% of requests failing over to fallback

**Response**:
1. Check QuickNode dashboard for issues
2. Check primary RPC health: `curl -X POST [primary-url] ...`
3. If primary unhealthy, temporarily promote fallback to primary
4. Investigate root cause

### Alert: AWS Secrets Manager Unavailable
**Trigger**: Backend logs show "Failed to load RPC config from AWS"

**Response**:
1. Backend automatically uses hardcoded fallback (no action needed)
2. Check AWS health dashboard
3. Check IAM permissions for ECS task role
4. Once AWS recovers, cache will auto-refresh in 5 minutes
```

### 6.2 User Guide

**Task 6.2.1: Create User Guide**

File: `docs/guides/RPC_MANAGEMENT_GUIDE.md`

```markdown
# RPC Endpoint Management Guide

## For System Administrators

### Prerequisites
- AWS CLI configured with appropriate credentials
- Access to QuickNode dashboard
- Access to Karmacadabra AWS account

### How to Replace Public RPCs with Private QuickNode RPCs

**Step 1: Create QuickNode Endpoints**
1. Sign up at https://www.quicknode.com/
2. Create endpoints for desired networks (see list below)
3. Copy endpoint URLs (format: `https://[name].quiknode.pro/[api-key]/`)

**Required Networks**:
- Avalanche C-Chain Mainnet
- Base Mainnet
- Celo Mainnet
- Polygon Mainnet
- Optimism Mainnet
- Avalanche Fuji Testnet
- Base Sepolia Testnet
- Polygon Amoy Testnet
- Optimism Sepolia Testnet

**Step 2: Update Configuration File**
1. Create `rpc-endpoints.json`:
```json
{
  "version": "1.0",
  "last_updated": "2025-10-30T12:00:00Z",
  "networks": {
    "avalanche-mainnet": {
      "primary": "https://[your-endpoint].quiknode.pro/[api-key]/ext/bc/C/rpc",
      "fallback": "https://avalanche-c-chain-rpc.publicnode.com"
    },
    ...
  }
}
```

**Step 3: Update AWS Secret**
```bash
aws secretsmanager update-secret \
  --secret-id karmacadabra-rpc-endpoints \
  --secret-string file://rpc-endpoints.json \
  --region us-east-1
```

**Step 4: Verify**
```bash
# Invalidate cache (forces immediate refresh)
curl -X POST https://facilitator.ultravioletadao.xyz/api/rpc-config/invalidate-cache

# Check new config
curl https://facilitator.ultravioletadao.xyz/api/rpc-config?network=avalanche-mainnet
```

**Step 5: Monitor**
- Open https://facilitator.ultravioletadao.xyz
- Verify all network badges show balances
- Check browser console for errors
- Monitor QuickNode dashboard for request count

### Troubleshooting

**Issue**: Balances not loading
- Check browser console for errors
- Verify AWS secret updated correctly
- Test QuickNode URLs directly with curl
- Check IAM permissions for ECS task role

**Issue**: Orange border on network badge
- Primary RPC is failing, using fallback
- Check QuickNode dashboard for rate limiting
- Verify API key is valid
- Consider upgrading QuickNode plan

**Issue**: Red border on network badge
- All RPCs failing
- Check QuickNode and public RPC availability
- Verify network is not under maintenance
- Check for typos in RPC URLs
```

### 6.3 Training Materials

**Task 6.3.1: Create Training Checklist**

For new team members:

```markdown
## RPC Management Training Checklist

**Trainee**: _______
**Trainer**: _______
**Date**: _______

### Fundamentals
- [ ] Understand three-layer architecture (AWS → Backend → Frontend)
- [ ] Understand caching strategy (5-minute TTL)
- [ ] Understand failover mechanism (Primary → Fallback → Hardcoded)

### Hands-On Tasks
- [ ] View current RPC config in AWS Secrets Manager
- [ ] Call backend API: `/api/rpc-config`
- [ ] Inspect frontend cache in browser localStorage
- [ ] Simulate RPC failure (DevTools network blocking)
- [ ] Update AWS secret (in staging environment)
- [ ] Invalidate cache via API
- [ ] Monitor QuickNode dashboard

### Emergency Procedures
- [ ] Practice rollback procedure
- [ ] Practice adding new network
- [ ] Practice rotating API keys
- [ ] Review alert response procedures

### Quiz
1. What happens if AWS Secrets Manager is unavailable?
2. How long does RPC config cache last?
3. What does orange border on network badge mean?
4. How to force immediate cache refresh?
5. What is the rollback procedure?

**Training Complete**: _______
**Trainer Signature**: _______
```

### Phase 6 Checklist

- [ ] Update README.md with RPC management section
- [ ] Create operations runbook
- [ ] Create user guide for admin tasks
- [ ] Create training materials for new team members
- [ ] Record video walkthrough (optional)
- [ ] Update Terraform documentation
- [ ] Update team wiki with RPC procedures
- [ ] Schedule training session for team

**Estimated Time**: 3-4 hours

---

## Summary and Next Steps

### Implementation Timeline

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|----------------|--------------|
| Phase 1 | AWS Secrets Setup | 2-3 hours | AWS access |
| Phase 2 | Backend API | 4-6 hours | Phase 1 complete |
| Phase 3 | Frontend Failover | 3-4 hours | Phase 2 complete |
| Phase 4 | Testing | 4-6 hours | Phase 3 complete |
| Phase 5 | QuickNode Migration | 4-6 hours + 24h monitoring | Phase 4 passing |
| Phase 6 | Documentation | 3-4 hours | Phase 5 complete |
| **Total** | | **20-29 hours** + 24h monitoring | |

### Success Metrics

After full implementation, measure:
- **Reliability**: Uptime >99.9% for balance fetching
- **Performance**: 95th percentile latency <3s for balance fetch
- **Cache Efficiency**: Cache hit rate >90%
- **Failover Frequency**: <1% of requests require failover
- **Cost**: AWS Secrets Manager <$2/month

### Known Limitations

1. **Cache Invalidation**: 5-minute TTL means secret updates take up to 5 minutes to propagate (acceptable for RPC config)
2. **Browser Support**: Requires modern browsers with localStorage and fetch API
3. **QuickNode Coverage**: Not all networks available on QuickNode (HyperEVM uses public RPC)
4. **Single Point of Failure**: If both primary and fallback RPCs fail, no mitigation (rare scenario)

### Future Enhancements

1. **RPC Health Monitoring**: Periodic health checks of all RPCs, automatic rotation
2. **Load Balancing**: Round-robin between multiple primary RPCs
3. **Geolocation-Based Routing**: Select closest RPC based on user location
4. **Admin Dashboard**: Web UI for managing RPC endpoints (no AWS CLI required)
5. **WebSocket Support**: Real-time balance updates using WebSocket RPCs

### Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AWS Secrets Manager outage | Low | Medium | Hardcoded fallback in code |
| QuickNode rate limiting | Medium | Low | Automatic failover to public RPC |
| All RPCs fail for a network | Very Low | High | Show error, retry after 30s |
| Cache poisoning | Very Low | Low | 5-minute TTL limits exposure |
| Browser compatibility issue | Low | Medium | Progressive enhancement, fallback to current implementation |

### Rollback Plan

At any point, revert to current implementation:
1. Remove `/api/rpc-config` routes from backend
2. Revert frontend to hardcoded RPC URLs (commit hash: `[current-commit]`)
3. Redeploy facilitator service
4. Estimated rollback time: 10 minutes

### Support Contacts

- **AWS Issues**: AWS Support (Business plan)
- **QuickNode Issues**: QuickNode Support (support@quicknode.com)
- **Code Issues**: Karmacadabra Core Team (GitHub issues)

---

## Appendices

### Appendix A: Network Reference

| Network | Chain ID | Native Token | QuickNode Support | Public RPC |
|---------|----------|--------------|-------------------|------------|
| Avalanche Mainnet | 43114 | AVAX | Yes | publicnode.com |
| Base Mainnet | 8453 | ETH | Yes | base.org |
| Celo Mainnet | 42220 | CELO | Yes | celocolombia.org |
| HyperEVM Mainnet | 998 | HYPE | No | hyperliquid.xyz |
| Polygon Mainnet | 137 | POL | Yes | drpc.org |
| Solana Mainnet | N/A | SOL | Yes | helius.xyz |
| Optimism Mainnet | 10 | ETH | Yes | optimism.io |
| Avalanche Fuji | 43113 | AVAX | Yes | publicnode.com |
| Base Sepolia | 84532 | ETH | Yes | base.org |
| Celo Sepolia | 44787 | CELO | Limited | ankr.com |
| Polygon Amoy | 80002 | POL | Yes | polygon.technology |
| Optimism Sepolia | 11155420 | ETH | Yes | optimism.io |

### Appendix B: AWS IAM Policy Template

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:karmacadabra-rpc-endpoints-*"
      ]
    }
  ]
}
```

### Appendix C: Sample RPC Health Check Script

```bash
#!/bin/bash
# rpc-health-check.sh
# Checks health of all RPCs in AWS Secrets Manager

SECRET_NAME="karmacadabra-rpc-endpoints"
REGION="us-east-1"

# Fetch secret
SECRET=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $REGION \
  --query SecretString \
  --output text)

# Parse networks
NETWORKS=$(echo $SECRET | jq -r '.networks | keys[]')

for NETWORK in $NETWORKS; do
  PRIMARY=$(echo $SECRET | jq -r ".networks[\"$NETWORK\"].primary")
  FALLBACK=$(echo $SECRET | jq -r ".networks[\"$NETWORK\"].fallback")

  echo "Testing $NETWORK..."

  # Test primary
  RESPONSE=$(curl -s -X POST $PRIMARY \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    --max-time 5)

  if echo $RESPONSE | jq -e '.result' > /dev/null 2>&1; then
    echo "  Primary: OK"
  else
    echo "  Primary: FAIL"
  fi

  # Test fallback
  RESPONSE=$(curl -s -X POST $FALLBACK \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    --max-time 5)

  if echo $RESPONSE | jq -e '.result' > /dev/null 2>&1; then
    echo "  Fallback: OK"
  else
    echo "  Fallback: FAIL"
  fi
done
```

Usage: `bash rpc-health-check.sh`

### Appendix D: Frontend Error Messages

User-facing messages for different error scenarios:

| Scenario | Badge Color | Console Log | User Action |
|----------|-------------|-------------|-------------|
| Normal operation | Default | "RPC config cache hit" | None |
| Primary RPC failed | Orange | "Primary RPC failed, using fallback" | None (automatic) |
| Both RPCs failed | Red | "All RPCs failed for {network}" | Refresh page, contact support |
| AWS unavailable | Default | "Using hardcoded fallback RPC config" | None (transparent) |
| Cache expired | Default | "RPC config cache expired, refreshing" | None (automatic) |

---

**End of Master Plan**

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Next Review**: After Phase 4 completion

**Approvals**:
- Technical Lead: _______
- DevOps Lead: _______
- Security Review: _______
