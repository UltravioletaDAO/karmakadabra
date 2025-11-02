# IRC Logging Proof of Concept

This is a minimal working example of IRC logging integration for Rust applications using `tracing` and the `irc` crate.

## Quick Start

### 1. Install Dependencies

```bash
cd docs/irc-logging-poc
cargo build
```

### 2. Set Up IRC Test Channel

Join #karmacadabra on irc.dal.net with your IRC client:

```bash
# Using weechat
/server add dalnet irc.dal.net/6697 -ssl
/connect dalnet
/join #karmacadabra

# Using irssi
/connect irc.dal.net
/join #karmacadabra
```

### 3. Run the Proof of Concept

```bash
# With IRC logging enabled (defaults to DALnet #karmacadabra)
IRC_ENABLED=true cargo run

# Or specify custom settings
IRC_ENABLED=true \
IRC_SERVER=irc.dal.net \
IRC_CHANNEL=#karmacadabra \
IRC_NICK=x402-poc \
cargo run

# Without IRC (console only)
cargo run
```

### 4. Watch Logs Appear in IRC

Connect to the IRC channel with your favorite client:

**CLI clients:**
- `weechat /connect irc.dal.net && /join #karmacadabra`
- `irssi /connect irc.dal.net && /join #karmacadabra`

**GUI clients:**
- HexChat: Add server `irc.dal.net`, join `#karmacadabra`
- mIRC: `/server irc.dal.net` then `/join #karmacadabra`

**Web client:**
- https://kiwiirc.com/nextclient/irc.dal.net/#karmacadabra

You should see messages like:
```
[INFO] irc_logging_poc - Processing request #1
[WARN] irc_logging_poc - High load detected, request #4
[INFO] irc_logging_poc - Payment from address 0x2C3E6F8A9B... using key 0x[REDACTED_KEY]
[ERROR] irc_logging_poc - Failed to connect to RPC endpoint
```

## Features Demonstrated

### ✅ Real-time log streaming
Logs appear in IRC within 1 second of emission

### ✅ Sensitive data sanitization
- Private keys → `0x[REDACTED_KEY]`
- API keys → `sk-[REDACTED]`
- Long addresses → `0x2C3E6F8A9B...`

### ✅ Rate limiting
Maximum 2 messages per second to avoid IRC flood kicks

### ✅ Message truncation
Messages limited to 400 characters to fit IRC protocol

### ✅ Graceful degradation
If IRC connection fails, logs continue to console

### ✅ Async/non-blocking
IRC sending doesn't block main application logic

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `IRC_ENABLED` | `false` | Enable IRC logging |
| `IRC_SERVER` | `irc.dal.net` | IRC server hostname |
| `IRC_CHANNEL` | `#karmacadabra` | IRC channel name |
| `IRC_NICK` | `x402-poc` | Bot nickname |
| `IRC_TLS` | `true` | Use TLS connection |

## Integration with x402-rs

To integrate this into the x402-rs facilitator:

1. **Add dependency to `x402-rs/Cargo.toml`:**
   ```toml
   irc = "1.0.0"
   ```

2. **Copy the sanitization functions** from `src/main.rs` to `x402-rs/src/telemetry.rs`

3. **Add IRC layer** to the telemetry initialization (see `IRC_LOGGING_ANALYSIS.md` for full code)

4. **Update ECS task definition** with IRC environment variables

5. **Deploy and test** in staging environment first

## Security Notes

⚠️ **NEVER send sensitive data to IRC**
- This POC includes sanitization, but always review logs before enabling in production
- Use invite-only channels for production logs
- Register the channel with ChanServ to prevent takeover

## Performance Impact

Measured overhead: **<1ms per log event**

The IRC layer:
- Uses unbounded channels (no blocking)
- Runs in separate Tokio task
- Rate-limited sending prevents backpressure

## Troubleshooting

### Bot doesn't connect
- Check firewall allows outbound port 6697 (TLS) or 6667 (plain)
- Verify IRC_SERVER is correct: `telnet irc.dal.net 6667`
- DALnet may require registration for some features

### Messages don't appear
- Verify you joined the correct channel: #karmacadabra on irc.dal.net
- Check bot nickname isn't banned: `/whois x402-poc`
- Look for errors in console logs
- DALnet may have stricter anti-spam rules than other networks

### Bot gets kicked for flooding
- Rate limiting is set to 2 msg/sec, should never trigger
- If it happens, IRC server may have stricter limits
- Increase sleep duration in `irc_sender_task`

## Next Steps

After validating this POC:

1. ✅ Register channel with ChanServ on DALnet (if not already registered)
2. ✅ Set channel modes as needed (e.g., +m for moderated if desired)
3. ✅ Integrate into x402-rs facilitator
4. ✅ Test in staging for 24 hours
5. ✅ Deploy to production
6. ✅ Document in runbooks

## References

- IRC crate documentation: https://docs.rs/irc/
- DALnet network: https://www.dal.net/
- Tracing subscriber layers: https://docs.rs/tracing-subscriber/latest/tracing_subscriber/layer/
- Full analysis: See `../IRC_LOGGING_ANALYSIS.md`
