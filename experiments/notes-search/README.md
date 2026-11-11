# Notes search: can LFM3's own notes plus a dumb search be Squiggle's fresh context?

Follow-up to [whiteboard](../whiteboard/) and [context-packets](../context-packets/). Keal's design (voice, 2026-11-10):
the packet for each new message is the last exchange plus the relevant lines of notes the model keeps itself, with
no chat history. Retrieval on the raw chat failed because throwaway corrections share no words with the later
question; the notes are short, clean and written by the model, so maybe a search over them works.

## Setup

- **Model:** LFM3 1.7B, Liquid's QAD Q4_0 GGUF on llama.cpp (native LFM3), same as Squiggle's CPU build.
- **Note pass** (separate from the reply, as it would run while the user reads): its own ~120-token system prompt,
  thinking off, max 200 tokens out. Input: the notes numbered, plus the latest exchange only. Output lines:
  `ADD: <fact> | tags: <plain words> | <kind>`, `CHANGE <n>: ...`, or `NONE`; the harness applies them.
  Tags (plain words someone would use to ask, plus a kind: date, place, money, person, rule, plan, number, other) are
  there to give BM25 something to match without a second model.
- **Packets** (per final question): the last exchange (user message whole, the reply's first 60 words) plus the top
  8 note lines from each of:
  - BM25 on the raw message, with tags / without tags
  - bge-small embeddings (33M parameters, ~35-130 MB)
  - hybrid (reciprocal rank fusion of the two)
  - an LFM3-written search query (thinking off, sees only the last exchange and the new message) into BM25 / hybrid
  - whole notes (ceiling)
- **Answers:** LFM3 with Squiggle PR 7's prompt and its real engine limits (1,024-token reply, 400-token thinking
  budget), handed the packet as the result of a `relevant_context` call it "already made". Arms: whole, BM25, hybrid,
  LFM3 query into BM25.
- **Timing:** every call logs its prompt and output tokens. Phone time is estimated from Keal's iPhone measurements of
  the LFM3 WebLLM build (13.7 tokens/s decode, first word in ~15 s with Squiggle's full prompt; lfm3-mlc README).

## Results

### Run 1 (`notes-search-1`, 19 min, about $0.25): the note pass was broken, by the prompt and the parser

- The prompt showed the format with placeholders (`ADD: <fact> | tags: <3-6 plain words…>`). LFM3 often copied them
  literally, and with thinking off it still thought on 318 of 833 passes (203 times it wrote "NONE (…)</think>NONE").
  Liquid's card warns thinking-off "can be inconsistent"; the rendering matches its template exactly.
- LFM3's natural style was plain bullet notes (344 outputs, often good: "- User plans to go on Saturday March 28th,
  the only day they had open"). The parser only took `ADD:` lines, so it dropped those and instead kept format lines
  quoted inside the thinking. Strictly parsed notes held 10/39 answer-key facts; every packet scored the same.
- Re-read leniently (`reparse.py`: bullets kept, thinking dropped) the notes hold 21/39 facts and all of them for 3/12
  tests, but miss the key throwaway lines (the party moving to March 22nd, Pearl's, the CI timezone), and are long
  (median ~750 words). Phone-time estimate as run: median note pass ~500 tokens in, 200 out (the cap) = ~20 s.

### Run 2 (`notes-search-2`): fixed note pass

A concrete bullet-style example unrelated to the tests, a parser that ignores thinking and takes bullets, and
Squiggle-style forced continuation when LFM3 thinks anyway. 22.5 min, about $0.30.

The opposite failure: LFM3 now wrote 300 tokens on every pass and never said NONE. 3,985 adds against 33 changes:
it re-states known facts every turn instead of changing them (chat 1's notes ended with 46 lines still saying the
14th and 6 saying the 22nd; "Party venue: Sky High" 23 times). The notes reached 3,000-8,800 words, longer than the
chats, and 5 chats (2, 4, 6, 13, 15) crashed when the note prompt outgrew the server's 14K-token slot. The note
prompt alone had a median of 5,600 tokens, which can't fit Squiggle's 4K window. Forced continuation never fired.

Answers, blind-graded ([hf-2/grades.json](hf-2/grades.json)), 11 chats:

| packet | pass | mean score |
|---|---|---|
| whole notes (6,800-13,800 tokens, over the 4K window, so 64 tokens left to reply) | 0/11 | 2.9 |
| BM25 on the raw message, top 8 lines | 3/11 | 3.5 |
| hybrid (BM25 + embeddings) | 3/11 | 3.1 |
| LFM3 writes the query, then BM25 | 4/11 | 4.3 |

When the packet lacked the fact, LFM3 kept calling `find` with new words until it ran out of tool rounds (3 here)
and never answered. Tags made no difference to BM25 (47% of facts with or without).

### Run 3 (`notes-search-3`): Keal's fix for the changes

Keal's suggestion: tell it to be extra sure to update facts that changed, with an unrelated example (Billy's
birthday, Mar 15 corrected to Dec 16), and let it delete lines. The prompt now says to write only new or changed
facts, never repeat one, that most exchanges add 0-2 lines, and has `- CHANGE n:` / `- DELETE n` with the Billy
example. The harness also skips exact repeats and, like the phone, fits the note prompt into 4K by hiding the oldest
lines. Answers get Squiggle's 6 tool rounds. 27 min, about $0.36.

**The notes now hold the facts, but old versions stay next to the new ones.**

| | run 2 | run 3 |
|---|---|---|
| adds | 3,985 | 2,368 |
| changes | 33 | 333 |
| exact repeats the harness skipped | - | 1,972 |
| answer-key facts anywhere in the notes (tests 1-12) | (5 chats crashed) | 36/39, all of them for 9/12 |
| notes size | 3,000-8,800 words | 1,400-4,700 words |

LFM3 still repeats itself constantly (the harness caught nearly as many repeats as it added lines), and when something
changes it usually adds a "was X, now Y" line instead of changing the old one: chat 1 has "Invitation date updated to
Sunday March 22nd (was Saturday March 14th)" but also four lines still saying Saturday March 14th. DELETE was used
once. The note prompt hit Squiggle's 4K and had to hide old lines on 200 of 833 passes, and LFM3 thought despite
thinking-off on 122 (forced continuation).

Facts in the packet ([hf-3/SCORES.md](hf-3/SCORES.md)): embeddings 59% (all facts for 4/12), BM25 44% with or without
tags (2/12), hybrid 44%, LFM3's query 38-41%.

Answers, blind-graded ([hf-3/GRADES.md](hf-3/GRADES.md)):

| packet | tests 1-12 | tests 13-16 |
|---|---|---|
| whole notes (3,300-8,700 tokens, mostly over the 4K window) | 1/12, mean 2.2 | 1/4 |
| BM25 on the raw message | 2/12, 2.9 | 4/4 |
| hybrid | 2/12, 3.4 | 2/4 |
| LFM3 query into BM25 | 2/12, 3.7 | 3/4 |
| *reference: LFM3 with the full chat (whiteboard-3)* | *5/12* | *4/4* |
| *reference: Opus-built packet (context-packets)* | *12/12* | |

Every packet is worse than just giving LFM3 the whole chat. Test 1 shows why: all three packets that reached an answer
said Saturday March 14th, because the stale lines outnumber the correction. Where the packet lacked the fact, LFM3
mostly asked the user or said it had no record (an improvement on run 2's endless `find` loops) but sometimes guessed
(test 7: two replies cleared the vetoed trash-can story).

**Phone time:** median note pass ~2,400 tokens in and 300 out, about 45 s at the estimated 100 tok/s reading and
13.7 tok/s writing. Far too slow even in the background.

**Spend:** run 1 $0.25, run 2 $0.30, run 3 $0.36: $0.91.

### Where this leaves it

The retrieval half works (milliseconds, and embeddings find 59% of the facts in noisy notes). The note-taking half is
the bottleneck: LFM3 with thinking off can't scan 100+ lines to see what's already there, so it repeats and appends
instead of fixing. Next, one change each against run 3:

1. The note pass sees only the lines that match the exchange (BM25 on it) plus the most recently touched lines, not
   all notes: a smaller prompt (faster) where the stale line is right in front of it when the correction arrives.
2. The note pass with thinking on, under Squiggle's 400-token budget.
3. Answer side, on run 3's notes: search with the last exchange as well as the new message, and a stop rule ("two
   empty searches: answer with what you have or ask").

### Runs 4a and 4b (in parallel, one change each against run 3)

Run 3's note pass put the notes in the *user* message, as a bulleted list, and asked for bullets back. Keal: notes
can't be the user's message. Looking at a real turn (chat 1, turn 9), the exchange was only about the memory leak, yet
LFM3 re-wrote the party lines after its memory-leak edit: it was continuing the list it was handed. The parser also let
in junk (`NONE`, "Add new fact from latest exchange: …", cut-off lines).

- **4a, native layout** (`--variant native`). Only the roles LFM3's template has (system, user, assistant, tool; no
  harness role, per Liquid's card and template): the system prompt is the note-taker's job; the real exchange goes in as
  real user and assistant turns; then a `read_notes` call it "already made" returns only the note lines BM25 matches to
  the exchange plus the three most recently touched; its edits go out as an `update_notes(add, change, delete)` tool
  call. Its output no longer looks like its notes, and the stale line is in view when a correction comes in.
- **4b, stricter parser** (`--variant strict`). Run 3 unchanged except the parser: rejects `NONE`, lines about the
  notes, cut-off lines, and adds whose words are 80% or more in one existing line.

Ran on a10g-small (the l4x1 jobs sat 2.5 h in Hugging Face's queue without a GPU and were cancelled, $0).

| | run 3 | 4a native layout | 4b strict parser |
|---|---|---|---|
| note passes | 833 | 833 | 771 (timed out at 45 min; chat 13 missing, 3 chats' answers missing) |
| lines added / changed / deleted | 2,368 / 333 / 1 | 541 / 6 / 1 | 693 / 479 / 2 |
| edits the harness refused | 1,972 exact repeats | 3 exact repeats | 2,563 near-repeats, 246 junk lines, 108 exact repeats |
| passes that wrote a reply instead of `update_notes` | - | 241 (29%) | - |
| passes that called `read_notes` again instead | - | 119 | - |
| chat 1's notes | 156 lines; 1 says Mar 22, 15 say Mar 14 | 54 lines; "Party moved to Sunday March 22nd" plus 4 stale Mar 14 lines | 34 lines; no Mar 22 at all |
| answer-key facts anywhere in the notes (tests 1-12) | 36/39, all of them for 9/12 | 32/39, 8/12 | 30/39, 7/12 |
| note-pass prompt, median / 90th pct | ~2,400 tokens | 861 / 984 | 1,071 / 2,227 |
| phone time per note pass, median (estimated) | ~45 s | ~12 s | ~33 s |

Answers, blind-graded ([hf-4a/GRADES.md](hf-4a/GRADES.md), [hf-4b/GRADES.md](hf-4b/GRADES.md)):

| packet | run 3, tests 1-12 | 4a, tests 1-12 | 4b, tests 1-12 (9 graded) |
|---|---|---|---|
| whole notes | 1/12, mean 2.2 | 1/12, 3.5 | 1/9, 3.6 |
| BM25 on the raw message | 2/12, 2.9 | 2/12, 3.3 | 2/9, 3.4 |
| hybrid | 2/12, 3.4 | 1/12, 2.6 | 3/9, 4.7 |
| LFM3 query into BM25 | 2/12, 3.7 | 1/12, 2.6 | 2/9, 4.6 |
| *reference: LFM3 with the full chat (whiteboard-3)* | *5/12* | | |

**4a (native layout) fixed the size and speed, not the answers.** With the notes as a tool result and its edits as a
tool call, LFM3 stopped copying the list: it added a quarter as many lines, the harness had almost nothing to refuse,
and a note pass is a quarter the size, ~12 s on the phone instead of ~45 s. Test 1 shows the layout working: every
packet now answers Sunday March 22nd (run 3's all said the 14th), because the correction went in as its own line. But
it almost never *changes* a line (6 changes in 833 passes; the 14th lines stay next to the 22nd), it lost a few facts
(32/39), and 29% of passes it answered the user in prose ("I checked my notes and didn't find…") instead of calling
`update_notes`, so those exchanges saved nothing. Answer quality didn't move: 1-2/12 per packet, mean scores 2.6-3.5.

**4b (strict parser) made it slower and lost the correction.** Refusing near-repeats kept the notes from ballooning,
but LFM3 still wrote 300 tokens per pass (it filled the cap on most passes), so the job ran out of time at 45 minutes.
It used CHANGE far more (479), but in chat 1 it changed the March 22nd line back out: the notes say only Saturday March
14th, and every answer to test 1 does too. The 9 tests that finished score about the same as run 3.

**Spend:** 4a $0.57, 4b $0.75 (hit its 45-minute cap). Notes-search total: $2.23.

### Where this leaves it

The native layout is the one to keep: it's what Liquid's template expects, it's 4x cheaper per pass, and the correction
in test 1 finally reached the answer. What it still can't do is maintain the notes: it appends and almost never
changes or deletes, and it talks to the user when it should be calling the tool. Neither layout gets the answers past
2/12, and LFM3 given the whole chat still gets 5/12, so notes plus search isn't ready to replace the chat in Squiggle's
fresh context yet. Ideas for 4a's two failures, not run:

1. Make "talked instead" impossible: the note pass offers only `update_notes` (no `read_notes`, which it re-called 119
   times) and treats prose as no edit, or uses a required tool choice where llama.cpp supports it.
2. Show the stale line next to the correction on purpose: when the exchange has a date, number or name that BM25 finds
   in an existing line, put that line first in `read_notes` and say in the system prompt that a changed fact is a
   `change`, not an `add`. Or let the harness drop older lines that a newer line contradicts on the same subject.
3. The answer side is now the bigger loss: even the whole notes pass only 1/12. A packet of notes plus the last few
   exchanges (not just one) may be the cheapest real gain.
