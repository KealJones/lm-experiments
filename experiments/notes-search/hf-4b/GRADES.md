# Blind grades (notes-search-4b)

Shuffled letters (mapping.json), graded against the context-packets keys, then unblinded.

| test | whole | bm25 | hybrid | lfm3q_bm25 |
|---|---|---|---|---|
| 1 | fail 3 | fail 2 | fail 3 | fail 3 |
| 3 | fail 4 | fail 3 | fail 3 | fail 1 |
| 4 | fail 3 | fail 3 | fail 2 | fail 7 |
| 5 | fail 6 | pass 8 | pass 8 | pass 9 |
| 7 | fail 1 | fail 0 | pass 8 | fail 6 |
| 9 | fail 2 | fail 0 | fail 2 | fail 0 |
| 10 | fail 3 | fail 3 | fail 5 | fail 3 |
| 11 | pass 10 | pass 10 | pass 10 | pass 10 |
| 12 | fail 0 | fail 2 | fail 1 | fail 2 |
| 14 | fail 1 | pass 10 | pass 10 | pass 10 |
| 15 | pass 10 | pass 10 | pass 9 | pass 10 |
| 16 | fail 1 | pass 8 | fail 1 | pass 9 |

| packet | tests 1-12 | mean | tests 13-16 |
|---|---|---|---|
| whole | 1/9 | 3.6 | 1/3 |
| bm25 | 2/9 | 3.4 | 3/3 |
| hybrid | 3/9 | 4.7 | 2/3 |
| lfm3q_bm25 | 2/9 | 4.6 | 3/3 |
