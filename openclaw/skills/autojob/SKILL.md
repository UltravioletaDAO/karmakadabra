---
name: autojob
description: Privacy-first job matching from behavioral evidence. Match skills to bounties, analyze profiles, register on Execution Market.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME"]
    mcp:
      server: https://autojob.cc/mcp
---

# AutoJob — Skill DNA and Job Matching

AutoJob analyzes behavioral evidence to build a Skill DNA profile and match it to opportunities. For KK agents, this means better matching of bounties to capabilities.

**MCP Server**: https://autojob.cc/mcp

## MCP Tools (via mcp_client)

### Check AutoJob server status
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_check_status","params":{}}' | python3 /app/openclaw/tools/mcp_client.py
```

### Analyze evidence to build Skill DNA
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_analyze","params":{"html":"<insights content>"}}' | python3 /app/openclaw/tools/mcp_client.py
```

### Match skills to available jobs
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_match_jobs","params":{"query":"data processing","live":true}}' | python3 /app/openclaw/tools/mcp_client.py
```

### Register as EM worker
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_register_em","params":{"wallet_address":"0x..."}}' | python3 /app/openclaw/tools/mcp_client.py
```

### Ingest evidence from various sources
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_ingest_evidence","params":{"source":"github_profile","source_type":"github"}}' | python3 /app/openclaw/tools/mcp_client.py
```

### List available evidence sources
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_list_sources","params":{}}' | python3 /app/openclaw/tools/mcp_client.py
```

### Share a public profile
```bash
echo '{"server":"autojob","action":"call","tool":"autojob_share_profile","params":{"expires_days":7}}' | python3 /app/openclaw/tools/mcp_client.py
```

### List all available MCP tools
```bash
echo '{"server":"autojob","action":"list","tool":"","params":{}}' | python3 /app/openclaw/tools/mcp_client.py
```

## All 12 MCP Tools

| Tool | Purpose |
|------|---------|
| `autojob_check_status` | Server health check |
| `autojob_analyze` | HTML insights to Skill DNA |
| `autojob_analyze_cumulative` | Analyze all stored snapshots |
| `autojob_upload_snapshot` | Store HTML snapshot |
| `autojob_match_jobs` | DNA to job matches |
| `autojob_analyze_resume` | Parse resume text |
| `autojob_merge_resume` | Merge resume + insights |
| `autojob_list_sources` | List evidence parsers |
| `autojob_ingest_evidence` | Generic evidence ingestion |
| `autojob_merge_sources` | Merge multiple sources |
| `autojob_register_em` | Register as EM worker |
| `autojob_share_profile` | Generate shareable profile URL |

## Integration with KK Swarm

AutoJob connects the KK swarm to the broader job economy:

1. **Skill Discovery**: Analyze what your agent is good at based on evidence
2. **Job Matching**: Find bounties on Execution Market that match your skills
3. **EM Registration**: Register your agent as a worker for matched jobs
4. **Profile Sharing**: Share a public skills profile with other agents

## Evidence Weighting

- Self-reported evidence: weight 0.3
- System-generated evidence: weight 1.0 (more trusted)

Use system-generated evidence (code outputs, API responses, task completions) for higher match quality.

## Privacy

- No persistent data retention on autojob.cc
- HTTPS encryption enforced
- No tracking, analytics, or cookies
- Local caching in the agent workspace
