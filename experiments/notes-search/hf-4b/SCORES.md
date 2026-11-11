# notes-search scores

## Facts in the packet (tests 1-12; whole = everything in the notes)

| test | bm25_notags | bm25 | emb | hybrid | lfm3q_bm25 | lfm3q_hybrid | whole |
|---|---|---|---|---|---|---|---|
| 1 | 2/3 | 2/3 | 2/3 | 2/3 | 2/3 | 2/3 | 2/3 |
| 2 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| 3 | 1/4 | 1/4 | 3/4 | 1/4 | 1/4 | 1/4 | 4/4 |
| 4 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| 5 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 6 | 0/3 | 0/3 | 2/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| 7 | 2/4 | 2/4 | 1/4 | 1/4 | 1/4 | 1/4 | 3/4 |
| 8 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 | 0/2 | 2/2 |
| 9 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| 10 | 3/4 | 3/4 | 2/4 | 4/4 | 3/4 | 4/4 | 4/4 |
| 11 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 12 | 1/5 | 1/5 | 2/5 | 2/5 | 1/5 | 2/5 | 3/5 |
| **all facts** | **4/12** | **4/12** | **3/12** | **4/12** | **4/12** | **4/12** | **7/12** |
| **fact recall** | 20/39 (51%) | 20/39 (51%) | 21/39 (54%) | 19/39 (49%) | 19/39 (49%) | 19/39 (49%) | 30/39 (77%) |

## Notes

| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |
|---|---|---|---|---|---|---|
| 1 | 44 | 34 | 43 | 0 | 1 | 1032 |
| 2 | 65 | 59 | 61 | 0 | 4 | 1587 |
| 3 | 47 | 29 | 47 | 0 | 0 | 685 |
| 4 | 64 | 19 | 59 | 0 | 5 | 420 |
| 5 | 46 | 111 | 46 | 0 | 0 | 2054 |
| 6 | 61 | 55 | 57 | 0 | 4 | 949 |
| 7 | 50 | 87 | 48 | 0 | 2 | 2264 |
| 8 | 66 | 61 | 60 | 0 | 6 | 906 |
| 9 | 47 | 8 | 47 | 0 | 0 | 167 |
| 10 | 48 | 38 | 43 | 0 | 5 | 865 |
| 11 | 40 | 26 | 36 | 0 | 4 | 357 |
| 12 | 38 | 18 | 38 | 0 | 0 | 348 |
| 14 | 47 | 79 | 40 | 0 | 7 | 1636 |
| 15 | 67 | 24 | 67 | 0 | 0 | 537 |
| 16 | 41 | 47 | 37 | 0 | 4 | 566 |

## Time per note pass (estimated for the phone)

771 note passes. Prompt tokens: median 1071, 90th pct 2227, max 3790. Output tokens: median 300, 90th pct 300, max 622.

At 100 tok/s reading and 13.7 tok/s writing: median pass ~33 s, 90th pct ~44 s.
LFM3 query step: prompt median 155 tokens, output median 19: ~2.9 s before the answer starts. BM25 itself: milliseconds.

## LFM3's queries

- 1: `dino piñata party mom son little goblins date location`
- 2: `bathroom budget, money, cost, purchase, quote, savings, expenses.`
- 3: `saturday recipes easy dinner low effort no cooking hard stuff?`
- 4: `formats the due date column priyas new test expected "Oct 31, 2026, 10:30 PM" received "Nov 1, 2026, 3:30`
- 5: `pink flag, garage, gary, breakfast spot, Hanksville, gas station, trick, good stuff`
- 6: `lrb, molar theory, bo woke 5:20, bedtime 7:15, drooling chewing, run vs lr, breakthrough molars.`
- 7: `moose stories usage rights; public domain vs copyrighted; fair use for jokes; recent news articles; memes about moose; legal guidelines.`
- 8: `big kitchen listing landlord friday sign lease`
- 9: `Director of *Jaws* (Shark movie) is Peter Weir? Actually, Jaws directed by Steven Spielberg. The shark movie likely "Jaws" (1975). Director:`
- 10: `day-by-day plan trip; travel itinerary; schedule; upcoming events; details discussed earlier.`
- 11: `monthly revenue, shipping total, sales tax amount`
- 12: `paginated search over the orders table, likely in a REST API context. Need to recall prior discussion about endpoints, maybe from earlier notes. The user previously said: "Yes, that is the`
- 14: `Vincent van Gogh born, The Starry Night painted June 1889, calculate age difference`
- 15: `"riverside landlord hold unit until monday text"`
- 16: `Canberra population residents inhabitants city demographics.`
