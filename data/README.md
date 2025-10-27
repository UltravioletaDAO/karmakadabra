# Sample Data for Karmacadabra Agents

Static demo files for testing seller agents and data marketplace functionality.

## Overview

This directory contains sample data files that seller agents (Karma-Hello, Abracadabra) can use for demonstrations and testing without needing real production databases.

## Structure

```
data/
├── karma-hello/          # Twitch chat logs
│   └── chat_logs_20251023.json
├── abracadabra/          # Stream transcriptions
│   └── transcription_20251023.json
└── README.md
```

## Karma-Hello Data (Chat Logs)

**File**: `karma-hello/chat_logs_20251023.json`

Simulates Twitch stream chat logs with:
- **156 messages** from 23 unique users
- **2-hour stream** (120 minutes)
- Timestamped messages with user badges
- Statistics (messages/minute, active users, etc.)
- Metadata (collection method, format version)

**Format**:
```json
{
  "stream_id": "stream_20251023_001",
  "stream_date": "2025-10-23",
  "messages": [
    {
      "timestamp": "2025-10-23T14:00:00Z",
      "user": "alice_crypto",
      "message": "Hello everyone!",
      "user_badges": ["subscriber"]
    }
  ],
  "statistics": {...},
  "metadata": {...}
}
```

**Use Cases:**
- Testing Karma-Hello seller agent
- Validator quality analysis
- Client agent purchase demos
- Chat sentiment analysis

**Pricing Reference**: 0.01 GLUE (Tier 1 service)

## Abracadabra Data (Transcriptions)

**File**: `abracadabra/transcription_20251023.json`

Simulates stream transcription with:
- **15 transcript segments** over 2 hours
- Speaker identification
- Timestamps (start/end for each segment)
- Summary and key topics
- Entity extraction
- Quality metrics

**Format**:
```json
{
  "stream_id": "stream_20251023_001",
  "stream_date": "2025-10-23",
  "transcript": [
    {
      "start": 0,
      "end": 15,
      "speaker": "host",
      "text": "Welcome everyone..."
    }
  ],
  "summary": "...",
  "key_topics": [...],
  "entities": [...],
  "metadata": {...}
}
```

**Use Cases:**
- Testing Abracadabra seller agent
- Transcript quality validation
- Text analysis demonstrations
- NLP feature testing

**Pricing Reference**: 0.02 GLUE (Tier 1 service)

## Data Relationships

Both files share the same `stream_id` and `stream_date`, simulating complementary data sources:

- **Chat logs** = What viewers said during the stream
- **Transcription** = What the streamer said during the stream

**Combined value**: Buyers can purchase both to get complete context of a stream.

## Quality Characteristics

Both sample files are designed to pass validation with high scores:

### Chat Logs Quality
- ✅ Complete message data (timestamp, user, text, badges)
- ✅ Valid JSON structure
- ✅ Realistic conversation patterns
- ✅ Comprehensive statistics
- ✅ High data quality metadata

**Expected Validation Score**: 0.8-0.9

### Transcription Quality
- ✅ Complete segments with timestamps
- ✅ Speaker identification
- ✅ Coherent technical content
- ✅ Entity extraction and summary
- ✅ High confidence scores

**Expected Validation Score**: 0.85-0.95

## Testing Scenarios

### Scenario 1: High-Quality Data
Use these files as-is to test:
- Successful purchase flow
- High validation scores
- Proper data storage
- Positive seller ratings

### Scenario 2: Create Modified Versions

For negative testing, create modified versions:

**Low Quality** (`*_low_quality.json`):
- Remove fields (incomplete data)
- Add inconsistencies
- Lower metadata quality scores

**Overpriced** (test with high prices):
- Use same files but set price to 10.0 GLUE
- Should trigger price validation warnings

**Suspicious** (fraud detection):
- Add spam-like content
- Include phishing patterns
- Inject malicious links

## File Sizes

- `chat_logs_20251023.json`: ~3.5 KB
- `transcription_20251023.json`: ~4.2 KB

**Total**: ~7.7 KB of sample data

## Integration with Agents

### Karma-Hello Seller
```python
# Load sample data
with open('data/karma-hello/chat_logs_20251023.json') as f:
    sample_logs = json.load(f)

# Serve via API endpoint
@app.get("/api/chat_logs")
async def get_logs():
    return sample_logs
```

### Abracadabra Seller
```python
# Load sample data
with open('data/abracadabra/transcription_20251023.json') as f:
    sample_transcript = json.load(f)

# Serve via API endpoint
@app.get("/api/transcription")
async def get_transcription():
    return sample_transcript
```

### Client Agent
```python
# Purchase sample data
data = await client.buy_data(
    seller_url="https://karma-hello.example.com",
    endpoint="/api/chat_logs",
    price_glue="0.01"
)

# Validate
validation = await client.request_validation(
    data=data,
    data_type="chat_logs",
    seller_address="0x...",
    price_glue="0.01"
)
```

## Extending Sample Data

To add more sample files:

1. **Create new date directories**:
   ```
   data/karma-hello/20251024/
   data/abracadabra/20251024/
   ```

2. **Follow naming convention**:
   - `chat_logs_YYYYMMDD.json`
   - `transcription_YYYYMMDD.json`

3. **Maintain schema compatibility**:
   - Keep same JSON structure
   - Include all required fields
   - Add metadata for quality tracking

## Data Generation

These files were manually created to represent realistic data for testing. For production:

- **Karma-Hello**: Real data from `z:\ultravioleta\ai\cursor\karma-hello` MongoDB
- **Abracadabra**: Real data from `z:\ultravioleta\ai\cursor\abracadabra` SQLite + Cognee

## Docker Build Issues (Windows)

### Known Issue: fsutil Walker Panic

**Problem**: Docker builds fail on Windows with `panic: runtime error: invalid memory address or nil pointer dereference` in `github.com/tonistiigi/fsutil` walker.

**Error**:
```
panic: runtime error: invalid memory address or nil pointer dereference
[signal 0xc0000005 code=0x0 addr=0x10 pc=0x375d33]

goroutine 150 [running]:
os.(*fileStat).Mode(...)
  os/types_windows.go:116
os.(*fileStat).IsDir(0xc000276180?)
  os/types.go:59 +0x13
github.com/tonistiigi/fsutil.Walk.func1(...)
```

**Root Cause**: Docker BuildKit on Windows has a bug when walking certain file structures during build context creation. This happens even before reaching the COPY commands.

**Solutions**:

#### Solution 1: Build in WSL2 (Recommended)
```bash
# From WSL2 terminal
cd /mnt/z/ultravioleta/dao/karmacadabra
python scripts/build-and-push.py --agents karma-hello abracadabra --force
```

#### Solution 2: Use GitHub Actions
Create `.github/workflows/build-docker.yml`:
```yaml
name: Build Docker Images
on:
  push:
    paths:
      - 'agents/**'
      - 'data/**'
      - 'Dockerfile.agent'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/setup-buildx-action@v2
      - uses: aws-actions/configure-aws-credentials@v2
      - run: python scripts/build-and-push.py --force
```

#### Solution 3: Manual Docker Commands (Linux/Mac only)
```bash
# Build karma-hello
docker build --platform linux/amd64 \
  -f Dockerfile.agent \
  -t karmacadabra/karma-hello:latest \
  --build-arg AGENT_PATH=agents/karma-hello \
  .

# Build abracadabra
docker build --platform linux/amd64 \
  -f Dockerfile.agent \
  -t karmacadabra/karma-hello:latest \
  --build-arg AGENT_PATH=agents/abracadabra \
  .
```

**Status**: Mock data files are ready and committed. Dockerfile is configured correctly. Only the build step is blocked on Windows native Docker.

## License

Sample data for testing purposes. Not for production use.

---

**Built with ❤️ by Ultravioleta DAO**
