# Docker Compose Guide

**Run the entire Karmacadabra agent stack with one command.**

---

## Quick Start

### Windows:
```bash
# Start all agents
scripts\docker-start.bat

# Or manually:
docker-compose up -d
```

### Linux/Mac:
```bash
# Start all agents
bash scripts/docker-start.sh

# Or manually:
docker-compose up -d
```

---

## What Gets Started

Running `docker-compose up` starts **5 agents**:

| Service | Port | Description |
|---------|------|-------------|
| **validator** | 9001 | Independent validation service using CrewAI |
| **karma-hello** | 9002 | Chat logs seller (0.01 GLUE base) |
| **abracadabra** | 9003 | Transcription seller (0.02 GLUE base) |
| **skill-extractor** | 9004 | Skill profiling (buys from karma-hello, sells profiles) |
| **voice-extractor** | 9005 | Personality profiling (buys from karma-hello, sells profiles) |

All agents communicate via internal Docker network: `karmacadabra`

---

## Prerequisites

### 1. Install Docker

**Windows**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
**Linux**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Mac**: [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

### 2. Create .env Files

Copy from examples:
```bash
# Windows
for %a in (validator karma-hello abracadabra skill-extractor voice-extractor) do copy agents\%a\.env.example agents\%a\.env

# Linux/Mac
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  cp agents/$agent/.env.example agents/$agent/.env
done
```

**Required in each .env:**
- `PRIVATE_KEY=` (leave empty to fetch from AWS Secrets Manager)
- `AGENT_ADDRESS=0x...` (your agent's public address)
- Contract addresses (already filled from deployment)
- OpenAI API key (optional, can use AWS Secrets Manager)

### 3. AWS Credentials (Optional but Recommended)

If using AWS Secrets Manager for private keys:

```bash
# Configure AWS CLI
aws configure

# Or create ~/.aws/credentials manually:
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
region = us-east-1
```

**Without AWS**: Set `PRIVATE_KEY=0x...` in each .env file (testing only)

### 4. Prepare Data Directories

Create sample data for local testing:
```bash
mkdir -p data/karma-hello data/abracadabra
```

Or use production databases (set `USE_LOCAL_FILES=false` in .env)

---

## Usage

### Start All Agents

```bash
# Production mode
docker-compose up -d

# Development mode (hot reload, verbose logs)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or use convenience scripts:
scripts/docker-start.bat        # Windows
bash scripts/docker-start.sh    # Linux/Mac
bash scripts/docker-start.sh dev  # Development mode
```

### Start Individual Agents

```bash
# Start only karma-hello
docker-compose up -d karma-hello

# Start karma-hello + skill-extractor (with dependencies)
docker-compose up -d skill-extractor
```

### View Logs

```bash
# All agents
docker-compose logs -f

# Single agent
docker-compose logs -f karma-hello

# Last 100 lines
docker-compose logs --tail=100 karma-hello

# Filter by keyword
docker-compose logs karma-hello | grep ERROR
```

### Check Status

```bash
# List running containers
docker-compose ps

# Health checks
curl http://localhost:9001/health  # validator
curl http://localhost:9002/health  # karma-hello
curl http://localhost:9003/health  # abracadabra
curl http://localhost:9004/health  # skill-extractor
curl http://localhost:9005/health  # voice-extractor

# Validator metrics
curl http://localhost:9090/metrics
```

### Stop Agents

```bash
# Stop all (keeps data)
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove everything including volumes (DELETES DATA!)
docker-compose down -v
```

### Restart Agent

```bash
# Restart single agent
docker-compose restart karma-hello

# Rebuild and restart (after code changes)
docker-compose up -d --build karma-hello
```

---

## Configuration

### Environment Variables

Each agent uses its own `.env` file:
- `agents/validator/.env`
- `agents/karma-hello/.env`
- `agents/abracadabra/.env`
- `agents/skill-extractor/.env`
- `agents/voice-extractor/.env`

**Override in docker-compose.yml:**
```yaml
services:
  karma-hello:
    environment:
      - PORT=9002
      - LOG_LEVEL=DEBUG
```

### Volumes

**Persistent data:**
- `karma-hello-data` - Cache and temporary data
- `abracadabra-data` - Cache and temporary data
- `skill-extractor-cache` - Profile cache
- `voice-extractor-cache` - Profile cache
- `validator-cache` - Validation results

**Mounted from host:**
- `./data/karma-hello` → `/app/agent/logs` (read-only product data)
- `./data/abracadabra` → `/app/agent/transcripts` (read-only product data)
- `~/.aws` → `/root/.aws` (AWS credentials)

### Networks

All agents run in the `karmacadabra` network.

**Internal URLs:**
- `http://validator:9001`
- `http://karma-hello:9002`
- `http://abracadabra:9003`
- `http://skill-extractor:9004`
- `http://voice-extractor:9005`

**External access** via `localhost:900X`

---

## Development

### Development Mode

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Features:**
- Code hot reload (changes reflect immediately)
- Verbose logging (`LOG_LEVEL=DEBUG`)
- CrewAI verbose mode enabled
- Read-write volume mounts

### Rebuild After Changes

```bash
# Rebuild all images
docker-compose build

# Rebuild single agent
docker-compose build karma-hello

# Rebuild and restart
docker-compose up -d --build karma-hello
```

### Debug Inside Container

```bash
# Open shell in running container
docker-compose exec karma-hello bash

# Run Python REPL
docker-compose exec karma-hello python

# Check environment
docker-compose exec karma-hello env

# Test connectivity
docker-compose exec skill-extractor curl http://karma-hello:9002/health
```

---

## Testing Flows

### Test 1: Simple Discovery

```bash
# Check all agents are registered
curl http://localhost:9002/.well-known/agent-card  # karma-hello
curl http://localhost:9004/.well-known/agent-card  # skill-extractor
```

### Test 2: Skill-Extractor Buys from Karma-Hello

From **outside** containers (host machine):

```bash
# Check skill-extractor can discover karma-hello
docker-compose exec skill-extractor curl http://karma-hello:9002/.well-known/agent-card

# Trigger purchase (implement test endpoint or use client agent)
```

From **inside** skill-extractor container:

```bash
docker-compose exec skill-extractor python -c "
from shared.a2a_protocol import discover_agent
card = discover_agent('http://karma-hello:9002')
print(card)
"
```

### Test 3: End-to-End Transaction

Use the client agent (not in docker-compose, run manually):

```bash
# From host machine
cd client-agents/template
python main.py --buy-logs --user 0xultravioleta
```

The client will:
1. Discover karma-hello via A2A
2. Sign payment authorization
3. Purchase chat logs via x402 protocol
4. Save data locally

---

## Troubleshooting

### Agent fails to start

**Check logs:**
```bash
docker-compose logs karma-hello
```

**Common issues:**
- ❌ Missing .env file → Create from .env.example
- ❌ Invalid PRIVATE_KEY → Leave empty to fetch from AWS
- ❌ Port already in use → Check with `netstat -ano | findstr "9002"`
- ❌ AWS credentials missing → Configure AWS CLI or add PRIVATE_KEY to .env

### "Address already in use" error

**Check what's using the port:**
```bash
# Windows
netstat -ano | findstr "9002"

# Linux/Mac
lsof -i :9002
```

**Fix:** Stop the conflicting process or change PORT in .env

### Agent can't connect to another agent

**Test connectivity:**
```bash
# From inside container
docker-compose exec skill-extractor curl http://karma-hello:9002/health

# Check DNS resolution
docker-compose exec skill-extractor ping karma-hello
```

**Fix:** Ensure both agents are in the same network (`karmacadabra`)

### AWS Secrets Manager connection fails

**Check credentials:**
```bash
docker-compose exec karma-hello cat /root/.aws/credentials
docker-compose exec karma-hello aws secretsmanager get-secret-value --secret-id karmacadabra --region us-east-1
```

**Fix:** Ensure ~/.aws/credentials exists and is mounted correctly

### Changes not reflecting

**Development mode not enabled:**
```bash
# Use dev compose file
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Rebuild needed:**
```bash
docker-compose up -d --build karma-hello
```

### Out of disk space

**Clean up:**
```bash
# Remove stopped containers
docker-compose down

# Remove unused images
docker image prune -a

# Remove unused volumes (DELETES DATA!)
docker volume prune
```

---

## Production Deployment

### Build Production Images

```bash
# Build all agents
docker-compose build

# Tag for registry
docker tag karmacadabra_karma-hello:latest registry.example.com/karmacadabra/karma-hello:v1.0.0

# Push to registry
docker push registry.example.com/karmacadabra/karma-hello:v1.0.0
```

### Security Best Practices

1. **Never expose ports publicly** - Use reverse proxy (nginx, traefik)
2. **Use secrets management** - AWS Secrets Manager, not .env files
3. **Enable TLS** - All inter-agent communication over HTTPS
4. **Resource limits** - Set memory/CPU limits in docker-compose.yml
5. **Regular updates** - Keep base images updated

### Example Production Compose

```yaml
services:
  karma-hello:
    image: registry.example.com/karmacadabra/karma-hello:v1.0.0
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    secrets:
      - aws_credentials
```

---

## Next Steps

1. **Start the stack**: `docker-compose up -d`
2. **Check health**: `curl http://localhost:9002/health`
3. **View logs**: `docker-compose logs -f`
4. **Test purchases**: Use client agent to buy services
5. **Monitor metrics**: `curl http://localhost:9090/metrics`

**For more details**: See MASTER_PLAN.md and ARCHITECTURE.md
