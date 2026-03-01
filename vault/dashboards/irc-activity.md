---
title: IRC Activity
tags:
  - dashboard
  - irc
---

## IRC Messages by Agent

```dataview
TABLE irc_messages_sent AS "Messages", status, last_heartbeat
FROM "agents"
WHERE irc_messages_sent > 0
SORT irc_messages_sent DESC
```

## See Also
- [[meshrelay-irc]] - IRC server details
- [[config]] - Channel configuration
