# Troubleshooting: #karmacadabra on DALnet

**Issue**: Bot connects but no messages appear in channel

---

## Common Causes & Fixes

### 1. Channel Doesn't Exist

**Problem**: #karmacadabra might not exist on DALnet yet

**Check**:
```
# In your IRC client connected to irc.dal.net
/list #karmacadabra
```

**If channel doesn't exist, create it:**
```
# In your IRC client
/join #karmacadabra
/topic #karmacadabra Karmacadabra infrastructure logs (x402-rs facilitator, test-seller)
```

**Register the channel** (optional but recommended):
```
/msg ChanServ REGISTER #karmacadabra <password> <description>
```

---

### 2. Channel Modes Block Unregistered Users

**Problem**: Channel has +m (moderated) or +n (no external messages) mode

**Check current modes**:
```
/mode #karmacadabra
```

**Fix** (if you're channel op):
```
/mode #karmacadabra -m   # Remove moderated mode
/mode #karmacadabra +nt  # Standard modes (no external msgs, topic protection)
```

**Give bot voice** (if channel is +m moderated):
```
/mode #karmacadabra +v x402-poc
```

---

### 3. Bot Nickname is Banned

**Problem**: Nickname 'x402-poc' might be banned

**Check**:
```
/mode #karmacadabra +b
# Shows ban list
```

**Fix - Try different nickname**:
```bash
IRC_ENABLED=true IRC_NICK=facilitator-test cargo run --release
```

---

### 4. DALnet NickServ Registration Required

**Problem**: DALnet might require nickname registration for some channels

**Register nickname** (in IRC client):
```
/msg NickServ REGISTER <password> <email>
/msg NickServ IDENTIFY <password>
```

**Then configure bot to use password**:
```rust
// In POC code, add to config:
password: Some("your_password".to_string()),
```

---

### 5. Network/Firewall Issues

**Problem**: Outbound connection blocked

**Test connectivity**:
```bash
# Test plain connection
telnet irc.dal.net 6667

# Test TLS connection
openssl s_client -connect irc.dal.net:6697
```

**If TLS fails, try without**:
```bash
IRC_ENABLED=true IRC_TLS=false cargo run --release
```

---

### 6. You're on Wrong Network

**Problem**: Your IRC client is on different network

**Verify** (in IRC client):
```
/server
# Should show: irc.dal.net or similar
```

**Reconnect to DALnet**:
```
/disconnect
/server irc.dal.net
/join #karmacadabra
```

---

## Debugging Steps

### Step 1: Verify Bot Output

Run POC and look for these lines:

**Good - Bot connected:**
```
IRC logging enabled: irc.dal.net:#karmacadabra as x402-poc
INFO irc_logging_poc: Connected to IRC server, identifying...
INFO irc_logging_poc: Successfully connected to IRC channel: #karmacadabra
[IRC->#karmacadabra] IRC logging initialized
[IRC->#karmacadabra] [INFO] Starting IRC logging proof of concept...
```

**Bad - Connection failed:**
```
ERROR irc_logging_poc: IRC connection failed: <error>, retrying in 30s
```

**Bad - Channel doesn't exist:**
```
ERROR irc_logging_poc: Failed to send initial message to IRC: <error>
ERROR irc_logging_poc: Channel might not exist or bot might be banned
```

### Step 2: Check Your IRC Client

**Verify you're in the channel:**
```
/names #karmacadabra
# Should show: yourname, x402-poc
```

**If you don't see x402-poc:**
- Bot might not have joined yet
- Channel might have join restrictions
- Bot might be using different channel name (check IRC_CHANNEL env var)

### Step 3: Test with Different Channel

**Create test channel first:**
```
# In IRC client
/join #test-karmacadabra-yourname
```

**Run bot with test channel:**
```bash
IRC_ENABLED=true IRC_CHANNEL=#test-karmacadabra-yourname cargo run --release
```

**If this works**, the problem is with #karmacadabra specifically (modes, bans, etc.)

---

## Quick Verification Test

**Terminal 1 - Start bot:**
```bash
cd docs/irc-logging-poc
IRC_ENABLED=true IRC_CHANNEL=#test-$(whoami) cargo run --release
```

**Terminal 2 - Join with IRC client:**
```bash
# Using weechat
weechat
/server add dalnet irc.dal.net/6697 -ssl
/connect dalnet
/join #test-yourname
```

**You should see:**
1. Bot joins: `x402-poc has joined #test-yourname`
2. Bot message: `<x402-poc> IRC logging initialized`
3. Log messages: `<x402-poc> [INFO] Processing request #1`

---

## Manual IRC Test (No Code)

**Verify DALnet connection works at all:**

```bash
# Connect manually
telnet irc.dal.net 6667
```

**Type these commands** (replace NICKNAME with your test name):
```
NICK testbot123
USER testbot 0 * :Test Bot
JOIN #karmacadabra
PRIVMSG #karmacadabra :Test message from manual connection
QUIT :Bye
```

**If you see errors**, DALnet might be having issues or blocking you.

---

## Known DALnet Quirks

### Registration Enforcement

Some DALnet servers enforce nickname registration for certain channels.

**Fix**: Register your bot nickname first
```
/msg NickServ REGISTER password email@example.com
```

### Anti-Spam Measures

DALnet has aggressive anti-spam. If bot sends too fast:

**Symptoms:**
- Messages don't appear
- Bot gets kicked/banned silently

**Fix**: Already implemented in POC (500ms rate limit)

### Channel Linking

#karmacadabra might be linked to another channel.

**Check**:
```
/msg ChanServ INFO #karmacadabra
```

---

## Alternative: Create Your Own Channel

**If #karmacadabra has restrictions you can't fix:**

1. **Create new channel:**
   ```
   /join #karmacadabra-logs
   ```

2. **Set permissive modes:**
   ```
   /mode #karmacadabra-logs +nt
   ```

3. **Update POC:**
   ```bash
   IRC_CHANNEL=#karmacadabra-logs cargo run --release
   ```

4. **Register it:**
   ```
   /msg ChanServ REGISTER #karmacadabra-logs password description
   ```

---

## Still Not Working?

### Try Different IRC Network

**Libera.Chat** (more lenient for bots):
```bash
IRC_SERVER=irc.libera.chat IRC_CHANNEL=#karmacadabra-test cargo run --release
```

**Rizon** (very bot-friendly):
```bash
IRC_SERVER=irc.rizon.net IRC_CHANNEL=#karmacadabra cargo run --release
```

### Enable Debug Logging

**Modify POC to show IRC protocol:**
```bash
# In main.rs, before running bot:
env_logger::init();
RUST_LOG=debug cargo run --release
```

### Contact DALnet Support

If nothing works:
- DALnet website: https://www.dal.net/
- Support channel: `/join #DALnet` on irc.dal.net
- Ask if #karmacadabra exists and what restrictions it has

---

## Success Checklist

When everything works, you should see:

- [x] Bot connects: "Connected to IRC server, identifying..."
- [x] Bot joins: "Successfully connected to IRC channel: #karmacadabra"
- [x] Initial message sent: "[IRC->#karmacadabra] IRC logging initialized"
- [x] Log messages appear: "[IRC->#karmacadabra] [INFO] Processing request #1"
- [x] In IRC client: You see `<x402-poc>` messages
- [x] In IRC client: `/names #karmacadabra` shows bot
- [x] Sanitization works: Private keys show as `[REDACTED_KEY]`

---

## Next Steps After Fix

Once working:

1. **Register channel permanently** (if owner):
   ```
   /msg ChanServ REGISTER #karmacadabra password Karmacadabra logs
   ```

2. **Set recommended modes**:
   ```
   /mode #karmacadabra +nt  # No external messages, topic protection
   ```

3. **Integrate into x402-rs** (see `X402_INTEGRATION_GUIDE.md`)

4. **Deploy to production** with nickname: `facilitator-prod`

---

**Most Common Fix**: Create the channel first in your IRC client, then run the bot!
