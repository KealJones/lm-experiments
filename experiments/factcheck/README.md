# Draft -> fact-check

**Question (Keal, 2026-11-04):** small models are bad at most things, but can one get *one message* right if it answers
first and then a second pass of the same model reviews that answer, looks things up, and fixes it? Does it actually
catch its own mistakes, or just say "yeah, that's fine"? Also: does a structured source (Wikipedia / Wikidata) beat the
generic web search Squiggle has now, which finds pages *about* Emma Stone rather than her latest film?

## Setup

- **12 questions** ([`questions.json`](questions.json)) that a web lookup should settle easily, some in Keal's casual
  phrasing. Several are traps: "current" or "latest" facts that changed after the models' training (UK PM is now Andy
  Burnham, Spain won the 2026 World Cup, Emma Stone's latest is *Bugonia*, Saturn has the most moons, not Jupiter).
  Ground truth was checked on 2026-11-04.
- **Tools** ([`factcheck.py`](factcheck.py)): `search` (Wikipedia search, top 5 titles + snippets), `read_page`
  (a Wikipedia page, optionally only the paragraphs mentioning some words), `wikidata` (hard facts about one thing:
  dates, heights, office holders, filtered by property name). Today's date is in every system prompt.
- **Step 1, draft:** the model answers the question, up to 6 turns of tool use. 3 sampled drafts per question.
- **Step 2, review:** a fresh chat with the same model gets the question and the draft, the same tools, and must end
  with `VERDICT: RIGHT/WRONG` and `FINAL ANSWER: ...`. Two styles:
  - **plain**: Keal's words, "review this question and answer and tell me if it is good and right"
  - **strict**: "you are a strict fact-checker, assume it may be wrong or out of date, check every claim with the tools"
- **Planted wrong answers:** each model also reviews one known-wrong answer per question ("The capital of Australia is
  Sydney"), so the catch rate is measurable even when a model's own drafts are all right (or all wrong).
- **Scoring:** draft right; caught wrong drafts; false alarms on right drafts; final answer right; *fixed*
  (wrong -> right) and *broke* (right -> wrong, the trap: small models love to "fix" correct answers). Answers are
  graded by regex on the key fact; transcripts are kept for hand checks.
- **Models (Kaggle, 2x T4, free):** Qwen3 0.6B (thinking off), Llama 3.2 1B Instruct (ungated unsloth mirror),
  Qwen3.5 0.8B (if it loads), Qwen2.5 Coder 1.5B Instruct. Built by [`make_notebook.py`](make_notebook.py) ->
  [`factcheck.ipynb`](factcheck.ipynb), jobs `factcheck`, `factcheck-2` … `factcheck-4` in [`kaggle/done/`](../../kaggle/).

## Baseline: Claude Haiku (run 2026-11-04, as Claude Code subagents)

Same questions and the same two review prompts, but Haiku used ordinary web search (WebSearch plus fetching result
pages), not the Wikipedia/Wikidata tools. Each subagent handled 3 questions (drafts) or 6 items (reviews: 3 of Haiku's
real drafts and 3 planted wrong answers for *other* questions, shuffled, with opaque keys).
Raw: [`haiku/drafts.json`](haiku/drafts.json), [`haiku/reviews.json`](haiku/reviews.json).

| | drafts right | false alarms on right drafts | planted caught | planted fixed |
|---|---|---|---|---|
| plain review | 12/12 | 0/12 | 12/12 | 12/12 |
| strict review | 12/12 | 0/12 | 12/12 | 12/12 |

- All 12 drafts were right, including every "current" trap (Burnham, Spain, *Bugonia*, Saturn). The UK PM took it
  4 searches; most took 1.
- Both review styles caught and fixed every planted mistake with zero false alarms. The plain reviewer mostly didn't
  search for static facts (it just knew Canberra, 1930, Nolan) but did search for the current ones. The strict
  reviewer searched nearly every item.
- So at Haiku's size, the second pass adds nothing on questions this easy: the draft is already right. It's a
  ceiling to compare the small models against, not a test of the idea.

## Small models (Kaggle, 2x T4)

Four runs. Runs 1–2 were mostly broken by my harness bugs; the numbers below are from runs 3 and 4
([`kaggle-out-3/`](kaggle-out-3/RESULTS.md), [`kaggle-out-4/`](kaggle-out-4/RESULTS.md)), which share the same code
apart from the fixes listed at the bottom.

**Draft arms** (how the first answer is produced):
- **free**: tools offered, "answer briefly". Thinking off.
- **lookup**: "your memory is out of date and often wrong, ALWAYS look it up". Thinking off.
- **think**: free, with Qwen thinking on (how Squiggle runs Qwen3 0.6B).
- **force**: the first turn is prefilled with the start of a `search` call, so the model must search once.
- **read**: the code itself searches Wikipedia for the question and reads the top page's paragraphs that mention
  the question's key words, and puts both in the chat as tool results before the model says anything. Same
  evidence for every model. Reviews get the same evidence.

### Drafts right (of 36: 12 questions x 3 samples)

| | free | lookup | think | force | read |
|---|---|---|---|---|---|
| Qwen3 0.6B | 10 (28%) | 13 (36%) | 12 (33%) | 24 (67%) | 24 (67%) |
| Qwen3.5 0.8B | 14 (39%) | 22 (61%) | **27 (75%)** | 18 (50%) | 24 (67%) |
| Llama 3.2 1B | 2 (6%) | 3 (8%) | - | 4 (11%) | 5 (14%) |
| Qwen2.5 Coder 1.5B | 3 (8%) | 7 (19%) | - | 7 (19%) | 11 (31%) |
| *Claude Haiku (web search)* | *12/12* | | | | |

**The read arm splits cleanly on whether the evidence held the answer:**

| | answer in the injected evidence | answer not in it |
|---|---|---|
| Qwen3 0.6B | **21/21** | 3/15 |
| Qwen3.5 0.8B | **21/21** | 3/15 |
| Qwen2.5 Coder 1.5B | 11/24 | 0/12 |
| Llama 3.2 1B | 5/24 | 0/12 |

(The 3 "not in it" hits are UN Secretary-General, which they know from memory.) The naive retrieval missed on 5 of 12
questions: Emma Stone (top hit is her biography, not her filmography; it said *Harry Potter*), UK PM (the office's page
doesn't name the holder in the matched paragraphs; it said Tony Blair), World Cup (top hit was the knockout-stage page,
the matched paragraphs don't say who won; it said Brazil), Kilimanjaro (top hit was *Mount Meru*), UN SG.

### Does the second pass (review) fix anything?

Final answer right after review, own drafts only, vs. the draft:

| | draft | after plain review | after strict review |
|---|---|---|---|
| Qwen3 0.6B (read) | 67% | 67% | 53% |
| Qwen3 0.6B (force) | 67% | 67% | 56% |
| Qwen3.5 0.8B (think) | 75% | 61% | 61% |
| Qwen3.5 0.8B (read) | 67% | 64% | 58% |
| Qwen3.5 0.8B (lookup) | 61% | 64% | 56% |
| Llama 3.2 1B (force) | 11% | 3% | 25% |
| Qwen2.5 Coder 1.5B (free) | 8% | 42% | 33% |

- **Qwen3 0.6B's reviewer doesn't judge, it follows the prompt.** Plain says RIGHT to almost everything (caught 0–12%
  of its wrong drafts). Strict says WRONG to almost everything: 88–100% false alarms on right answers in every arm
  except think (where it went quiet instead: 38% caught, 0% false alarms). Even with the evidence in front of it
  (read arm), strict flagged 23 of 24 right answers.
- **Qwen3.5 0.8B is the most sensible reviewer and it still makes things worse:** with thinking on it broke 5–6 of
  27 right drafts and fixed 0–1 of 9 wrong ones. Its review also often skips the VERDICT line (14–36%).
- **The only times review helped were when the drafts were terrible:** Qwen2.5 Coder free (8% -> 42% plain; its
  reviewer used tools the drafter hadn't) and Llama force strict (11% -> 25%). Both still end below Qwen's drafts.
- **Planted wrong answers** ("the capital of Australia is Sydney"): the best was Qwen3.5 read + strict, 22/36 caught
  and 21/36 fixed. Haiku: 12/12 and 12/12 with either prompt.

### Other things that matter for Squiggle

- **Qwen3 0.6B only searches with thinking on.** Thinking off: 0 tool calls in free and lookup, even when told
  "ALWAYS look it up". Thinking on: 0.5 calls per draft (Keal's Squiggle chats show it calling tools most turns, with
  Squiggle's own prompt and tools).
- **Nobody follows up.** In the force arm every Qwen draft made exactly one search and answered from the snippets,
  which rarely contain the answer. Qwen3 0.6B got results titled "2026 FIFA World Cup final" and answered Brazil; got
  the PM's office page and invented "Sarah Hinton". No small model opened a page to find the answer.
- **Llama 3.2 1B over-calls tools and never lands:** 4–6 tool calls per draft, usually hits the 6-turn limit, and even
  with the answer in its context got 5/24. Wikidata property names copied from the tool description ("head of
  government" for Emma Stone) show up in every model.
- The "current" questions (World Cup, UK PM, Emma Stone) were wrong in 2 of 3 samples or worse for every small model
  in every arm. That's the retrieval, not the model: the evidence never contained the answer.

### Takeaways

1. **At 0.6–0.8B the model can read; it can't search.** Give Qwen3 0.6B a paragraph containing the answer and it's
   right every time. Ask it to find that paragraph and it mostly isn't.
2. **So the lever is the tool, not a review prompt.** Searching and choosing what to read should be done by code, and
   tools should return the answer, not pages about the subject: Wikidata's current office holder, a filmography sorted
   by date, the infobox field.
3. **Self-review by the same small model doesn't work.** Plain review approves; strict review rejects; neither tracks
   whether the answer is right. A better second pass is a mechanical check (is the answer actually in the retrieved
   text?) rather than the model's opinion.
4. Qwen3.5 0.8B with thinking on is the best small drafter here (75%), and Qwen3 0.6B is as good as it once the
   evidence is handed over. Llama 3.2 1B and Qwen2.5 Coder 1.5B are clearly worse at this.

### Harness bugs (and fixes), so nobody trusts run 1–2 numbers

- Run 1: Llama crashed in my call parser; Qwen2.5 Coder writes calls as prose + a ```json fence that I didn't parse;
  Qwen3.5 writes calls as `<function=search><parameter=query>` XML that I didn't parse either, so "Qwen3.5 never
  searched" was wrong; the Wikidata example said "height" where Wikidata says "elevation".
- Run 2: Llama 3.2's chat template rejects two tool calls in one turn; only the pilot ran.
- Run 3: Llama crashed again on a malformed call (empty `tool_calls` list, which its template rejects).
- Thinking was off for Qwen in runs 1–3, which is why Qwen3 0.6B looked unable to call tools at all.

## Spend

Kaggle free tier, 4 runs (about 7.5 h of Kaggle wall time including queueing; run 4 with thinking on took 2.8 h). Haiku baseline: a few cents of subagent usage.
