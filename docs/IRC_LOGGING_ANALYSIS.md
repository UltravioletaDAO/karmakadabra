# IRC Logging Integration - Technical Analysis

**Date**: 2025-10-31
**Scope**: x402-rs facilitator and test-seller service
**Goal**: Real-time log streaming to IRC channel as alternative to CloudWatch/ECS console

---

## Executive Summary

**RECOMMENDATION: ✅ FEASIBLE AND RECOMMENDED**

IRC logging is a proven DevOps practice that would significantly improve operational visibility for the Karmacadabra infrastructure. The implementation is straightforward with existing Rust ecosystem libraries and can be deployed incrementally.

**Key Benefits**:
- ✅ Real-time monitoring without AWS console access
- ✅ Team collaboration (multiple people can watch same channel)
- ✅ Searchable history via IRC client or bouncer
- ✅ Low latency (<100ms vs 3-10s CloudWatch delay)
- ✅ Works during live streams without exposing AWS credentials

**Key Concerns**:
- ⚠️ IRC server dependency (mitigated with fallback to console logging)
- ⚠️ Need filtering to avoid log spam
- ⚠️ Must sanitize sensitive data (private keys, API keys)

---

## Technical Implementation

### 1. Rust IRC Library Selection

**Recommended: `irc` crate (v1.0.0)**

```toml
[dependencies]
irc = "1.0.0"  # Mature, async/await, Tokio-based
```

**Why this library:**
- ✅ Actively maintained (last release: recent)
- ✅ Async/await support (matches x402-rs Tokio stack)
- ✅ RFC 2812 compliant
- ✅ MPL-2.0 license (compatible with Apache-2.0)
- ✅ Battle-tested in production systems

**Alternatives considered:**
- `twitch-irc`: Twitch-specific, not general IRC
- `irc-channel`: Lower-level, requires more boilerplate

---

### 2. Architecture for x402-rs Facilitator

#### Option A: Custom Tracing Layer (RECOMMENDED)

Create a custom `tracing-subscriber` layer that sends events to IRC:

```rust
// src/irc_layer.rs
use tracing_subscriber::Layer;
use tracing::{Event, Subscriber};
use irc::client::prelude::*;
use tokio::sync::mpsc;

pub struct IrcLayer {
    tx: mpsc::UnboundedSender<String>,
}

impl<S> Layer<S> for IrcLayer
where
    S: Subscriber,
{
    fn on_event(&self, event: &Event<'_>, _ctx: tracing_subscriber::layer::Context<'_, S>) {
        let metadata = event.metadata();

        // Filter based on level (only INFO, WARN, ERROR)
        if matches!(metadata.level(), &tracing::Level::INFO | &tracing::Level::WARN | &tracing::Level::ERROR) {
            // Format message
            let msg = format!(
                "[{}] {} - {}",
                metadata.level(),
                metadata.target(),
                // Extract event fields (requires custom visitor)
                format_event_fields(event)
            );

            // Send to IRC channel (non-blocking)
            let _ = self.tx.send(msg);
        }
    }
}

// Background task that sends messages to IRC
async fn irc_sender_task(
    mut rx: mpsc::UnboundedReceiver<String>,
    channel: String,
    config: Config,
) {
    loop {
        match Client::from_config(config.clone()).await {
            Ok(mut client) => {
                client.identify().await.ok();

                while let Some(msg) = rx.recv().await {
                    // Rate limiting: max 1 message per 500ms to avoid flood kick
                    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

                    if let Err(e) = client.send_privmsg(&channel, &msg) {
                        eprintln!("Failed to send IRC message: {}", e);
                    }
                }
            }
            Err(e) => {
                eprintln!("IRC connection failed: {}, retrying in 30s...", e);
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
            }
        }
    }
}
```

**Integration in `src/telemetry.rs`:**

```rust
pub fn register(&self) -> TelemetryProviders {
    let telemetry_protocol = TelemetryProtocol::from_env();

    // IRC layer setup (if IRC_ENABLED=true)
    let irc_layer = if env::var("IRC_ENABLED").is_ok() {
        let (tx, rx) = mpsc::unbounded_channel();

        let config = Config {
            nickname: Some(env::var("IRC_NICK").unwrap_or("x402-facilitator".to_string())),
            server: Some(env::var("IRC_SERVER").unwrap_or("irc.libera.chat".to_string())),
            channels: vec![env::var("IRC_CHANNEL").unwrap_or("#karmacadabra-logs".to_string())],
            use_tls: Some(true),
            ..Default::default()
        };

        // Spawn background IRC sender
        tokio::spawn(irc_sender_task(rx, config.channels[0].clone(), config));

        Some(IrcLayer { tx })
    } else {
        None
    };

    match telemetry_protocol {
        Some(telemetry_protocol) => {
            let tracer_provider = self.init_tracer_provider(&telemetry_protocol);
            let meter_provider = self.init_meter_provider(&telemetry_protocol);
            let tracer = tracer_provider.tracer("tracing-otel-subscriber");

            // Register with optional IRC layer
            let subscriber = tracing_subscriber::registry()
                .with(tracing_subscriber::filter::LevelFilter::INFO)
                .with(tracing_subscriber::fmt::layer())
                .with(MetricsLayer::new(meter_provider.clone()))
                .with(OpenTelemetryLayer::new(tracer));

            if let Some(irc_layer) = irc_layer {
                subscriber.with(irc_layer).init();
            } else {
                subscriber.init();
            }

            // ... rest of function
        }
        // ... None case
    }
}
```

**Environment Variables:**

```bash
# .env or ECS task definition
IRC_ENABLED=true
IRC_SERVER=irc.libera.chat  # or irc.oftc.net, irc.rizon.net
IRC_CHANNEL=#karmacadabra-logs
IRC_NICK=facilitator-prod
IRC_PASSWORD=<optional_nickserv_password>
```

#### Option B: Separate Log Forwarder (Alternative)

Less invasive, but requires parsing logs:

```rust
// Separate binary that reads logs and forwards to IRC
// NOT RECOMMENDED - adds complexity and lag
```

---

### 3. Python test-seller Implementation

For the Python test-seller, we can use the `irc` library:

```python
# requirements.txt
irc>=20.0.0  # Python IRC library

# irc_logging.py
import logging
import irc.client
import irc.bot
from threading import Thread
from queue import Queue

class IRCLogHandler(logging.Handler):
    """Custom logging handler that sends logs to IRC channel"""

    def __init__(self, server, port, channel, nickname):
        super().__init__()
        self.server = server
        self.port = port
        self.channel = channel
        self.nickname = nickname
        self.queue = Queue()

        # Start IRC bot in background thread
        self.bot = IRCBot(channel, nickname, server, port, self.queue)
        self.thread = Thread(target=self.bot.start, daemon=True)
        self.thread.start()

    def emit(self, record):
        msg = self.format(record)
        # Add to queue (non-blocking)
        self.queue.put(msg)

class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port, queue):
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port)], nickname, nickname
        )
        self.channel = channel
        self.queue = queue

    def on_welcome(self, connection, event):
        connection.join(self.channel)
        # Start sending queued messages
        self.connection.execute_every(0.5, self._send_queued_messages)

    def _send_queued_messages(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self.connection.privmsg(self.channel, msg)

# Usage in main.py
if os.getenv("IRC_ENABLED"):
    irc_handler = IRCLogHandler(
        server=os.getenv("IRC_SERVER", "irc.libera.chat"),
        port=6667,
        channel=os.getenv("IRC_CHANNEL", "#karmacadabra-logs"),
        nickname="test-seller"
    )
    irc_handler.setLevel(logging.INFO)
    logger.addHandler(irc_handler)
```

---

## 4. IRC Server Options

### Public IRC Networks

| Network | Server | Port | TLS | Notes |
|---------|--------|------|-----|-------|
| Libera.Chat | irc.libera.chat | 6697 | ✅ | FOSS projects, good uptime |
| OFTC | irc.oftc.net | 6697 | ✅ | Debian/FOSS focused |
| Rizon | irc.rizon.net | 6697 | ✅ | General purpose |

**Recommendation**: **Libera.Chat** - most popular for tech/FOSS projects

### Self-Hosted Option (Advanced)

Run your own IRC server (e.g., InspIRCd, UnrealIRCd):

**Pros:**
- ✅ Full control, no rate limits
- ✅ Private, secure
- ✅ Can integrate with internal tools

**Cons:**
- ❌ Maintenance burden
- ❌ Additional infrastructure cost
- ❌ Overkill for this use case

**Verdict**: Use public network initially, self-host only if needed

---

## 5. Security Considerations

### Data Sanitization (CRITICAL)

**NEVER send to IRC:**
- ❌ Private keys (even partial)
- ❌ API keys / tokens
- ❌ Full wallet addresses (use first 10 chars: `0x2C3...`)
- ❌ User PII (unless explicitly consented)

**Sanitization filter:**

```rust
fn sanitize_log_message(msg: &str) -> String {
    let mut sanitized = msg.to_string();

    // Redact private keys
    sanitized = regex::Regex::new(r"0x[a-fA-F0-9]{64}")
        .unwrap()
        .replace_all(&sanitized, "0x[REDACTED]")
        .to_string();

    // Redact API keys
    sanitized = regex::Regex::new(r"sk-proj-[A-Za-z0-9_-]+")
        .unwrap()
        .replace_all(&sanitized, "sk-[REDACTED]")
        .to_string();

    // Truncate long addresses
    sanitized = regex::Regex::new(r"(0x[a-fA-F0-9]{10})[a-fA-F0-9]{30,}")
        .unwrap()
        .replace_all(&sanitized, "$1...")
        .to_string();

    sanitized
}
```

### Channel Security

**Option 1: Public channel** (e.g., #karmacadabra-logs)
- ✅ Easy for team to join
- ⚠️ Logs are public (ensure sanitization)

**Option 2: Private channel** (invite-only)
- ✅ More secure
- ❌ Requires channel registration + invite management

**Recommendation**: Start with **invite-only channel**, register with ChanServ:

```
/msg ChanServ REGISTER #karmacadabra-logs
/msg ChanServ SET #karmacadabra-logs PRIVATE ON
/msg ChanServ ACCESS #karmacadabra-logs ADD <your_nick> +AFRefiorstv
```

---

## 6. Filtering and Rate Limiting

### Log Level Filter

**DO send to IRC:**
- ✅ ERROR (all errors)
- ✅ WARN (warnings)
- ✅ INFO (important events only - payment settlements, health checks)

**DO NOT send:**
- ❌ DEBUG (too verbose)
- ❌ TRACE (internal library logs)

### Rate Limiting

**Problem**: IRC servers kick bots that flood (typically >5 msgs/sec)

**Solution**: Message queue with rate limiter

```rust
// Rate limit: 1 message per 500ms = 2 msgs/sec (safe)
tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
```

**Burst handling**: Queue up to 100 messages, drop oldest if full

```rust
if queue.len() > 100 {
    queue.pop_front();  // Drop oldest message
    tracing::warn!("IRC queue full, dropping oldest message");
}
```

### Message Truncation

IRC message limit: **510 bytes** (including protocol overhead)

```rust
fn truncate_irc_message(msg: &str) -> String {
    const MAX_LEN: usize = 400;  // Leave room for channel name + protocol
    if msg.len() <= MAX_LEN {
        msg.to_string()
    } else {
        format!("{}... (truncated)", &msg[..MAX_LEN])
    }
}
```

---

## 7. Operational Workflow

### Normal Operation

```
[Facilitator] → [Tracing Event] → [IRC Layer] → [Queue] → [IRC Bot] → [#karmacadabra-logs]
                                      ↓
                                 [Console Log]  (still enabled)
                                      ↓
                                 [CloudWatch]   (still enabled)
```

**IRC is ADDITIVE, not replacement** - console + CloudWatch continue working

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| IRC server down | Logs queue up, then drop | Continue console/CloudWatch, retry connection |
| Network partition | Same as above | Same |
| Bot kicked (flood) | Reconnect with backoff | Rate limiting prevents this |
| Channel invite revoked | Bot can't send | Alert via console log |

**Graceful degradation**: IRC is optional, service continues if IRC fails

---

## 8. Example IRC Session

```
14:32:15 <facilitator-prod> [INFO] x402_rs::handlers - Health check from 203.0.113.45
14:32:47 <facilitator-prod> [INFO] x402_rs::handlers - Payment verification started - Payer: 0x2C3...
14:32:48 <facilitator-prod> [INFO] x402_rs::chain::evm - Calling transferWithAuthorization on base network
14:32:49 <facilitator-prod> [INFO] x402_rs::handlers - Payment settled - TX: 0xabc123...
14:33:02 <test-seller> [INFO] main - [SUCCESS] Payment settled - TX: 0xabc123... - Payer: 0x2C3...
14:35:12 <facilitator-prod> [ERROR] x402_rs::chain::evm - RPC timeout for base network, trying backup
14:35:13 <facilitator-prod> [INFO] x402_rs::chain::evm - Backup RPC succeeded
```

**Use case**: During live stream, you can watch this channel to show real-time activity without exposing CloudWatch console

---

## 9. Implementation Roadmap

### Phase 1: Proof of Concept (2-4 hours)

- [ ] Add `irc = "1.0.0"` to x402-rs/Cargo.toml
- [ ] Create `src/irc_layer.rs` with basic implementation
- [ ] Test locally with IRC server (e.g., Libera.Chat)
- [ ] Verify rate limiting and message formatting

**Test command:**
```bash
cd x402-rs
cargo build
IRC_ENABLED=true IRC_SERVER=irc.libera.chat IRC_CHANNEL=#test-karmacadabra cargo run
```

Join #test-karmacadabra with IRC client and verify logs appear.

### Phase 2: Production Integration (2-3 hours)

- [ ] Register #karmacadabra-logs channel on Libera.Chat
- [ ] Set up invite-only mode
- [ ] Add sanitization filter for sensitive data
- [ ] Update ECS task definition with IRC env vars
- [ ] Deploy to staging facilitator first
- [ ] Monitor for 24h, verify no performance impact

### Phase 3: test-seller Integration (1-2 hours)

- [ ] Add IRC logging handler to test-seller Python code
- [ ] Deploy to test-seller ECS service
- [ ] Verify both services logging to same channel

### Phase 4: Documentation and Monitoring (1 hour)

- [ ] Document IRC setup in DEPLOYMENT.md
- [ ] Add IRC monitoring to runbooks
- [ ] Create alerts for IRC bot disconnections (optional)

**Total estimated effort**: 6-10 hours

---

## 10. Cost Analysis

### Infrastructure Costs

**Using Public IRC (Libera.Chat)**: **$0/month** ✅

**Self-hosted IRC server**:
- EC2 t3.micro: ~$7.50/month
- NOT RECOMMENDED unless privacy requirements change

### Developer Time Investment

**Initial setup**: 6-10 hours
**Ongoing maintenance**: ~30 min/month (monitoring, updates)

**ROI**: Saves 5-10 min per debugging session × 50 sessions/month = **4-8 hours/month saved**

**Payback period**: ~1 month

---

## 11. Alternatives Considered

### Alternative 1: CloudWatch Live Tail

**Pros:**
- ✅ Built into AWS
- ✅ No additional dependencies

**Cons:**
- ❌ Requires AWS credentials (not shareable during live streams)
- ❌ 3-10s delay
- ❌ Clunky UI for multi-service monitoring
- ❌ Can't collaborate with team in real-time

**Verdict**: Not a replacement for IRC real-time visibility

### Alternative 2: Slack/Discord Webhooks

**Pros:**
- ✅ Modern UI
- ✅ Mobile apps

**Cons:**
- ❌ Rate limits (1 msg/sec for free tier)
- ❌ Vendor lock-in
- ❌ Privacy concerns (logs sent to third party)
- ❌ More complex authentication

**Verdict**: IRC is simpler, faster, and more battle-tested for log streaming

### Alternative 3: Grafana Loki

**Pros:**
- ✅ Purpose-built for log aggregation
- ✅ Beautiful dashboards

**Cons:**
- ❌ Heavy infrastructure (needs Loki + Grafana + Promtail)
- ❌ Overkill for current scale
- ❌ Higher maintenance burden

**Verdict**: Good for future (10+ services), but IRC suffices for now

---

## 12. Recommendation and Next Steps

### ✅ PROCEED WITH IRC LOGGING

**Recommended Implementation:**
1. **Phase 1 (Week 1)**: Proof of concept for x402-rs facilitator
2. **Phase 2 (Week 2)**: Production deployment + monitoring
3. **Phase 3 (Week 3)**: Extend to test-seller and other agents (optional)

### Environment Setup

```bash
# Add to x402-rs/.env (production via AWS Secrets Manager)
IRC_ENABLED=true
IRC_SERVER=irc.libera.chat
IRC_PORT=6697
IRC_TLS=true
IRC_CHANNEL=#karmacadabra-logs
IRC_NICK=facilitator-prod
```

### Success Criteria

- ✅ Logs appear in IRC within 1 second of emission
- ✅ No sensitive data leaked to IRC
- ✅ No performance degradation (<5ms overhead per log)
- ✅ Bot maintains connection for >24h without manual intervention
- ✅ Rate limiting prevents flood kicks

### Monitoring

Add to monitoring dashboard:
- IRC bot connection status
- IRC message send failures
- Queue depth (alert if >50 messages)

---

## 13. FAQ

**Q: Will this slow down the facilitator?**
A: No. IRC sending is async and non-blocking. Logs are queued in-memory and sent by background task.

**Q: What if IRC server goes down?**
A: Logs continue to console + CloudWatch. IRC layer fails gracefully.

**Q: Can we use this during live streams?**
A: YES - this is the primary use case. IRC doesn't expose AWS credentials.

**Q: How do we prevent log spam?**
A: Filter to INFO/WARN/ERROR only, rate limit to 2 msg/sec, queue with max depth.

**Q: What about log retention?**
A: IRC doesn't replace CloudWatch. For long-term retention, use CloudWatch (already configured).

**Q: Can multiple services log to same channel?**
A: YES. Each service connects with different nickname (facilitator-prod, test-seller-prod, etc.)

---

## Conclusion

IRC logging is a **proven, lightweight, cost-effective** solution for real-time monitoring of Rust microservices. The Rust ecosystem has mature libraries (`irc` crate), and integration with `tracing-subscriber` is straightforward.

**Next action**: Proceed with Phase 1 proof of concept (4 hours). If successful, roll out to production within 2 weeks.

**References:**
- `irc` crate: https://crates.io/crates/irc
- `tracing-subscriber` custom layers: https://burgers.io/custom-logging-in-rust-using-tracing
- Libera.Chat network: https://libera.chat/

---

**Document prepared by**: Claude Code
**Review status**: Draft - pending approval
**Last updated**: 2025-10-31
