# Draft -> fact-check: results

12 questions, 3 sampled drafts each, tools = Wikipedia search, Wikipedia page, Wikidata. Each draft is reviewed twice by the same model in a fresh chat: **plain** (Keal's wording) and **strict** (fact-checker, assume it's wrong).

**Own drafts** = the model reviews its own answers. **Planted** = it reviews a known-wrong answer per question (e.g. 'The capital of Australia is Sydney').

| model | draft right | review | caught wrong own drafts | false alarms on right drafts | final right | fixed (wrong->right) | broke (right->wrong) | planted caught | planted fixed | no verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen/Qwen2.5-Coder-1.5B-Instruct | 3/36 (8%) | plain | 4/33 (12%) | 0/3 (0%) | 15/36 (42%) | 12/33 (36%) | 0/3 (0%) | 1/36 (3%) | 0/36 (0%) | 1/72 (1%) |
| Qwen/Qwen2.5-Coder-1.5B-Instruct | 3/36 (8%) | strict | 9/33 (27%) | 0/3 (0%) | 11/36 (31%) | 8/33 (24%) | 0/3 (0%) | 12/36 (33%) | 4/36 (11%) | 5/72 (7%) |
| | tool calls per draft: 1.4 (search 4, read_page 13, wikidata 34) | | | | | | | | | |
| Qwen/Qwen3-0.6B | 11/36 (31%) | plain | 0/25 (0%) | 0/11 (0%) | 11/36 (31%) | 0/25 (0%) | 0/11 (0%) | 0/36 (0%) | 0/36 (0%) | 0/72 (0%) |
| Qwen/Qwen3-0.6B | 11/36 (31%) | strict | 25/25 (100%) | 11/11 (100%) | 8/36 (22%) | 0/25 (0%) | 3/11 (27%) | 36/36 (100%) | 10/36 (28%) | 0/72 (0%) |
| | tool calls per draft: 0.0 (search 0, read_page 0, wikidata 0) | | | | | | | | | |
| Qwen/Qwen3.5-0.8B | 15/36 (42%) | plain | 9/21 (43%) | 1/15 (7%) | 16/36 (44%) | 2/21 (10%) | 1/15 (7%) | 12/36 (33%) | 8/36 (22%) | 1/72 (1%) |
| Qwen/Qwen3.5-0.8B | 15/36 (42%) | strict | 8/21 (38%) | 1/15 (7%) | 15/36 (42%) | 2/21 (10%) | 2/15 (13%) | 13/36 (36%) | 7/36 (19%) | 9/72 (12%) |
| | tool calls per draft: 0.0 (search 0, read_page 0, wikidata 0) | | | | | | | | | |

## Drafts per question (✓ right / ✗ wrong, one mark per sample)

| question | coder | qwen3 | qwen35 |
|---|---|---|---|
| emma | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| uk_pm | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| wc2026 | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| pluto | ✗✗✗ | ✗✗✗ | ✓✓✓ |
| australia | ✗✗✗ | ✓✓✓ | ✗✓✗ |
| oppenheimer | ✗✗✗ | ✗✗✗ | ✓✓✗ |
| kilimanjaro | ✗✓✓ | ✓✗✗ | ✗✗✓ |
| moons | ✗✗✗ | ✗✓✗ | ✗✗✗ |
| frankenstein | ✗✗✗ | ✓✓✓ | ✓✓✓ |
| platypus | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| berlin | ✗✗✓ | ✓✓✓ | ✓✓✓ |
| un_sg | ✗✗✗ | ✗✗✗ | ✓✗✓ |
