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
  [`factcheck.ipynb`](factcheck.ipynb), job [`kaggle/queue/factcheck.json`](../../kaggle/).

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

## Small models (Kaggle)

Pending: results land in `kaggle-out/` (`RESULTS.md`, transcripts in `results_full_*.json`).

## Spend

Kaggle free tier (counts against the weekly GPU quota). Haiku baseline: a few cents of subagent usage.
