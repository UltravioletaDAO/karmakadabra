# Docker Compose + Port Update Summary

**Date**: 2025-10-25
**Changes**: Complete Docker Compose setup + Port migration to 9000 range

---

## ✅ What Changed

### 1. All Ports Updated (8000→9000 Range)

| Agent | Old Port | New Port |
|-------|----------|----------|
| validator | 8001/8083 | **9001** |
| karma-hello | 8002 | **9002** |
| abracadabra | 8003 | **9003** |
| skill-extractor | 8085 | **9004** |
| voice-extractor | 8005 | **9005** |

**Files Updated:**
- ✅ All `agents/*/.env` files
- ✅ All `agents/*/.env.example` files
- ✅ Integration URLs (KARMA_HELLO_URL in skill-extractor and voice-extractor)

### 2. Docker Compose Setup Created

**New Files:**
```
karmacadabra/
├── Dockerfile.agent                  # Base image for all Python agents
├── docker-compose.yml                # Production stack
├── docker-compose.dev.yml            # Development overrides (hot reload)
├── DOCKER_GUIDE.md                   # Complete documentation
└── scripts/
    ├── docker-start.sh               # Linux/Mac startup script
    └── docker-start.bat              # Windows startup script
```

**Features:**
- ✅ One-command startup: `docker-compose up -d`
- ✅ All 5 agents orchestrated together
- ✅ Internal networking (agents can discover each other)
- ✅ Persistent volumes for data
- ✅ AWS credentials mounting
- ✅ Health checks
- ✅ Auto-restart
- ✅ Log management

### 3. Security Fixes

**OPENAI_API_KEY cleaned from .env files:**
- ✅ `agents/skill-extractor/.env` - removed hardcoded key
- ✅ `agents/validator/.env` - removed hardcoded key

All keys now fetched from AWS Secrets Manager (unless overridden in .env for testing).

---

## 🚀 How to Use

### Quick Start (Docker - Recommended)

```bash
# Windows
scripts\docker-start.bat

# Linux/Mac
bash scripts/docker-start.sh

# Or manually
docker-compose up -d
```

**Check status:**
```bash
docker-compose ps
curl http://localhost:9002/health  # karma-hello
```

**View logs:**
```bash
docker-compose logs -f
docker-compose logs -f karma-hello  # single agent
```

**Stop:**
```bash
docker-compose down
```

### Manual Startup (Without Docker)

If you prefer running agents directly:

```bash
# Start validator
cd agents/validator && python main.py

# Start karma-hello (in new terminal)
cd agents/karma-hello && python main.py

# Start skill-extractor (in new terminal)
cd agents/skill-extractor && python main.py

# ... etc
```

**Note:** Make sure ports 9001-9005 are available.

---

## 📁 Files Modified

### Configuration Files (.env)
```
agents/validator/.env          - PORT=9001, OPENAI_API_KEY cleared
agents/karma-hello/.env        - PORT=9002
agents/abracadabra/.env        - PORT=9003
agents/skill-extractor/.env    - PORT=9004, KARMA_HELLO_URL updated, OPENAI_API_KEY cleared
agents/voice-extractor/.env    - PORT=9005, KARMA_HELLO_URL updated
```

### Example Files (.env.example)
```
agents/validator/.env.example       - Added PORT=9001
agents/karma-hello/.env.example     - PORT=9002
agents/abracadabra/.env.example     - PORT=9003
agents/skill-extractor/.env.example - PORT=9004, KARMA_HELLO_URL updated
agents/voice-extractor/.env.example - PORT=9005, KARMA_HELLO_URL updated
```

### Documentation
```
docs/guides/DOCKER_GUIDE.md                     - NEW: Complete Docker documentation
docs/migration/PORT_MIGRATION_9000.md           - Updated with Docker info
docs/migration/DOCKER_AND_PORT_UPDATE_SUMMARY.md - NEW: This file
CLAUDE.md                                        - Added Docker Compose section, updated port numbers
.gitignore                          - Added Docker entries
```

---

## 🧪 Testing

### Test 1: Start All Agents
```bash
docker-compose up -d
docker-compose ps
```

**Expected:** All 5 agents running, healthy

### Test 2: Health Checks
```bash
for port in 9001 9002 9003 9004 9005; do
  echo "Port $port:"
  curl -s http://localhost:$port/health | jq .
done
```

**Expected:** All return 200 OK

### Test 3: Agent Discovery
```bash
curl http://localhost:9002/.well-known/agent-card
```

**Expected:** JSON with karma-hello AgentCard

### Test 4: Inter-Agent Communication
```bash
docker-compose exec skill-extractor curl http://karma-hello:9002/health
```

**Expected:** 200 OK from inside skill-extractor container

---

## 🔧 Troubleshooting

### Port conflicts

**Error:** `address already in use`

**Fix:**
```bash
# Windows
netstat -ano | findstr "9002"

# Linux/Mac
lsof -i :9002

# Then kill the process or change PORT in .env
```

### AWS credentials not working

**Error:** `Unable to locate credentials`

**Fix:**
```bash
# Check credentials are mounted
docker-compose exec karma-hello ls -la /root/.aws/

# Verify credentials work
docker-compose exec karma-hello aws secretsmanager get-secret-value --secret-id karmacadabra --region us-east-1
```

### Agent can't find shared module

**Error:** `ModuleNotFoundError: No module named 'shared'`

**Fix:** Check volume mount in docker-compose.yml:
```yaml
volumes:
  - ./shared:/app/shared:ro
```

### Changes not reflecting

**Solution:** Rebuild containers
```bash
docker-compose up -d --build
```

---

## 📊 Next Steps

1. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

2. **Check logs for any errors:**
   ```bash
   docker-compose logs -f
   ```

3. **Test agent discovery:**
   ```bash
   curl http://localhost:9002/.well-known/agent-card
   ```

4. **Run client agent to test purchases:**
   ```bash
   cd client-agents/template
   python main.py --buy-logs
   ```

5. **Monitor validator metrics:**
   ```bash
   curl http://localhost:9090/metrics
   ```

---

## 📚 Documentation

**Quick References:**
- **../guides/DOCKER_GUIDE.md** - Complete Docker documentation
- **PORT_MIGRATION_9000.md** - Port changes details (same folder)
- **../../CLAUDE.md** - Project guidelines (updated with Docker info)
- **../../MASTER_PLAN.md** - Overall architecture
- **../guides/QUICKSTART.md** - 30-minute setup guide

**For help:**
- Docker issues → ../guides/DOCKER_GUIDE.md "Troubleshooting"
- Port conflicts → PORT_MIGRATION_9000.md
- General setup → ../guides/QUICKSTART.md

---

**Status**: ✅ Ready to use
**Command**: `docker-compose up -d`
