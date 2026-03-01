---
title: Supply Chain Flow
tags:
  - dashboard
  - supply-chain
---

## Sellers (Data Producers)

```dataview
TABLE daily_revenue_usdc AS "Revenue", tasks_completed AS "Tasks"
FROM "agents"
WHERE role = "seller" OR role = "buyer-seller"
SORT daily_revenue_usdc DESC
```

## Buyers (Consumers)

```dataview
TABLE daily_spent_usdc AS "Spent", tasks_completed AS "Purchases"
FROM "agents"
WHERE role = "community-buyer" OR role = "buyer-seller"
SORT daily_spent_usdc DESC
```

## See Also
- [[supply-chain]] - Chain architecture
- [[ledger]] - Transaction history
