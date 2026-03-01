---
title: Transaction Dashboard
tags:
  - dashboard
  - transactions
---

## Transaction Log
See [[ledger]] for full transaction history.

## Revenue by Agent

```dataview
TABLE daily_revenue_usdc AS "Revenue", daily_spent_usdc AS "Spent", (daily_revenue_usdc - daily_spent_usdc) AS "Net"
FROM "agents"
WHERE daily_revenue_usdc > 0 OR daily_spent_usdc > 0
SORT daily_revenue_usdc DESC
```
