# Blind grades (notes-search-4a)

Shuffled letters (mapping.json), graded against the context-packets keys, then unblinded.

| test | whole | bm25 | hybrid | lfm3q_bm25 |
|---|---|---|---|---|
| 1 | fail 4 | fail 6 | fail 5 | fail 6 |
| 2 | fail 5 | fail 3 | fail 3 | fail 1 |
| 3 | fail 4 | fail 2 | fail 1 | fail 1 |
| 4 | fail 5 | pass 8 | fail 4 | fail 3 |
| 5 | fail 0 | fail 1 | fail 1 | fail 0 |
| 6 | fail 1 | fail 1 | fail 1 | fail 1 |
| 7 | fail 1 | fail 0 | fail 0 | fail 0 |
| 8 | fail 2 | fail 1 | fail 0 | fail 1 |
| 9 | fail 2 | fail 0 | fail 0 | fail 1 |
| 10 | fail 5 | fail 5 | fail 4 | fail 4 |
| 11 | pass 10 | pass 10 | pass 10 | pass 10 |
| 12 | fail 3 | fail 3 | fail 2 | fail 3 |
| 13 | pass 10 | fail 2 | fail 2 | pass 10 |
| 14 | pass 10 | fail 0 | pass 10 | pass 10 |
| 15 | pass 10 | pass 9 | pass 10 | pass 9 |
| 16 | fail 1 | fail 1 | fail 0 | fail 1 |

| packet | tests 1-12 | mean | tests 13-16 |
|---|---|---|---|
| whole | 1/12 | 3.5 | 3/4 |
| bm25 | 2/12 | 3.3 | 1/4 |
| hybrid | 1/12 | 2.6 | 2/4 |
| lfm3q_bm25 | 1/12 | 2.6 | 3/4 |
