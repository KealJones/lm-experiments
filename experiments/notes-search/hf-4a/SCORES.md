# notes-search scores

## Facts in the packet (tests 1-12; whole = everything in the notes)

| test | bm25_notags | bm25 | emb | hybrid | lfm3q_bm25 | lfm3q_hybrid | whole |
|---|---|---|---|---|---|---|---|
| 1 | 1/3 | 1/3 | 1/3 | 1/3 | 1/3 | 1/3 | 3/3 |
| 2 | 2/4 | 2/4 | 1/4 | 2/4 | 1/4 | 2/4 | 4/4 |
| 3 | 1/4 | 1/4 | 4/4 | 2/4 | 2/4 | 3/4 | 4/4 |
| 4 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 |
| 5 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| 6 | 1/3 | 1/3 | 2/3 | 1/3 | 0/3 | 0/3 | 2/3 |
| 7 | 1/4 | 1/4 | 2/4 | 2/4 | 2/4 | 2/4 | 3/4 |
| 8 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 |
| 9 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| 10 | 2/4 | 2/4 | 2/4 | 2/4 | 2/4 | 2/4 | 4/4 |
| 11 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 12 | 3/5 | 3/5 | 3/5 | 4/5 | 3/5 | 4/5 | 5/5 |
| **all facts** | **2/12** | **2/12** | **3/12** | **2/12** | **1/12** | **1/12** | **8/12** |
| **fact recall** | 16/39 (41%) | 16/39 (41%) | 20/39 (51%) | 19/39 (49%) | 14/39 (36%) | 17/39 (44%) | 32/39 (82%) |

## Notes

| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |
|---|---|---|---|---|---|---|
| 1 | 44 | 54 | 44 | 0 | 0 | 665 |
| 2 | 65 | 39 | 65 | 0 | 0 | 604 |
| 3 | 47 | 35 | 47 | 0 | 0 | 521 |
| 4 | 64 | 51 | 64 | 0 | 0 | 726 |
| 5 | 46 | 29 | 46 | 0 | 0 | 456 |
| 6 | 61 | 56 | 60 | 0 | 1 | 906 |
| 7 | 50 | 46 | 50 | 0 | 0 | 701 |
| 8 | 66 | 40 | 66 | 0 | 0 | 555 |
| 9 | 47 | 2 | 47 | 0 | 0 | 23 |
| 10 | 48 | 20 | 48 | 0 | 0 | 287 |
| 11 | 40 | 14 | 40 | 0 | 0 | 146 |
| 12 | 38 | 17 | 38 | 0 | 0 | 423 |
| 13 | 62 | 54 | 62 | 0 | 0 | 849 |
| 14 | 47 | 34 | 47 | 0 | 0 | 547 |
| 15 | 67 | 33 | 67 | 0 | 0 | 510 |
| 16 | 41 | 16 | 41 | 0 | 0 | 192 |

## Time per note pass (estimated for the phone)

833 note passes. Prompt tokens: median 861, 90th pct 984, max 1173. Output tokens: median 44, 90th pct 99, max 616.

At 100 tok/s reading and 13.7 tok/s writing: median pass ~12 s, 90th pct ~17 s.
LFM3 query step: prompt median 155 tokens, output median 18: ~2.9 s before the answer starts. BM25 itself: milliseconds.

## LFM3's queries

- 1: `dino piñata party mom son little goblins date location`
- 2: `bathroom budget, bathroom purchase, bathroom cost, bathroom money, bathroom finances, bathroom spending.`
- 3: `saturday recipes easy dinner low effort no cooking hard stuff?`
- 4: `formats the due date column priyas new test expected "Oct 31, 2026, 10:30 PM" received "Nov 1, 2026, 3:30`
- 5: `pink flag garage gary breakout trip route bookings Hanksville breakfast spot trick`
- 6: `lr type leaky vs real win run bo molar drool 5:20 wake 9 days bedtime 7:15`
- 7: `moose stories usage rights; public domain vs copyrighted; fair use for jokes; recent news articles; memes about moose; legal guidelines.`
- 8: `big kitchen listings landlord friday sign lease`
- 9: `Director of *Jaws* (Shark movie) is Peter Weir? Actually, Jaws directed by Steven Spielberg. The shark movie likely "Jaws" (1975). Director:`
- 10: `day-by-day plan trip; travel itinerary; schedule; upcoming events; details discussed earlier.`
- 11: `monthly revenue, shipping total, sales tax amount`
- 12: `paginated search, orders table, endpoint, SQL query, API route.`
- 13: `(2+2)/3 or 2+2/3?`
- 14: `Vincent van Gogh born, The Starry Night painted June 1889, calculate age.`
- 15: `"riverside landlord hold unit until monday text"`
- 16: `Canberra population residents inhabitants demographics.`
