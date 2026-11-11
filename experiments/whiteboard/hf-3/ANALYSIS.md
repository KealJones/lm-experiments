# What LFM3 did when asked to update its notes

693 update turns.

| what happened | turns | share |
|---|---|---|
| ran out of output (1,536 tokens) while still thinking | 492 | 71% |
| finished thinking, then ended without a call | 137 | 20% |
| wrote the file | 61 | 9% |
| called tools, never wrote | 3 | 0% |

By turn number (writes happen early, then the growing file crowds them out):

| turns | wrote | ran out while thinking | ended without a call |
|---|---|---|---|
| 1-10 | 50 | 69 | 40 |
| 11-20 | 8 | 118 | 34 |
| 21-30 | 2 | 128 | 30 |
| 31-40 | 1 | 133 | 22 |
| 41-50 | 0 | 44 | 11 |

## Per chat

| test | turns replayed | finished | wrote | notes words at the end | answer-key facts kept / said so far |
|---|---|---|---|---|---|
| 1 | 44/44 | no | 2 | 159 | 1/3 |
| 2 | 44/65 | no | 2 | 132 | 1/4 |
| 3 | 44/47 | no | 4 | 167 | 1/5 |
| 4 | 44/64 | no | 2 | 147 | 0/1 |
| 5 | 44/46 | no | 3 | 205 | 2/2 |
| 6 | 44/61 | no | 2 | 150 | 0/2 |
| 7 | 44/50 | no | 4 | 232 | 0/4 |
| 8 | 45/66 | no | 5 | 215 | 1/2 |
| 9 | 44/47 | no | 3 | 264 | 0/1 |
| 10 | 45/48 | no | 7 | 211 | 4/4 |
| 11 | 40/40 | yes | 7 | 207 | 1/3 |
| 12 | 38/38 | yes | 3 | 247 | 1/5 |
| 13 | 44/62 | no | 3 | 133 | - |
| 14 | 44/47 | no | 2 | 209 | - |
| 15 | 44/67 | no | 7 | 184 | - |
| 16 | 41/41 | yes | 5 | 192 | - |
