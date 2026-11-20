# Notes cleanup: can a pass over finished notes drop the stale lines without losing facts?

Follow-up to [notes-search](../notes-search/) run 4a. The native layout made LFM3's notes small and cheap to write,
but it almost never changes or deletes a line (6 changes, 1 delete in 833 passes), so old values sit next to new
ones: chat 1 has "Party moved to Sunday March 22nd" and four lines still saying March 14th. This tries cleaning the
notes afterwards instead of during the chat, the way a "dream" or consolidation pass would: once, in the background,
over the whole set.

## Setup

Input: run 4a's final notes for the 16 chats ([../notes-search/hf-4a](../notes-search/hf-4a)). Arms (`cleanup.py`):

- **raw:** 4a's notes as they are.
- **tidy** (no model): strips leftovers (`4.` / `12:` numbers LFM3 copied into its lines, JSON brackets, cut-off
  lines) and drops exact and near repeats, keeping the newest copy.
- **words** (no model): tidy, then "newest wins": an older line goes when a later line shares most of its words
  (swept 50-80%) but has different numbers.
- **newest** (bge-small embeddings): the same rule, but the later line also has to be close in meaning (cosine
  swept 0.75-0.9).
- **lfm3:** tidy, then LFM3 itself, once per group of related lines (embedding groups of up to 10), in 4a's native
  layout: the group comes back from a `read_notes` call, numbered oldest first, and the edits go out as an
  `update_notes(change, delete)` call. Thinking off, 300 tokens out, so each call fits Squiggle's 4K window.

Scored for free: answer-key facts still in the notes (notes-search's needles, tests 1-12), stale lines left on the
three trap tests (test 1 March 14th without the 22nd, test 2 the $2,200 plumber quote without the $1,800 one, test 6
the leaked 78.9 / 76.5 scores without the corrected 70.3 / 68.2), and size. Then LFM3 answers (whole notes and the
hybrid packet, through `notes_search.py --notes-from`), blind-graded like 4a.

## Results

### Local, no model ([local/SCORES.md](local/SCORES.md))

Hugging Face downloads are blocked from the machine this ran on, so only the arms that need no model ran here.

| arm | facts kept (tests 1-12) | all facts | stale lines t1 / t2 / t6 | lines | words |
|---|---|---|---|---|---|
| raw | 31/39 | 7/12 | 4 / 1 / 1 | 540 | 8,111 |
| tidy | 31/39 | 7/12 | 4 / 1 / 1 | 503 | 7,540 |
| words 50% | 30/39 | 7/12 | 2 / 1 / 0 | 479 | 7,198 |
| words 60% | 31/39 | 7/12 | 2 / 1 / 0 | 490 | 7,341 |
| words 70% | 31/39 | 7/12 | 4 / 1 / 0 | 498 | 7,451 |

**A word-overlap rule is too blunt to trust.** At 60% it cleared two of test 1's stale lines and test 6's leaked
score without losing an answer-key fact, but it also threw away lines that were right: run-a's 71.4 score (a later
run line had different numbers), "8 inches is the corrected length" (a correction!), and test 6's "run-b: 70.3,
corrected from 78.9". Different runs, cups of coffee and party lines all look alike in words. The two test 1 lines it
left are the birthday itself (March 14th really is Milo's birthday; only the party moved), so that count overstates
how stale test 1 is. Tidying only saves 7% of the words: most of 4a's size is real, distinct lines.

### On Hugging Face (`job.json`, not run yet)

The embedding and LFM3 arms, plus answers on the newest-0.8 and lfm3 notes (4a's own answers are the raw control).
a10g-small, 40-minute cap: at most $0.67. Waiting on a go-ahead.

## Spend

$0 so far.
