---
name: kk-data
description: Access local data stores including chat logs, transcripts, agent memory, and workspace files.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME"]
---

# kk-data

Local data access for KarmaCadabra agents. Provides access to chat logs, transcripts, agent memory files, and workspace data stored on the agent's local filesystem.

## Data Locations

| Data Type | Path | Format |
|-----------|------|--------|
| Chat logs | `logs/YYYYMMDD/full.txt` | Plain text, one message per line |
| Transcripts | `data/transcripts/YYYYMMDD/{id}/transcripcion.json` | JSON with timestamps and text |
| Agent memory | `data/workspaces/{agent}/memory/MEMORY.md` | Markdown |
| Workspace | `data/workspaces/{agent}/` | Mixed files |
| Reputation snapshots | `data/reputation/` | JSON snapshots |

## Script

### read_agent_memory.py

Located at `scripts/kk/read_agent_memory.py`. Read another agent's MEMORY.md from their workspace directory. Useful for understanding what other agents know and have learned.

```bash
python3 scripts/kk/read_agent_memory.py --agent kk-skill-extractor
python3 scripts/kk/read_agent_memory.py --agent kk-coordinator --section "Trusted Agents"
```

Arguments:
- `--agent` (required): Agent name to read memory from
- `--section` (optional): Specific `## Section Name` to extract from the MEMORY.md

Output (full memory):
```json
{
  "agent": "kk-skill-extractor",
  "content": "# Agent Memory\n\n## Skills Database\n..."
}
```

Output (specific section):
```json
{
  "agent": "kk-coordinator",
  "section": "Trusted Agents",
  "content": "## Trusted Agents\n\n- kk-karma-hello: reliable, fast\n..."
}
```

Output (not found):
```json
{
  "agent": "kk-new-agent",
  "content": "",
  "note": "No MEMORY.md found at data/workspaces/kk-new-agent/memory/MEMORY.md"
}
```

The script tries both `kk-{name}` and `{name}` prefixes when searching.

## Accessing Logs Directly

Chat logs are plain text files organized by date. Each agent can read its own logs directory:

```bash
# List available log dates
ls logs/

# Read today's logs
cat logs/20260225/full.txt

# Count messages
wc -l logs/20260225/full.txt
```

## Accessing Transcripts Directly

Transcripts are JSON files organized by date and session ID:

```bash
# List available transcript dates
ls data/transcripts/

# List sessions for a date
ls data/transcripts/20260225/

# Read a transcript
cat data/transcripts/20260225/{session-id}/transcripcion.json
```

## Dependencies

- `lib.memory` (read_memory_md)

## Error Handling

Exit code 1 on failure with JSON error to stderr:
```json
{"error": "description of what went wrong", "agent": "kk-karma-hello"}
```
