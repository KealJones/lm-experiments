# notes-search scores

## Facts in the packet (tests 1-12; whole = everything in the notes)

| test | bm25_notags | bm25 | emb | hybrid | lfm3q_bm25 | lfm3q_hybrid | whole |
|---|---|---|---|---|---|---|---|
| 1 | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 | 1/3 | 3/3 |
| 2 | 1/4 | 1/4 | 0/4 | 1/4 | 0/4 | 1/4 | 4/4 |
| 3 | 1/4 | 1/4 | 4/4 | 0/4 | 0/4 | 0/4 | 4/4 |
| 4 | 0/2 | 0/2 | 2/2 | 0/2 | 0/2 | 0/2 | 2/2 |
| 5 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 6 | 2/3 | 2/3 | 2/3 | 2/3 | 0/3 | 0/3 | 3/3 |
| 7 | 3/4 | 3/4 | 3/4 | 3/4 | 3/4 | 3/4 | 3/4 |
| 8 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 |
| 9 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| 10 | 0/4 | 0/4 | 2/4 | 1/4 | 3/4 | 1/4 | 4/4 |
| 11 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 12 | 3/5 | 3/5 | 3/5 | 3/5 | 2/5 | 2/5 | 4/5 |
| **all facts** | **2/12** | **2/12** | **4/12** | **2/12** | **2/12** | **2/12** | **9/12** |
| **fact recall** | 17/39 (44%) | 17/39 (44%) | 23/39 (59%) | 17/39 (44%) | 16/39 (41%) | 15/39 (38%) | 36/39 (92%) |

## Notes

| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |
|---|---|---|---|---|---|---|
| 1 | 44 | 156 | 43 | 2 | -1 | 4267 |
| 2 | 65 | 85 | 64 | 1 | 0 | 1781 |
| 3 | 47 | 220 | 47 | 0 | 0 | 4655 |
| 4 | 64 | 127 | 60 | 0 | 4 | 2430 |
| 5 | 46 | 147 | 46 | 0 | 0 | 3111 |
| 6 | 61 | 162 | 52 | 0 | 9 | 3746 |
| 7 | 50 | 82 | 50 | 1 | -1 | 1405 |
| 8 | 66 | 129 | 66 | 1 | -1 | 3226 |
| 9 | 47 | 111 | 47 | 0 | 0 | 2057 |
| 10 | 48 | 93 | 41 | 3 | 4 | 1794 |
| 11 | 40 | 201 | 38 | 0 | 2 | 2461 |
| 12 | 38 | 79 | 38 | 1 | -1 | 1987 |
| 13 | 62 | 170 | 54 | 0 | 8 | 3362 |
| 14 | 47 | 118 | 46 | 1 | 0 | 2710 |
| 15 | 67 | 302 | 63 | 0 | 4 | 4212 |
| 16 | 41 | 187 | 40 | 0 | 1 | 2392 |

## Time per note pass (estimated for the phone)

833 note passes. Prompt tokens: median 2409, 90th pct 3781, max 3796. Output tokens: median 300, 90th pct 423, max 622.

At 100 tok/s reading and 13.7 tok/s writing: median pass ~46 s, 90th pct ~69 s.
LFM3 query step: prompt median 155 tokens, output median 19: ~2.9 s before the answer starts. BM25 itself: milliseconds.

## LFM3's queries

- 1: `dino piñata party mom location date goblins`
- 2: `bathroom budget, money, cost, purchase, quote, savings, expenses.`
- 3: `saturday recipes easy dinner low effort no cooking hard stuff?`
- 4: `formats the due date column priyas new test Expected: "Oct 31, 2026, 10:30 PM" Received: "Nov 1, 2026, 3`
- 5: `pink flag garage gary breakout trip route bookings Hanksville breakfast spot trick`
- 6: `lr type leaky vs real win run bo molar drool 5:20 wake 9 days bedtime 7:15`
- 7: `moose stories usage rights; public domain vs copyrighted; fair use for jokes; recent news articles; memes about moose; legal guidelines.`
- 8: `big kitchen listings landlord friday sign lease`
- 9: `Director of *Jaws* (Shark movie) is Peter Weir? Actually, Jaws directed by Steven Spielberg. The shark movie likely "Jaws" (1975). Director:`
- 10: `day-by-day plan trip; travel itinerary; schedule; upcoming events; details discussed earlier.`
- 11: `$33,320 - $3,025 - $2,748.90 = 27,546.10`
- 12: `paginated search over the orders table, likely in a REST API context. Need to recall prior discussion about endpoints, maybe from earlier notes. The user mentions "the new message" and asks what`
- 13: `(2+2)/3 or 2+2/3?`
- 14: `Vincent van Gogh born, The Starry Night painted June 1889, calculate age.`
- 15: `"riverside landlord hold unit until monday text"`
- 16: `Canberra population residents inhabitants demographics.`
