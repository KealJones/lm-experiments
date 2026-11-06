# Context packets: answer from a small packet instead of the whole conversation

**Question:** If a front layer reads the whole chat and writes a ~350-word packet (a gist, what the vague words in
the new message point to, and only the facts that matter), can the model answer from just that packet as well as
it can from the full history?

The idea: a small model can't hold a long conversation, and even big ones carry everything all the time. So one
layer resolves the references ("that party thing", "the gas station dude") and pulls in only what the current
message needs. Then the main model answers that one message fresh. The question is whether it loses anything.

## What was tested

- **16 test conversations**, written by Sonnet subagents:
  - **8 messy (1–8):** 5,000–6,500 words each. Casual, swearing, typos, run-ons, three topics jumping around. Each
    one hides a trap: a fact changed later in a throwaway line, a total built from four scattered mentions,
    constraints dropped one at a time, a config detail that explains a much later error, a place named once in a
    story, a score corrected after a data leak, a nickname shared with a houseplant, and a dealbreaker the user
    breaks without noticing.
  - **4 clean baselines (9–12):** plain language, no traps. A trivia session that comes back to "the director of
    that shark movie", a Japan trip, chained business arithmetic, and a FastAPI endpoint with team rules stated early.
  - **4 last-message follow-ups (13–16):** a long messy chat, then "whats 2+2" / "4" / "ok now divide that by 3".
    Only the previous turn matters, and the packet layer must not lose it.
- **6 noisy-context cases (N1–N6):** hand-written packets stuffed with junk. Other people's birthdays next to a web
  snippet with Emma Stone's, an old and a new Eiffel Tower height, a forum post with the wrong year for the Berlin
  Wall, a question whose answer isn't there at all.
- **Packet builders:** Opus, Sonnet and Haiku, all with the same prompt (`data/instructions/builder.md`): 350-word cap,
  GIST / REFERENCES RESOLVED / RELEVANT FACTS, latest version of any changed fact, don't answer.
- **Answerers:** Opus and Haiku. Every answerer ran as a fresh subagent that could read only its one input file.
- **Grading:** one blind Opus grader per test, given the answer key and traps and the replies under shuffled letters
  (`data/keys/mapping.json` unshuffles them). It scored each reply 0–10 and gave a pass/fail.

## Results (Claude Code subagents, 6 Nov 2026, ~150 agent runs, no GPU spend): the packet matched full history at 7% of the words

| Model answering, and what it saw | Words seen (avg, 1–12) | Messy 1–8 | Clean 9–12 | Last-message 13–16 | All of 1–12 |
|---|---|---|---|---|---|
| Opus, full history | 5,375 | 8/8 pass, 8.9 | 3/4, 8.8 | – | 11/12, 8.8 |
| Opus, Opus packet | 363 | 8/8, 9.1 | 4/4, 8.8 | 4/4, 9.5 | 12/12, 9.0 |
| Opus, Sonnet packet | 388 | 8/8, 9.0 | 4/4, 8.8 | – | 12/12, 8.9 |
| Opus, Haiku packet | 358 | 7/8, 8.5 | 4/4, 8.5 | 3/4, 8.2 | 11/12, 8.5 |
| Haiku, full history | 5,375 | 7/8, 8.0 | 4/4, 8.5 | – | 11/12, 8.2 |
| Haiku, Opus packet | 363 | 7/8, 8.5 | 3/4, 6.5 | – | 10/12, 7.8 |

Noisy-context cases: Opus 6/6 (60/60), Haiku 6/6 (58/60), Sonnet 6/6 (55/60). No model was fooled by junk.

- **The packet lost nothing that mattered.** Opus answering from a 363-word Opus packet passed all 12 main tests.
  Its one full-history miss (the Japan trip) was overpacking a day, not a recall problem. Every trap, including
  the date that moved in a throwaway line and the carpet dealbreaker, survived compression.
- **The front layer is where it breaks.** Both failures behind a Haiku packet trace straight back to the packet.
  On the dinner party, Haiku's packet listed ginger beer as a drink and left the brother-in-law's dessert open.
  Opus's packet said "no spicy ginger beer" and "dessert cancelled". On "divide that by 3", Haiku's packet said
  "that" *most likely* means the 4, then listed every eval score as other candidates. The answerer hedged exactly
  the way the packet did. The answerer trusts the packet, so the packet's mistakes become the answer's.
- **A good packet didn't lift Haiku.** Haiku from an Opus packet did slightly worse than Haiku from the full history
  (10/12 vs 11/12). Its misses were answering, not finding: an incomplete table, and declining to name any December
  18 event. Haiku with the full history missed one constraint (cilantro). At this length, Haiku's problem isn't
  holding the context.
- **Junk in the context barely mattered.** All three models picked the right fact out of tangential and wrong
  retrieval. The worst of it: on the "what's my sister's name" case, Sonnet mentioned "your son Milo", who only
  exists in two of the other cases.

## What this doesn't show

- **The conversations are short.** About 8,000 tokens each, where full history doesn't hurt a frontier model. The
  real test of the idea is 50k–200k tokens, or a small model with a 4k window, where the full history doesn't fit.
- **It's near the ceiling.** Almost everything passed, and with 12 tests a one-item difference is noise.
- **Synthetic data, one grader.** Sonnet wrote the conversations, Opus graded, and the grader made judgement calls
  (noted in `data/grading/`). Two generator quirks made tests easier: conversation 2 already contains the final
  question in its last turn, and conversation 11 ends with the assistant restating every number.
- **The packet builder saw the whole conversation.** This tests whether a packet is *enough*, not whether a
  cheap layer can find the right bits without reading everything.
- **The subagents could see the account's saved memory.** Two of the generated conversations, and several
  packets, picked up details of the real account owner (his name, his son's name, and other personal details).
  The packets also called the synthetic user by that name. None of the tested facts depended on it. Those details
  were replaced or removed in `data/` after the run, so a few packets are a handful of words shorter than what the
  model actually saw. Next time, run the agents with memory off.
- **Side effects.** Several Haiku subagents scheduled stray reminders and used Bash despite read/write-only rules.
  This is noted only because it shows how Haiku behaves as an agent. It doesn't affect the scores.

## Next

- Long conversations (real Claude history, 50k+ tokens), where full history is expected to slip.
- A builder that doesn't read everything: retrieval over chunks plus a rolling gist, then the packet.
- The same test with a 1B answerer, which is the case this is really for.

## Files

`data/convs/` conversations, `data/questions/` final messages, `data/keys/` answer keys and the blind mapping,
`data/packets_*/` packets, `data/answers/` replies (`full`, `opuspkt`, `sonnetpkt`, `haikupkt` are Opus answering;
`haikufull` and `haikuXopuspkt` are Haiku), `data/grading/` grader scores, `data/noisy/` noisy cases and replies,
`data/instructions/` every prompt used.
