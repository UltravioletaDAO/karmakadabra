# Quick Start: IRC Logging on DALnet

**Target**: `#karmacadabra` on `irc.dal.net`

---

## ⚡ 5-Minute Test

### Step 1: Join #karmacadabra on DALnet

**Option A: Web Client (Easiest)**
1. Open: https://kiwiirc.com/nextclient/irc.dal.net/#karmacadabra
2. Enter a nickname
3. You're in #karmacadabra!

**Option B: HexChat (Windows)**
1. Download: https://hexchat.github.io/downloads.html
2. Open HexChat
3. Add network: `irc.dal.net`
4. Connect and `/join #karmacadabra`

**Option C: mIRC (Windows)**
1. `/server irc.dal.net`
2. `/join #karmacadabra`

**Option D: WeeChat (Linux/Mac)**
```bash
weechat
/server add dalnet irc.dal.net/6697 -ssl
/connect dalnet
/join #karmacadabra
```

### Step 2: Run the POC

**Windows (PowerShell):**
```powershell
cd Z:\ultravioleta\dao\karmacadabra\docs\irc-logging-poc
.\test.ps1
```

**Linux/Mac:**
```bash
cd /mnt/z/ultravioleta/dao/karmacadabra/docs/irc-logging-poc
./test.sh
```

### Step 3: Watch Logs Appear

In your IRC client (#karmacadabra), you should see:

```
<x402-poc> [INFO] irc_logging_poc - Event at src/main.rs:195
<x402-poc> [INFO] irc_logging_poc - Event at src/main.rs:203
<x402-poc> [WARN] irc_logging_poc - Event at src/main.rs:204
<x402-poc> [INFO] irc_logging_poc - Event at src/main.rs:207
<x402-poc> [ERROR] irc_logging_poc - Event at src/main.rs:216
```

**Success!** 🎉 Logs are streaming to IRC in real-time.

---

## 🔧 Customization

### Change Nickname

```bash
IRC_ENABLED=true IRC_NICK=my-bot cargo run
```

### Test on Different Channel

```bash
IRC_ENABLED=true IRC_CHANNEL=#test-channel cargo run
```

### Disable TLS (not recommended)

```bash
IRC_ENABLED=true IRC_TLS=false cargo run
```

---

## 🚀 Next: Integrate into x402-rs Facilitator

Once POC works, integrate into production facilitator:

### 1. Add Dependency

Edit `x402-rs/Cargo.toml`:
```toml
[dependencies]
irc = "1.0.0"
```

### 2. Copy IRC Layer Code

Copy from `docs/irc-logging-poc/src/main.rs`:
- `sanitize_message()` function
- `truncate_irc_message()` function
- `IrcLayer` struct
- `irc_sender_task()` function

Paste into `x402-rs/src/telemetry.rs`

### 3. Update Telemetry Registration

In `x402-rs/src/telemetry.rs`, modify the `register()` function to include IRC layer (see full code in `docs/IRC_LOGGING_ANALYSIS.md`)

### 4. Configure ECS Task Definition

Add environment variables to `facilitator-task-def-mainnet.json`:

```json
{
  "name": "IRC_ENABLED",
  "value": "true"
},
{
  "name": "IRC_SERVER",
  "value": "irc.dal.net"
},
{
  "name": "IRC_CHANNEL",
  "value": "#karmacadabra"
},
{
  "name": "IRC_NICK",
  "value": "facilitator-prod"
},
{
  "name": "IRC_TLS",
  "value": "true"
}
```

### 5. Deploy

```bash
cd x402-rs
docker build -t x402-facilitator:latest .

# Push to ECR and update ECS (existing deployment process)
```

### 6. Verify

Join #karmacadabra and watch for messages from `facilitator-prod`:

```
<facilitator-prod> [INFO] x402_rs::handlers - Health check from 203.0.113.45
<facilitator-prod> [INFO] x402_rs::handlers - Payment verification started
<facilitator-prod> [INFO] x402_rs::chain::evm - Calling transferWithAuthorization
<facilitator-prod> [INFO] x402_rs::handlers - Payment settled - TX: 0xabc...
```

---

## 🐛 Troubleshooting

### POC doesn't connect to IRC

**Check firewall:**
```bash
telnet irc.dal.net 6667
# Should connect successfully
```

**Try without TLS:**
```bash
IRC_ENABLED=true IRC_TLS=false cargo run
```

### Bot connects but doesn't send messages

**Check channel name has # prefix:**
```bash
IRC_CHANNEL=#karmacadabra  # Correct
IRC_CHANNEL=karmacadabra   # Wrong - missing #
```

**Check you're on the right network:**
- Make sure your IRC client is connected to `irc.dal.net`
- Not `irc.libera.chat` or other networks

### Messages appear delayed

**Normal**: Rate limiting is 500ms per message (2 msg/sec)

This prevents IRC flood kicks and is working as designed.

### Build errors

**Missing dependencies:**
```bash
cargo clean
cargo build
```

**Rust version:**
```bash
rustc --version
# Should be 1.70+ (edition 2021 support)
```

---

## 📊 DALnet-Specific Notes

### Server Info
- **Network**: DALnet (since 1994)
- **Server**: irc.dal.net (round-robin to closest server)
- **Ports**: 6667 (plain), 6697 (SSL/TLS)
- **Website**: https://www.dal.net/

### Channel Registration

If #karmacadabra isn't registered, you can register it:

```
/msg ChanServ REGISTER #karmacadabra <password>
/msg ChanServ SET #karmacadabra MLOCK +nt
/msg ChanServ SET #karmacadabra DESC Karmacadabra infrastructure logs
```

### Recommended Channel Modes

```
/mode #karmacadabra +nt
```

Explanation:
- `+n` = No external messages (only joined users can send)
- `+t` = Topic protection (only ops can change)

Optional for private logs:
```
/mode #karmacadabra +i
```
- `+i` = Invite-only (more secure for production logs)

---

## 🎯 Success Criteria

After running the POC, you should verify:

- ✅ Bot connects to irc.dal.net
- ✅ Bot joins #karmacadabra
- ✅ Messages appear in channel within 1 second
- ✅ Private keys are sanitized (`0x[REDACTED_KEY]`)
- ✅ Long addresses are truncated (`0x2C3...`)
- ✅ Rate limiting works (no flood kick)
- ✅ Console logs still work (IRC is additive)

---

## 📚 Reference Files

- **Full analysis**: `../IRC_LOGGING_ANALYSIS.md` (9,600 words)
- **POC code**: `src/main.rs` (200 lines, fully commented)
- **README**: `README.md` (setup and troubleshooting)
- **Summary**: `../../IRC_LOGGING_SUMMARY.md` (executive summary)

---

**Ready?** Run `.\test.ps1` (Windows) or `./test.sh` (Linux/Mac) and join #karmacadabra! 🚀
