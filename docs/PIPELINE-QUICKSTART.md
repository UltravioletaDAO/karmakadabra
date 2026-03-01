# Task Pipeline — Quick Start Guide

The Task Pipeline is the engine that makes KK agents autonomously execute Execution Market tasks. It handles the full lifecycle: discover → evaluate → apply → execute → submit → learn.

## Architecture

```
                    ┌──────────────────────────────────────────┐
                    │           Task Pipeline                   │
                    │                                          │
  EM Marketplace ──→│  DISCOVER → EVALUATE → APPLY → EXECUTE  │──→ Evidence
  (published tasks) │              ↓                   ↓       │    Submission
                    │         Match Scoring      LLM Provider  │
                    │         (5 factors)     (Anthropic/OpenAI)│
                    │              ↓                   ↓       │
                    │         Budget Check        Cost Track    │
                    └──────────────────────────────────────────┘
```

## Prerequisites

```bash
# Required Python packages
pip install httpx anthropic  # or just httpx for OpenAI-only

# Set at least one LLM API key
export ANTHROPIC_API_KEY="sk-ant-..."   # Preferred
# OR
export OPENAI_API_KEY="sk-proj-..."     # Alternative
```

## Single Agent — Quick Test

```bash
cd ~/clawd/projects/karmakadabra

# Dry run (plan but don't execute/submit)
python3 services/task_pipeline.py \
  --workspace workspaces/kk-agent-1 \
  --once --dry-run

# Live execution (single cycle)
python3 services/task_pipeline.py \
  --workspace workspaces/kk-agent-1 \
  --once --budget 1.00

# Continuous mode (5 min intervals)
python3 services/task_pipeline.py \
  --workspace workspaces/kk-agent-1 \
  --continuous --interval 300 --budget 5.00
```

## Multi-Agent Swarm

```bash
# All agents in workspaces directory
python3 services/task_pipeline.py \
  --workspaces-dir workspaces/ \
  --max-cycles 10 --budget 2.00

# With specific LLM backend
python3 services/task_pipeline.py \
  --workspaces-dir workspaces/ \
  --backend openai --model gpt-4o-mini \
  --max-cycles 5 --dry-run
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KK_PER_TASK_BUDGET` | `0.50` | Max USD per task execution |
| `KK_DAILY_BUDGET` | `5.00` | Max USD per day per agent |
| `KK_MIN_BOUNTY` | `0.05` | Ignore tasks below this bounty |
| `KK_MAX_TASKS_PER_CYCLE` | `3` | Max tasks evaluated per cycle |
| `KK_LLM_BACKEND` | `auto` | `auto`, `anthropic`, `openai`, `mock` |
| `KK_LLM_MODEL` | (auto) | Specific model name |
| `KK_ADAPTIVE_LLM` | `1` | Auto-select model by task complexity |
| `KK_CYCLE_INTERVAL` | `300` | Seconds between continuous cycles |
| `KK_DRY_RUN` | `0` | `1` to enable dry-run mode |

### JSON Config File

Create `pipeline_config.json` in agent workspace:

```json
{
  "per_task_budget_usd": 0.50,
  "daily_budget_usd": 5.00,
  "min_bounty_usd": 0.05,
  "max_tasks_per_cycle": 3,
  "preferred_categories": ["research", "analysis", "code_review"],
  "adaptive_llm": true
}
```

## LLM Provider Options

### Auto-detect (default)
The pipeline checks for API keys in order: `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` → Mock

### Adaptive Mode (recommended)
Automatically routes tasks to the cheapest model that can handle them:
- **Short tasks** → Haiku / GPT-4.1-nano ($0.10-1.00/M tokens)
- **Medium tasks** → Sonnet / GPT-4o-mini ($0.75-3.00/M tokens)  
- **Complex tasks** → Sonnet / GPT-4o ($3.00-10.00/M tokens)

### Mock Mode (testing)
No API key needed. Returns deterministic responses. Great for testing the pipeline without spending money.

```bash
python3 services/task_pipeline.py --workspace workspaces/test --once --backend mock
```

## Pipeline Stages

### 1. DISCOVER
Polls EM for `published` tasks. Filters: min bounty, excluded categories, already-active.

### 2. EVALUATE
Creates execution plans. Scores each task on 5 factors:
- **Confidence (30%)** — How sure the agent is it can complete this
- **Profitability (25%)** — Bounty ÷ estimated cost
- **Category (20%)** — Does it match the agent's specialization?
- **Recency (15%)** — Newer tasks = less competition
- **Evidence (10%)** — Can we produce the required evidence type?

### 3. APPLY
Submits application to EM marketplace with agent name, strategy, and confidence.

### 4. EXECUTE
Routes to the right execution strategy:
- **LLM_DIRECT** — Pure knowledge tasks (research, analysis, translation)
- **LLM_WITH_TOOLS** — Tasks needing enriched context (code review, data collection)
- **COMPOSITE** — Multi-step tasks (break down, execute parts, assemble)
- **HUMAN_ROUTE** — Self-aware refusal for physical tasks

### 5. SUBMIT
Packages output as EM-compatible evidence and submits via API.

### 6. LEARN
Updates agent performance profiles. Feeds back into match scoring.

## Output

Each cycle produces a JSON log in `<workspace>/logs/pipeline_YYYYMMDD_HHMMSS.json`:

```json
{
  "cycle_id": "kk-agent-1-cycle-1",
  "agent_name": "kk-agent-1",
  "tasks_discovered": 5,
  "tasks_evaluated": 3,
  "tasks_submitted": 2,
  "total_cost_usd": 0.0045,
  "total_bounty_usd": 0.50
}
```

## Tests

```bash
# LLM Provider tests
python3 -m pytest tests/v2/test_llm_provider.py -v    # 41 tests

# Pipeline tests
python3 -m pytest tests/v2/test_task_pipeline.py -v    # 38 tests

# Full suite
python3 -m pytest tests/ -q                            # 1,443+ tests
```

## Key Files

| File | Lines | Description |
|------|------:|-------------|
| `lib/llm_provider.py` | 566 | Multi-backend LLM provider |
| `services/task_pipeline.py` | 968 | End-to-end task pipeline |
| `services/task_executor.py` | 877 | Task execution strategies |
| `services/evidence_processor.py` | 628 | Evidence processing + learning |
| `services/intelligence_synthesizer.py` | 1,100 | Compound intelligence routing |
| `services/swarm_runner.py` | 930 | Production daemon |
