# notes-search scores

## Facts in the packet (tests 1-12; whole = everything in the notes)

| test | bm25_notags | bm25 | emb | hybrid | lfm3q_bm25 | lfm3q_hybrid | whole |
|---|---|---|---|---|---|---|---|
| 1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| 2 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| 3 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| 4 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| 5 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| 6 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| 7 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| 8 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| 9 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| 10 | 2/4 | 2/4 | 2/4 | 2/4 | 2/4 | 2/4 | 2/4 |
| 11 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 12 | 4/5 | 4/5 | 3/5 | 3/5 | 4/5 | 4/5 | 4/5 |
| **all facts** | **1/12** | **1/12** | **1/12** | **1/12** | **1/12** | **1/12** | **1/12** |
| **fact recall** | 10/39 (26%) | 10/39 (26%) | 9/39 (23%) | 9/39 (23%) | 10/39 (26%) | 10/39 (26%) | 10/39 (26%) |

## Notes

| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |
|---|---|---|---|---|---|---|
| 1 | 44 | 5 | 5 | 26 | 13 | 125 |
| 2 | 65 | 19 | 18 | 22 | 25 | 355 |
| 3 | 47 | 5 | 5 | 32 | 10 | 97 |
| 4 | 64 | 25 | 22 | 53 | -11 | 1015 |
| 5 | 46 | 13 | 12 | 19 | 15 | 217 |
| 6 | 61 | 10 | 9 | 52 | 0 | 227 |
| 7 | 50 | 9 | 9 | 33 | 8 | 166 |
| 8 | 66 | 16 | 11 | 46 | 9 | 286 |
| 9 | 47 | 4 | 4 | 46 | -3 | 232 |
| 10 | 48 | 8 | 8 | 39 | 1 | 286 |
| 11 | 40 | 4 | 4 | 39 | -3 | 116 |
| 12 | 38 | 14 | 10 | 33 | -5 | 444 |
| 13 | 62 | 27 | 27 | 15 | 20 | 519 |
| 14 | 47 | 8 | 8 | 26 | 13 | 152 |
| 15 | 67 | 12 | 11 | 49 | 7 | 219 |
| 16 | 41 | 17 | 8 | 41 | -8 | 221 |

## Time per note pass (estimated for the phone)

833 note passes. Prompt tokens: median 502, 90th pct 936, max 2017. Output tokens: median 200, 90th pct 200, max 200.

At 100 tok/s reading and 13.7 tok/s writing: median pass ~20 s, 90th pct ~24 s.
LFM3 query step: prompt median 155 tokens, output median 29: ~3.7 s before the answer starts. BM25 itself: milliseconds.

## LFM3's queries

- 1: `dino piñata party mom son little goblins date location`
- 2: `bathroom budget, bathroom purchase, bathroom cost, bathroom money, bathroom finances, bathroom spending.`
- 3: `saturday recipes easy dinner low effort no cooking hard stuff?`
- 4: `formats due date column; priyas test "formats the due date column"; Expected: "Oct 31, 2026, 10:30 PM" Received: "Nov 1`
- 5: `pink flag garage gary breakout trip route bookings Hanksville breakfast spot trick`
- 6: `lr type leaky vs real win run bo molar drool 5:20 wake 9 days bedtime 7:15`
- 7: `moose stories usage rights; public domain vs copyrighted; fair use for jokes; recent news articles; folklore references; social media memes.`
- 8: `big kitchen listings landlord friday sign lease`
- 9: `<think>We need to parse the user's latest message. The user asks: "Going back to the director of that shark movie from the start, what else notable happened on the exact day he was born`
- 10: `day-by-day plan; trip; organize; schedule; travel itinerary; details.`
- 11: `monthly revenue, shipping total, sales tax amount`
- 12: `<think>We need to find what the new message needs looked up. The user asks: "Can you write the endpoint for paginated search over the orders table that we discussed?" This is a request for`
- 13: `2+2 divided by 3, or (2+2)/3?</think>(2+2)/3 or 2+2/3?`
- 14: `Vincent van Gogh birth year, Starry Night painting date, age calculation.</think>Vincent van Gogh born, The Starry Night painted June 1889, calculate age.`
- 15: `<think>We need to write a search query for the notes of this chat: what does the new message need looked up? The user asks: "Last exchange: User: ... You: Sure, here`
- 16: `<think>We need to find a search query for the notes of this chat. The last exchange: User asked about capital of Australia, I answered Canberra. New message: "And roughly how many people`
