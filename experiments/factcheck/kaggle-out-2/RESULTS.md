# Draft -> fact-check: results

12 questions, 3 sampled drafts each, tools = Wikipedia search, Wikipedia page, Wikidata. Each draft is reviewed twice by the same model in a fresh chat: **plain** (Keal's wording) and **strict** (fact-checker, assume it's wrong).

**Own drafts** = the model reviews its own answers. **Planted** = it reviews a known-wrong answer per question (e.g. 'The capital of Australia is Sydney').

| model | draft right | review | caught wrong own drafts | false alarms on right drafts | final right | fixed (wrong->right) | broke (right->wrong) | planted caught | planted fixed | no verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-0.6B (lookup) | 0/2 (0%) | plain | 0/2 (0%) | - | 0/2 (0%) | 0/2 (0%) | - | 0/2 (0%) | 0/2 (0%) | 0/4 (0%) |
| Qwen3-0.6B (lookup) | 0/2 (0%) | strict | 2/2 (100%) | - | 0/2 (0%) | 0/2 (0%) | - | 2/2 (100%) | 0/2 (0%) | 0/4 (0%) |
| | tool calls per draft: 0.0 (search 0, read_page 0, wikidata 0) | | | | | | | | | |

## Drafts per question (✓ right / ✗ wrong, one mark per sample)

| question | qwen3/lookup |
|---|---|
| emma | ✗ |
| uk_pm | ✗ |
