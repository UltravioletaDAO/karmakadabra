# x402-rs: Payment Facilitator for Karmacadabra

> HTTP 402 payment facilitator customized for Ultravioleta DAO's trustless agent economy

**Version**: 1.0.0 (Karmacadabra Custom)
**Network**: Avalanche Fuji Testnet
**Status**: 🔴 Ready to configure and deploy
**Last Updated**: October 22, 2025

---

## 🗂️ Location in Project

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    (GLUE Token - facilitator settles with this)
├── erc-8004/                  (ERC-8004 Registries)
├── x402-rs/                   ← YOU ARE HERE
├── validator/                 (Uses facilitator for validation fees)
├── karma-hello-agent/         (Uses facilitator for 0.01 UVD payments)
├── abracadabra-agent/         (Uses facilitator for 0.02 UVD payments)
├── MASTER_PLAN.md
└── MONETIZATION_OPPORTUNITIES.md
```

**Part of Master Plan**: Phase 1 - Blockchain Infrastructure (Week 1-2)

---

## 🎯 Description

The **x402-rs facilitator** is the **payment engine** for Karmacadabra's trustless agent economy. It enables:

- ✅ **Gasless micropayments** using EIP-3009 meta-transactions
- ✅ **HTTP 402 protocol** for payment-gated APIs
- ✅ **Stateless verification** (no database needed)
- ✅ **Multi-token support** (USDC, UVD, WAVAX)
- ✅ **OpenTelemetry** observability

### Role in Ecosystem

**All agent payments flow through this facilitator:**

1. **Karma-Hello Seller** sells logs (0.01 UVD) → x402 verifies & settles
2. **Abracadabra Seller** sells transcripts (0.02 UVD) → x402 verifies & settles
3. **Validator Agent** charges validation fees (0.001 UVD) → x402 verifies & settles

**Key Innovation**: Agents don't need AVAX for gas. The facilitator pays gas fees using its hot wallet, enabling fully autonomous agent operation.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│    facilitator.ultravioletadao.xyz          │
│    (Docker on Cherry Servers)               │
├─────────────────────────────────────────────┤
│                                             │
│  POST /verify                               │
│  • Verify EIP-712 signature                 │
│  • Check nonce not used on-chain            │
│  • Validate UVD balance                     │
│  • Return: {valid: true}                    │
│                                             │
│  POST /settle                               │
│  • Execute transferWithAuthorization()      │
│  • Submit to Avalanche Fuji                 │
│  • Wait for confirmation                    │
│  • Return: {txHash: "0x..."}                │
│                                             │
│  GET /supported                             │
│  • List: ["evm-eip3009-USDC-fuji",          │
│           "evm-eip3009-UVD-fuji",           │
│           "evm-eip3009-WAVAX-fuji"]         │
│                                             │
│  GET /health                                │
│  • Return service status                    │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 🔧 Karmacadabra Configuration

### Network Configuration

**Supported Networks:**
- ✅ **Avalanche Fuji Testnet** (primary)
- ❌ Base Sepolia (not supported)
- ❌ Ethereum Sepolia (not supported)
- ❌ Polygon Amoy (not supported)

**RPC Endpoints:**
- **Primary**: Custom RPC (private endpoint)
- **Fallback**: `https://avalanche-fuji-c-chain-rpc.publicnode.com`

### Supported Tokens

Based on deployment addresses from `erc-20/deployment.json`:

| Token | Network | Address | Decimals | Use Case |
|-------|---------|---------|----------|----------|
| **GLUE** | Fuji | `0x...` (from deployment) | 6 | Primary payment token |
| **USDC** | Fuji | `0x5425890298aed601595a70AB815c96711a31Bc65` | 6 | Alternative payment |
| **WAVAX** | Fuji | `0xd00ae08403B9bbb9124bB305C09058E32C39A48c` | 18 | Alternative payment |

**Note**: Token addresses will be configured after deploying GLUE token in Phase 1.

### Wallet Configuration

**Hot Wallet Setup** (2 keys for rotation):

```bash
# Primary facilitator wallet
FACILITATOR_WALLET_PRIMARY=0x...    # Active key
FACILITATOR_BALANCE_MIN=1.0         # Min 1 AVAX for gas

# Standby wallet (for key rotation)
FACILITATOR_WALLET_STANDBY=0x...    # Backup key
```

**Gas Strategy:**
- Facilitator pays gas for all `transferWithAuthorization()` calls
- Estimated cost: 0.001-0.01 AVAX per transaction
- With 1 AVAX: ~100-1000 transactions
- Monitoring alerts when balance < 1 AVAX

---

## 📦 Deployment

### Environment Variables

Create `.env` for Karmacadabra:

```bash
# Network Configuration
SIGNER_TYPE=private-key
EVM_PRIVATE_KEY=0x...                           # Facilitator hot wallet
RPC_URL_AVALANCHE_FUJI=https://your-rpc.xyz     # Primary RPC
RPC_URL_AVALANCHE_FUJI_FALLBACK=https://avalanche-fuji-c-chain-rpc.publicnode.com

# Server Configuration
HOST=0.0.0.0
PORT=8080
RUST_LOG=info

# Token Addresses (from erc-20/deployment.json)
UVD_TOKEN_ADDRESS=0x...                         # After deployment
USDC_FUJI_ADDRESS=0x5425890298aed601595a70AB815c96711a31Bc65
WAVAX_FUJI_ADDRESS=0xd00ae08403B9bbb9124bB305C09058E32C39A48c

# Observability (Prometheus + Grafana + Loki)
OTEL_EXPORTER_OTLP_ENDPOINT=http://grafana.ultravioletadao.xyz:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=x402-facilitator-karmacadabra

# Rate Limiting (future)
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Webhooks (future)
WEBHOOK_URL=https://api.ultravioletadao.xyz/webhooks/payments
```

### Build & Run (Docker on Cherry Servers)

```bash
# 1. Build Docker image
docker build -t x402-facilitator-karmacadabra .

# 2. Run container
docker run -d \
  --name facilitator \
  --restart unless-stopped \
  --env-file .env \
  -p 8080:8080 \
  -v /var/log/facilitator:/var/log \
  x402-facilitator-karmacadabra

# 3. Check logs
docker logs -f facilitator

# 4. Health check
curl https://facilitator.ultravioletadao.xyz/health
```

### HTTPS Setup (Caddy)

```caddyfile
facilitator.ultravioletadao.xyz {
    reverse_proxy localhost:8080

    # Rate limiting
    rate_limit {
        zone facilita facilitator {
            key {remote_host}
            events 60
            window 1m
        }
    }

    # Logging
    log {
        output file /var/log/caddy/facilitator.log
    }
}
```

---

## 🔌 Integration with Agents

### Server-Side (Sellers use x402-axum)

**Karma-Hello Seller:**
```rust
// karma-hello-agent/src/main.rs (if using Rust API)
use x402_axum::X402Middleware;

let facilitator = X402Middleware::try_from(
    "https://facilitator.ultravioletadao.xyz"
).unwrap();

let uvd = UVDDeployment::by_network(Network::AvalancheFuji);

let app = Router::new()
    .route("/api/logs", post(get_logs).layer(
        facilitator.with_price_tag(
            uvd.amount("0.01")
                .pay_to("0xKarmaHelloSellerWallet")
                .unwrap()
        )
    ));
```

**Or in Python (FastAPI + x402):**
```python
# karma-hello-agent/agents/karma_hello_seller.py
from x402 import X402Middleware

x402 = X402Middleware(
    facilitator_url="https://facilitator.ultravioletadao.xyz",
    token_address=UVD_TOKEN_ADDRESS,
    price="0.01"  # 0.01 UVD
)

@app.post("/api/logs")
@x402.require_payment
async def get_logs(request: LogsRequest):
    # Payment verified, return data
    return {"logs": [...]}
```

### Client-Side (Buyers use x402-reqwest)

**Karma-Hello Buyer:**
```python
# karma-hello-agent/agents/karma_hello_buyer.py
from x402_client import X402Client

client = X402Client(
    private_key=BUYER_PRIVATE_KEY,
    facilitator_url="https://facilitator.ultravioletadao.xyz"
)

# Buy transcript from Abracadabra
response = await client.post(
    url="https://abracadabra-seller.xyz/api/transcripts",
    payment=UVD.amount("0.02").pay_to(abracadabra_wallet),
    json={"stream_id": "12345"}
)

transcript = response.json()
```

---

## 📊 Monitoring & Observability

### Prometheus Metrics

**Exposed at**: `http://facilitator.ultravioletadao.xyz:8080/metrics`

**Key Metrics:**
- `x402_payments_total` - Total payments processed
- `x402_payments_success` - Successful settlements
- `x402_payments_failed` - Failed transactions
- `x402_verify_latency_seconds` - Verification latency
- `x402_settle_latency_seconds` - Settlement latency
- `x402_gas_used_total` - Total gas consumed
- `x402_balance_avax` - Facilitator AVAX balance

### Grafana Dashboard

**Panels:**
1. **Payments Overview**
   - Total payments/hour
   - Success rate (%)
   - Average transaction time

2. **Agent Activity**
   - Karma-Hello transactions
   - Abracadabra transactions
   - Validator fees

3. **System Health**
   - Facilitator balance (alert if < 1 AVAX)
   - RPC endpoint status
   - Error rate

4. **Gas Metrics**
   - Gas used per transaction
   - Total gas cost (AVAX)
   - Estimated runway

### Alerts

**Critical Alerts (PagerDuty/Discord):**
```yaml
- name: FacilitatorBalanceLow
  condition: x402_balance_avax < 1.0
  action: Send alert to ops channel

- name: HighErrorRate
  condition: (x402_payments_failed / x402_payments_total) > 0.1
  action: Send alert + auto-restart

- name: RpcEndpointDown
  condition: x402_rpc_errors_total > 10 in 5min
  action: Switch to fallback RPC + alert
```

---

## 🧪 Testing

### Local Testing (Anvil)

```bash
# Terminal 1: Start Anvil (simulates Fuji)
anvil --chain-id 43113 --port 8545

# Terminal 2: Deploy UVD token to local chain
cd ../erc-20
forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast

# Terminal 3: Run facilitator with local RPC
cd ../x402-rs
RPC_URL_AVALANCHE_FUJI=http://localhost:8545 cargo run

# Terminal 4: Test with curl
curl -X POST http://localhost:8080/verify \
  -H "Content-Type: application/json" \
  -d '{
    "from": "0x...",
    "to": "0x...",
    "value": "10000",
    "validAfter": "0",
    "validBefore": "9999999999",
    "nonce": "0xabc...",
    "v": 27,
    "r": "0x...",
    "s": "0x..."
  }'
```

### Integration Testing

```bash
# Test with real agents
cd ../karma-hello-agent
python scripts/test_payment.py --facilitator http://localhost:8080

# Expected output:
# ✅ Payment verified
# ✅ Transaction settled: 0x...
# ✅ Balance updated on-chain
```

---

## 🚀 Deployment Checklist

### Phase 1: Initial Deployment

- [ ] Deploy GLUE token to Fuji
- [ ] Save UVD address to `erc-20/deployment.json`
- [ ] Update `.env` with UVD address
- [ ] Build Docker image
- [ ] Deploy to Cherry Servers
- [ ] Configure Caddy reverse proxy
- [ ] Setup HTTPS certificate
- [ ] Test `/health` endpoint
- [ ] Test `/supported` endpoint
- [ ] Verify Prometheus metrics working

### Phase 1.5: Observability

- [ ] Configure Grafana data source
- [ ] Import facilitator dashboard
- [ ] Setup alerts in Prometheus
- [ ] Test alert firing
- [ ] Configure Discord/PagerDuty webhooks

### Phase 2: Agent Integration

- [ ] Karma-Hello Seller connects to facilitator
- [ ] Abracadabra Seller connects to facilitator
- [ ] Validator Agent connects to facilitator
- [ ] Test end-to-end payment flow
- [ ] Verify transactions on Snowtrace

### Phase 3: Production Hardening

- [ ] Enable rate limiting
- [ ] Setup key rotation procedure
- [ ] Configure automatic AVAX top-up
- [ ] Load testing (100 tx/min)
- [ ] Disaster recovery plan
- [ ] Documentation for ops team

---

## 🔒 Security Considerations

### Hot Wallet Protection

1. **Minimum Balance**: Keep only 5-10 AVAX max
2. **Key Rotation**: Rotate every 30 days
3. **Monitoring**: Alert if unexpected gas usage
4. **Backup**: Standby key ready for immediate rotation

### Rate Limiting

```rust
// Future implementation
const MAX_REQUESTS_PER_MINUTE: u32 = 60;
const MAX_REQUESTS_PER_HOUR: u32 = 1000;

// Per IP address
// Per agent (via signature verification)
```

### Replay Protection

- ✅ EIP-3009 nonces prevent replay attacks
- ✅ `validBefore` timestamp prevents expired payments
- ✅ Signature verification ensures authenticity

---

## 📈 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Verify latency | < 100ms | TBD |
| Settle latency | < 3s | TBD |
| Throughput | 100 tx/min | TBD |
| Uptime | 99.9% | TBD |
| Error rate | < 1% | TBD |

---

## 🛠️ Future Enhancements

### Phase 2+ Features (Post-MVP)

1. **Payment Receipts Export**
   - JSON export: `/api/receipts?format=json&from=date&to=date`
   - CSV export: `/api/receipts?format=csv`

2. **Webhooks**
   - POST to `WEBHOOK_URL` on every settlement
   - Payload: `{txHash, from, to, amount, timestamp}`

3. **Analytics Dashboard**
   - Revenue per agent
   - Most popular services
   - Peak usage times

4. **Multi-Wallet Support**
   - Round-robin between multiple hot wallets
   - Auto-distribute gas costs

5. **Advanced Rate Limiting**
   - Per-agent quotas
   - Dynamic pricing based on load

---

## 📚 References

### Karmacadabra Docs

- **MASTER_PLAN.md**: Complete system architecture
- **erc-20/README.md**: GLUE Token documentation
- **MONETIZATION_OPPORTUNITIES.md**: All services & pricing

### x402 Protocol

- **x402 Spec**: https://www.x402.org
- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712**: https://eips.ethereum.org/EIPS/eip-712

### Original x402-rs

- **GitHub**: https://github.com/x402-rs/x402-rs
- **Crates.io**: https://crates.io/crates/x402-rs
- **Docker Hub**: https://hub.docker.com/r/ukstv/x402-facilitator

---

## 🤝 Support

**Deployment Issues:**
- Check facilitator logs: `docker logs -f facilitator`
- Verify RPC endpoint: `curl $RPC_URL_AVALANCHE_FUJI`
- Check AVAX balance: `cast balance $FACILITATOR_WALLET --rpc-url $RPC_URL`

**Payment Failures:**
- Verify UVD token address is correct
- Check buyer has sufficient UVD balance
- Verify nonce is unique (not reused)
- Check signature validity with `cast`

**Monitoring:**
- Grafana: https://grafana.ultravioletadao.xyz
- Metrics: https://facilitator.ultravioletadao.xyz/metrics
- Logs: `/var/log/facilitator/`

---

**Part of Karmacadabra**: Trustless Agent Economy by Ultravioleta DAO

**Status**: Ready for Phase 1 deployment

**Next Step**: Deploy GLUE token, then configure and deploy facilitator
