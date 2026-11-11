# notes-search scores

## Facts in the packet (tests 1-12; whole = everything in the notes)

| test | bm25_notags | bm25 | emb | hybrid | lfm3q_bm25 | lfm3q_hybrid | whole |
|---|---|---|---|---|---|---|---|
| 1 | 1/3 | 1/3 | 0/3 | 1/3 | 1/3 | 2/3 | 3/3 |
| 3 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 4/4 |
| 5 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 7 | 2/4 | 2/4 | 2/4 | 2/4 | 1/4 | 1/4 | 4/4 |
| 8 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 |
| 9 | 2/2 | 2/2 | 1/2 | 2/2 | 1/2 | 1/2 | 2/2 |
| 10 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 4/4 |
| 11 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 12 | 3/5 | 3/5 | 2/5 | 2/5 | 3/5 | 2/5 | 5/5 |
| **all facts** | **3/12** | **3/12** | **2/12** | **3/12** | **2/12** | **2/12** | **9/12** |
| **fact recall** | 14/30 (47%) | 14/30 (47%) | 11/30 (37%) | 13/30 (43%) | 12/30 (40%) | 12/30 (40%) | 30/30 (100%) |

## Notes

| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |
|---|---|---|---|---|---|---|
| 1 | 44 | 541 | 44 | 0 | 0 | 6674 |
| 3 | 47 | 401 | 47 | 0 | 0 | 7616 |
| 5 | 46 | 297 | 46 | 0 | 0 | 7544 |
| 7 | 50 | 366 | 50 | 0 | 0 | 7737 |
| 8 | 66 | 502 | 66 | 0 | 0 | 7777 |
| 9 | 47 | 373 | 47 | 0 | 0 | 5590 |
| 10 | 48 | 316 | 48 | 0 | 0 | 5869 |
| 11 | 40 | 211 | 39 | 0 | 1 | 3286 |
| 12 | 38 | 297 | 38 | 0 | 0 | 6244 |
| 14 | 47 | 260 | 47 | 0 | 0 | 8832 |
| 16 | 41 | 421 | 41 | 0 | 0 | 5207 |

## Time per note pass (estimated for the phone)

514 note passes. Prompt tokens: median 5608, 90th pct 10876, max 13777. Output tokens: median 300, 90th pct 300, max 300.

At 100 tok/s reading and 13.7 tok/s writing: median pass ~78 s, 90th pct ~131 s.
LFM3 query step: prompt median 150 tokens, output median 18: ~2.8 s before the answer starts. BM25 itself: milliseconds.

## LFM3's queries

- 1: `dino piñata party mom son little goblins date location`
- 3: `saturday recipes easy dinner low effort no cooking hard stuff?`
- 5: `pink flag, garage, gary, breakfast spot, Hanksville, gas station, trick, good stuff`
- 7: `moose stories usage rights; public domain vs copyrighted; fair use for jokes; recent news articles; folklore references; social media memes.`
- 8: `big kitchen listings landlord friday sign lease`
- 9: `Director of *Jaws* (Shark movie) is Peter Weir? Actually, Jaws directed by Steven Spielberg. The shark movie likely "Jaws" (1975). Director:`
- 10: `day-by-day plan trip; travel itinerary; schedule; upcoming events; details discussed earlier.`
- 11: `monthly revenue, shipping total, sales tax amount`
- 12: `paginated search, orders table, endpoint, API route, SQL query, pagination.`
- 14: `Vincent van Gogh born, The Starry Night painted June 1889, calculate his age`
- 16: `Canberra population residents inhabitants demographics.`
