# Port Migration to 9000+ Range

**Date**: 2025-10-25
**Reason**: Avoid port conflicts with running services on 8000 range

---

## Port Changes

All agents migrated from 8000 range to 9000 range:

| Agent | Old Port | New Port |
|-------|----------|----------|
| **validator** | 8001 | **9001** |
| **karma-hello** | 8002 | **9002** |
| **abracadabra** | 8003 | **9003** |
| **skill-extractor** | 8085 | **9004** |
| **voice-extractor** | 8005 | **9005** |

**Client agents** don't run servers, so no port needed.

---

## Files Updated

### ✅ Committed (.env.example files):
- `agents/karma-hello/.env.example` - PORT=9002
- `agents/abracadabra/.env.example` - PORT=9003
- `agents/skill-extractor/.env.example` - PORT=9004
- `agents/voice-extractor/.env.example` - PORT=9005
- `agents/validator/.env.example` - PORT=9001 (added)

### ⚠️ YOU MUST UPDATE MANUALLY (.env files):
These files contain secrets and are NOT in git. Update them manually:

```bash
# Copy new ports from .env.example files
agents/karma-hello/.env              # Change PORT=8002 to PORT=9002
agents/abracadabra/.env              # Change PORT=8003 to PORT=9003
agents/skill-extractor/.env          # Change PORT=8085 to PORT=9004
agents/voice-extractor/.env          # Change PORT=8005 to PORT=9005
agents/validator/.env                # Add PORT=9001
```

### Integration URLs Updated:
- `agents/skill-extractor/.env.example` - KARMA_HELLO_URL=http://localhost:9002
- `agents/voice-extractor/.env.example` - KARMA_HELLO_URL=http://localhost:9002

---

## How to Update Your Local .env Files

### Option 1: Manual Edit (Recommended)

Open each `.env` file and change the PORT value:

**agents/karma-hello/.env**:
```bash
# Find line:
PORT=8002
# Change to:
PORT=9002
```

**agents/abracadabra/.env**:
```bash
# Find line:
PORT=8003
# Change to:
PORT=9003
```

**agents/skill-extractor/.env**:
```bash
# Find line:
PORT=8085
# Change to:
PORT=9004

# Also find:
KARMA_HELLO_URL=http://localhost:8002
# Change to:
KARMA_HELLO_URL=http://localhost:9002
```

**agents/voice-extractor/.env**:
```bash
# Find line:
PORT=8005
# Change to:
PORT=9005

# Also find:
KARMA_HELLO_URL=http://localhost:8002
# Change to:
KARMA_HELLO_URL=http://localhost:9002
```

**agents/validator/.env**:
```bash
# Add these lines after VALIDATOR_DOMAIN:
HOST=0.0.0.0
PORT=9001
```

### Option 2: Automated (PowerShell - Windows)

⚠️ **BACKUP YOUR .env FILES FIRST!**

```powershell
# karma-hello
(Get-Content agents/karma-hello/.env) -replace 'PORT=8002', 'PORT=9002' | Set-Content agents/karma-hello/.env

# abracadabra
(Get-Content agents/abracadabra/.env) -replace 'PORT=8003', 'PORT=9003' | Set-Content agents/abracadabra/.env

# skill-extractor
(Get-Content agents/skill-extractor/.env) -replace 'PORT=8085', 'PORT=9004' | Set-Content agents/skill-extractor/.env
(Get-Content agents/skill-extractor/.env) -replace 'KARMA_HELLO_URL=http://localhost:8002', 'KARMA_HELLO_URL=http://localhost:9002' | Set-Content agents/skill-extractor/.env

# voice-extractor
(Get-Content agents/voice-extractor/.env) -replace 'PORT=8005', 'PORT=9005' | Set-Content agents/voice-extractor/.env
(Get-Content agents/voice-extractor/.env) -replace 'KARMA_HELLO_URL=http://localhost:8002', 'KARMA_HELLO_URL=http://localhost:9002' | Set-Content agents/voice-extractor/.env
```

---

## Restart All Agents

After updating .env files, restart all agents:

```bash
# Stop all running agents (Ctrl+C or kill processes on old ports)

# Start validator (9001)
cd agents/validator && python main.py

# Start karma-hello (9002)
cd agents/karma-hello && python main.py

# Start abracadabra (9003)
cd agents/abracadabra && python main.py

# Start skill-extractor (9004)
cd agents/skill-extractor && python main.py

# Start voice-extractor (9005)
cd agents/voice-extractor && python main.py
```

---

## Verify Ports

Check that agents are running on new ports:

```bash
# Windows (PowerShell)
netstat -ano | findstr "900"

# Linux/Mac
lsof -i :9001
lsof -i :9002
lsof -i :9003
lsof -i :9004
lsof -i :9005
```

Expected output should show processes listening on 9001-9005.

---

## Troubleshooting

### Agent still trying to bind to old port
- ❌ You didn't update the `.env` file (only updated `.env.example`)
- ✅ Make sure to edit the actual `.env` file, not just `.env.example`

### "Address already in use" error on 9000+ port
- ❌ Another process is using that port
- ✅ Check with `netstat -ano | findstr "PORTNUMBER"` (Windows) or `lsof -i :PORTNUMBER` (Linux/Mac)
- ✅ Kill the process or choose a different port

### Skill/Voice extractor can't reach karma-hello
- ❌ You didn't update KARMA_HELLO_URL in `.env`
- ✅ Update from `http://localhost:8002` to `http://localhost:9002`

---

## Production Deployment

When deploying to production servers:
- Update DNS/reverse proxy to point to new ports
- Update any firewall rules to allow 9001-9005
- Update any load balancer configurations
- Update monitoring/alerting to check new ports

---

**Status**: ✅ All .env and .env.example files updated
**Docker**: ✅ Docker Compose setup available - see DOCKER_GUIDE.md

---

## Docker Compose (Recommended)

Instead of manually managing ports and processes, use Docker Compose:

```bash
# Start all agents with one command
docker-compose up -d

# Or use the convenience script
scripts\docker-start.bat        # Windows
bash scripts/docker-start.sh    # Linux/Mac
```

**See DOCKER_GUIDE.md for complete documentation.**
