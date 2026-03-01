---
title: Agent Status Dashboard
tags:
  - dashboard
---

## All Agents

```dataview
TABLE status, role, last_heartbeat, daily_revenue_usdc, tasks_completed, errors_last_24h
FROM "agents"
SORT status ASC, agent_id ASC
```

## Active Agents

```dataview
TABLE role, current_task, daily_revenue_usdc, irc_messages_sent
FROM "agents"
WHERE status = "active"
SORT last_heartbeat DESC
```

## Pending Deployment

```dataview
LIST
FROM "agents"
WHERE status = "pending"
SORT agent_id ASC
```
