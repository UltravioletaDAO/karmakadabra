# Top Chatters Analysis — KarmaHello Twitch Logs

**Date**: 2026-03-03
**Source**: `z:\ultravioleta\ai\cursor\karma-hello\logs\chat\full.txt`
**Total**: 471,050 messages from 832 unique users (June 2024 - December 2025)

---

## Data Cleanup Performed

### david_uvd -> davidtherich Merge
Same person, two usernames. Merged all data:

| Location | Files | Operation |
|---|---|---|
| `logs/chat/full.txt` | 1 | 2,632 lines renamed |
| Per-user folder (`david_uvd/`) | 3 + folder deleted | full.txt, all.txt, saludo.txt appended |
| Per-stream `.txt` files | 68 | 67 renamed + 1 append+delete |
| S3 JSON (`chat_logs_YYYYMMDD.json`) | 68 | "user" field replaced, re-uploaded |
| Analytics JSON | 3 | user_profiles merged (stats combined), snapshots+events renamed |
| **Total** | **143 files** | |

Result: davidtherich went from 4,272 msgs (#10) to **6,904 msgs (#7)**.

---

## Top 18 Community Agents (Final Selection)

Excluding: 0xultravioleta (streamer), 1nocty, coleguin_, detx8, teddysaintt, inichelt_go.

| # | Username | Messages | % Total |
|---|----------|----------|---------|
| 1 | juanjumagalp | 12,922 | 2.74% |
| 2 | stovedove | 10,098 | 2.14% |
| 3 | 0xroypi | 9,031 | 1.92% |
| 4 | davidtherich | 6,904 | 1.47% |
| 5 | 0xjokker | 6,044 | 1.28% |
| 6 | 0xyuls | 5,523 | 1.17% |
| 7 | datbo0i_lp | 5,129 | 1.09% |
| 8 | acpm444 | 4,102 | 0.87% |
| 9 | saemtwentytwo | 3,757 | 0.80% |
| 10 | x4rlz | 3,316 | 0.70% |
| 11 | alej_o | 3,148 | 0.67% |
| 12 | 0xpineda | 3,007 | 0.64% |
| 13 | 0xkysaug | 2,970 | 0.63% |
| 14 | karenngo | 2,712 | 0.58% |
| 15 | eljuyan | 2,710 | 0.58% |
| 16 | elbitterx | 2,704 | 0.57% |
| 17 | f3l1p3_bx | 2,572 | 0.55% |
| 18 | cyberpaisa | 2,553 | 0.54% |

**Combined**: 87,195 messages (18.51% of total)

---

## Changes vs Current identities.json

### Agents that STAY (already registered)
juanjumagalp, stovedove, 0xroypi, davidtherich, 0xjokker, datbo0i_lp, acpm444, karenngo, eljuyan, elbitterx, cyberpaisa

### Agents that ENTER (new)
0xyuls, saemtwentytwo, x4rlz, alej_o, 0xpineda, 0xkysaug, f3l1p3_bx

### Agents that EXIT (removed from 18)
sanvalencia2, elboorja, cymatix, painbrayan, psilocibin3, 0xsoulavax, 1nocty

---

## Additional Lookups

- **cdt8a_**: 832 messages (does not qualify for top 18)

---

## Script

`scripts/kk/top_chatters.py` — usage: `python scripts/kk/top_chatters.py [N]` (default: 18)
