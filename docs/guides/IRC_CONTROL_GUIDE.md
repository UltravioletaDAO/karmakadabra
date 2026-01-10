# IRC Control Plane for Karmacadabra

Control your entire agent fleet from IRC. Send commands, receive telemetry, halt/resume agents, and coordinate multi-agent operations in real-time.

## Architecture

```
TU (0xUltraVeleta)
     │
     │  IRC Client (weechat, irssi, HexChat)
     ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐
│   IRC Server    │────▶│   uvd_commander  │────▶│      Redis Streams          │
│  (libera.chat   │     │   (IRC Bot)      │     │  uvd:tasks (entrada)        │
│   o propio)     │◀────│                  │◀────│  uvd:results (salida)       │
└─────────────────┘     └──────────────────┘     └─────────────────────────────┘
         │                                                    │
         │  #karma-cabra                                      │
         │  #karma-cabra-alerts                               ▼
         ▼                                       ┌─────────────────────────────┐
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENT FLEET                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ karma-hello │  │ abracadabra │  │  validator  │  │skill-extract│         │
│  │   :9002     │  │   :9003     │  │   :9001     │  │   :9004     │         │
│  │ IRCMixin    │  │ IRCMixin    │  │ IRCMixin    │  │ IRCMixin    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                                              │
│  ECS Fargate (karmacadabra-prod)                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Generate HMAC Secret

```bash
python scripts/irc_sign.py --generate-secret
# Output: abc123def456...
# Save this securely!
```

### 2. Configure Environment

Create `.env.irc`:
```bash
IRC_HMAC_SECRET=your-secret-here
IRC_SERVER=irc.libera.chat
IRC_PORT=6667
IRC_NICK=uvd_commander
IRC_CHANNELS=#karma-cabra
IRC_PRIVILEGED_USERS=0xUltraVeleta
```

### 3. Start Infrastructure

```bash
# Development (local)
docker-compose -f docker-compose.yml -f docker-compose.irc.yml up -d

# Or just IRC infrastructure
docker-compose -f docker-compose.irc.yml up redis irc-commander -d
```

### 4. Connect to IRC

```
/server irc.libera.chat
/join #karma-cabra
```

### 5. Sign and Send Commands

```bash
# Sign a command
python scripts/irc_sign.py "!ping agent:all"

# Copy output to IRC:
# !ping agent:all |sig=a1b2c3d4e5f6...
```

## Commands Reference

### Public Commands (No Signature Required)

| Command | Description |
|---------|-------------|
| `!agents` | List all online agents with heartbeat status |
| `!help` | Show available commands |

### Signed Commands

All commands below require `|sig=<hmac>` suffix.

| Command | Syntax | Description |
|---------|--------|-------------|
| `!ping` | `!ping <target> \|sig=...` | Ping agents, verify connectivity |
| `!status` | `!status <target> \|sig=...` | Get agent status and metrics |
| `!balance` | `!balance <target> \|sig=...` | Check wallet balance |
| `!dispatch` | `!dispatch <target> <action> <json> \|sig=...` | Send custom command |
| `!halt` | `!halt <target> \|sig=...` | Pause agent task processing |
| `!resume` | `!resume <target> \|sig=...` | Resume paused agent |

### Target Patterns

| Pattern | Matches |
|---------|---------|
| `agent:karma-hello` | Specific agent by ID |
| `agent:all` | All agents |
| `karma-cabra:all` | All Karmacadabra agents |
| `role:validator` | Agents with "validator" role |
| `role:seller` | Agents with "seller" role |
| `group:extractors` | Agent group |

### Examples

```irc
# List online agents
!agents

# Ping all agents
!ping agent:all |sig=abc123...

# Get karma-hello status
!status karma-hello |sig=abc123...

# Check validator balance
!balance validator |sig=abc123...

# Send custom summarize command
!dispatch karma-hello summarize {"stream_id":"2026-01-08","max":20} |sig=abc123...

# Halt all agents (emergency)
!halt karma-cabra:all |sig=abc123...

# Resume after halt
!resume karma-cabra:all |sig=abc123...
```

## Command Signing

### Using the CLI Tool

```bash
# Interactive mode (recommended)
python scripts/irc_sign.py --interactive

# Single command
python scripts/irc_sign.py "!dispatch validator validate {}"

# With custom secret
python scripts/irc_sign.py -s "your-secret" "!ping agent:all"
```

### Programmatic Signing

```python
from shared.irc_protocol import format_signed_command

secret = "your-hmac-secret"
raw = "!dispatch karma-hello summarize {}"
signed = format_signed_command(raw, secret)
print(signed)  # !dispatch karma-hello summarize {} |sig=abc123...
```

## Agent Integration

### Pattern 1: Mixin (Recommended)

```python
from shared.base_agent import ERC8004BaseAgent
from shared.irc_control import IRCControlMixin

class MyAgent(ERC8004BaseAgent, IRCControlMixin):
    def __init__(self, config):
        super().__init__(
            agent_name="my-agent",
            agent_domain="my-agent.karmacadabra.ultravioletadao.xyz",
            ...
        )

        # Initialize IRC control
        self.init_irc_control(
            agent_id="my-agent",
            roles=["seller", "extractor"],
            redis_url="redis://localhost:6379/0",
        )

        # Register custom handlers
        self.register_irc_handler("my_action", self.handle_my_action)

    async def handle_my_action(self, task):
        # Process command
        result = do_something(task.payload)

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output=result,
        )

    async def run(self):
        # Start IRC worker in background
        asyncio.create_task(self.start_irc_worker())

        # Start HTTP server
        await self.start_server()
```

### Pattern 2: Decorator

```python
from shared.irc_control import IRCControlMixin, irc_handler, register_irc_handlers

class MyAgent(ERC8004BaseAgent, IRCControlMixin):
    def __init__(self, config):
        super().__init__(...)
        self.init_irc_control(agent_id="my-agent", roles=["seller"])
        register_irc_handlers(self)  # Auto-register decorated methods

    @irc_handler("summarize")
    async def handle_summarize(self, task):
        # Handler for !dispatch my-agent summarize {...}
        return TaskResult(...)

    @irc_handler("ingest")
    async def handle_ingest(self, task):
        # Handler for !dispatch my-agent ingest {...}
        return TaskResult(...)
```

### Built-in Handlers

Every agent with `IRCControlMixin` automatically responds to:

| Action | Description |
|--------|-------------|
| `ping` | Returns pong with timestamp |
| `status` | Returns agent status (override `get_agent_status()` for custom data) |
| `health` | Returns health check info |
| `halt` | Pauses task processing |
| `resume` | Resumes task processing |
| `balance` | Returns wallet balance (requires ERC8004BaseAgent) |

### Custom Status

```python
class MyAgent(ERC8004BaseAgent, IRCControlMixin):
    def get_agent_status(self):
        """Override to provide custom status info"""
        return {
            "logs_processed": self.logs_count,
            "queue_size": len(self.queue),
            "last_sale": self.last_sale_timestamp,
        }
```

## Security Model

### HMAC Signatures

All commands (except `!agents` and `!help`) require HMAC-SHA256 signature:

```
Raw:    !dispatch agent:all ping {}
Secret: your-secret-here
Sig:    hmac_sha256(secret, raw) = abc123...
Final:  !dispatch agent:all ping {} |sig=abc123...
```

### Rate Limiting

- Default: 20 requests per 60 seconds per user
- Configurable via `IRC_RATE_LIMIT` and `IRC_RATE_WINDOW`

### User Permissions

```bash
# Allow only specific users
IRC_ALLOWED_USERS=0xUltraVeleta,trusted_user

# Privileged users (can use !halt, !resume)
IRC_PRIVILEGED_USERS=0xUltraVeleta
```

### Privileged Commands

These require user to be in `IRC_PRIVILEGED_USERS`:
- `!halt`
- `!resume`
- `!dispatch` (with certain actions)

## Redis Streams

### Stream Names

| Stream | Purpose |
|--------|---------|
| `uvd:tasks` | Commands from IRC to agents |
| `uvd:results` | Results from agents to IRC |
| `uvd:events` | Agent events (halt, resume, errors) |

### Heartbeat Keys

```
uvd:agent:hb:karma-hello = 1736419200 (Unix timestamp)
uvd:agent:hb:validator = 1736419195
```

TTL: 120 seconds. Stale = no heartbeat in 60+ seconds.

### Manual Testing

```bash
# List online agents
redis-cli KEYS "uvd:agent:hb:*"

# Send a ping task
redis-cli XADD uvd:tasks '*' \
  task_id ping-test-1 \
  target agent:all \
  action ping \
  payload '{}' \
  sender manual-test \
  ttl_sec 30 \
  created_at $(date +%s) \
  nonce test123

# Read results
redis-cli XRANGE uvd:results - +
```

## Docker Deployment

### docker-compose.irc.yml

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  irc-commander:
    build:
      dockerfile: Dockerfile.irc-commander
    depends_on:
      - redis
    environment:
      - IRC_SERVER=${IRC_SERVER}
      - IRC_NICK=${IRC_NICK}
      - IRC_CHANNELS=${IRC_CHANNELS}
      - IRC_HMAC_SECRET=${IRC_HMAC_SECRET}
      - REDIS_URL=redis://redis:6379/0
```

### Start Commands

```bash
# Full stack with IRC
docker-compose -f docker-compose.yml -f docker-compose.irc.yml up -d

# IRC only
docker-compose -f docker-compose.irc.yml up -d

# View commander logs
docker logs -f karmacadabra-irc-commander
```

## ECS Fargate Deployment

### Task Definition Addition

Add to each agent's task definition:

```json
{
  "environment": [
    {"name": "REDIS_URL", "value": "redis://your-elasticache:6379/0"},
    {"name": "IRC_ENABLED", "value": "true"}
  ]
}
```

### ElastiCache Setup

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id karmacadabra-irc \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-nodes 1 \
  --region us-east-1
```

## Troubleshooting

### Commander Not Connecting

```bash
# Check IRC logs
docker logs karmacadabra-irc-commander

# Verify Redis
redis-cli ping  # Should return PONG

# Check environment
docker exec karmacadabra-irc-commander env | grep IRC
```

### Agents Not Responding

```bash
# Check agent has IRC enabled
docker logs karmacadabra-karma-hello | grep IRC

# Check heartbeats
redis-cli KEYS "uvd:agent:hb:*"

# Check for stale heartbeats
redis-cli GET uvd:agent:hb:karma-hello
```

### Invalid Signature

```bash
# Verify secret matches
echo $IRC_HMAC_SECRET

# Re-sign command
python scripts/irc_sign.py "!ping agent:all"
```

### Rate Limited

Wait 60 seconds or adjust limits:
```bash
IRC_RATE_LIMIT=50
IRC_RATE_WINDOW=60
```

## Files Reference

| File | Description |
|------|-------------|
| `shared/irc_protocol.py` | Protocol definitions, signatures, message formats |
| `shared/irc_control.py` | Agent mixin for IRC capabilities |
| `shared/irc_commander.py` | IRC bot that bridges to Redis |
| `shared/irc_integration_example.py` | Integration examples and demo |
| `scripts/irc_sign.py` | CLI tool for signing commands |
| `docker-compose.irc.yml` | Docker Compose for IRC infrastructure |
| `Dockerfile.irc-commander` | Docker image for commander |

## Future Enhancements

- [ ] WebSocket bridge for web UI
- [ ] Prometheus metrics export
- [ ] Command history and audit log
- [ ] Agent-to-agent messaging via IRC
- [ ] Scheduled commands (cron-like)
- [ ] Multi-channel routing (#alerts, #logs)
