# Draft -> fact-check: results

12 questions, 3 sampled drafts each, tools = Wikipedia search, Wikipedia page, Wikidata. Each draft is reviewed twice by the same model in a fresh chat: **plain** (Keal's wording) and **strict** (fact-checker, assume it's wrong).

**Own drafts** = the model reviews its own answers. **Planted** = it reviews a known-wrong answer per question (e.g. 'The capital of Australia is Sydney').

| model | draft right | review | caught wrong own drafts | false alarms on right drafts | final right | fixed (wrong->right) | broke (right->wrong) | planted caught | planted fixed | no verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder-1.5B-Instruct (force) | 7/36 (19%) | plain | 10/29 (34%) | 5/7 (71%) | 5/36 (14%) | 2/29 (7%) | 4/7 (57%) | - | - | 4/36 (11%) |
| Qwen2.5-Coder-1.5B-Instruct (force) | 7/36 (19%) | strict | 17/29 (59%) | 4/7 (57%) | 3/36 (8%) | 3/29 (10%) | 7/7 (100%) | - | - | 7/36 (19%) |
| | tool calls per draft: 2.9 (search 64, read_page 42, wikidata 0) | | | | | | | | | |
| Qwen2.5-Coder-1.5B-Instruct (free) | 3/36 (8%) | plain | 8/33 (24%) | 0/3 (0%) | 15/36 (42%) | 12/33 (36%) | 0/3 (0%) | 1/36 (3%) | 0/36 (0%) | 0/72 (0%) |
| Qwen2.5-Coder-1.5B-Instruct (free) | 3/36 (8%) | strict | 12/33 (36%) | 1/3 (33%) | 12/36 (33%) | 9/33 (27%) | 0/3 (0%) | 13/36 (36%) | 3/36 (8%) | 7/72 (10%) |
| | tool calls per draft: 2.2 (search 22, read_page 14, wikidata 44) | | | | | | | | | |
| Qwen2.5-Coder-1.5B-Instruct (lookup) | 7/36 (19%) | plain | 15/29 (52%) | 1/7 (14%) | 10/36 (28%) | 4/29 (14%) | 1/7 (14%) | - | - | 0/36 (0%) |
| Qwen2.5-Coder-1.5B-Instruct (lookup) | 7/36 (19%) | strict | 9/29 (31%) | 1/7 (14%) | 3/36 (8%) | 1/29 (3%) | 5/7 (71%) | - | - | 4/36 (11%) |
| | tool calls per draft: 1.8 (search 2, read_page 7, wikidata 55) | | | | | | | | | |
| Qwen3.5-0.8B (force) | 18/36 (50%) | plain | 3/18 (17%) | 0/18 (0%) | 18/36 (50%) | 3/18 (17%) | 3/18 (17%) | - | - | 9/36 (25%) |
| Qwen3.5-0.8B (force) | 18/36 (50%) | strict | 2/18 (11%) | 2/18 (11%) | 18/36 (50%) | 2/18 (11%) | 2/18 (11%) | - | - | 13/36 (36%) |
| | tool calls per draft: 1.0 (search 36, read_page 0, wikidata 0) | | | | | | | | | |
| Qwen3.5-0.8B (free) | 14/36 (39%) | plain | 8/22 (36%) | 4/14 (29%) | 15/36 (42%) | 1/22 (5%) | 0/14 (0%) | 6/36 (17%) | 4/36 (11%) | 7/72 (10%) |
| Qwen3.5-0.8B (free) | 14/36 (39%) | strict | 10/22 (45%) | 0/14 (0%) | 14/36 (39%) | 4/22 (18%) | 4/14 (29%) | 21/36 (58%) | 14/36 (39%) | 13/72 (18%) |
| | tool calls per draft: 0.0 (search 0, read_page 0, wikidata 0) | | | | | | | | | |
| Qwen3.5-0.8B (lookup) | 22/36 (61%) | plain | 8/14 (57%) | 5/22 (23%) | 23/36 (64%) | 1/14 (7%) | 0/22 (0%) | - | - | 1/36 (3%) |
| Qwen3.5-0.8B (lookup) | 22/36 (61%) | strict | 7/14 (50%) | 4/22 (18%) | 20/36 (56%) | 3/14 (21%) | 5/22 (23%) | - | - | 9/36 (25%) |
| | tool calls per draft: 0.5 (search 13, read_page 0, wikidata 5) | | | | | | | | | |
| Qwen3-0.6B (force) | 24/36 (67%) | plain | 0/12 (0%) | 1/24 (4%) | 24/36 (67%) | 0/12 (0%) | 0/24 (0%) | - | - | 0/36 (0%) |
| Qwen3-0.6B (force) | 24/36 (67%) | strict | 12/12 (100%) | 21/24 (88%) | 20/36 (56%) | 2/12 (17%) | 6/24 (25%) | - | - | 0/36 (0%) |
| | tool calls per draft: 1.0 (search 36, read_page 0, wikidata 0) | | | | | | | | | |
| Qwen3-0.6B (free) | 10/36 (28%) | plain | 2/26 (8%) | 0/10 (0%) | 10/36 (28%) | 0/26 (0%) | 0/10 (0%) | 1/36 (3%) | 0/36 (0%) | 0/72 (0%) |
| Qwen3-0.6B (free) | 10/36 (28%) | strict | 26/26 (100%) | 10/10 (100%) | 8/36 (22%) | 1/26 (4%) | 3/10 (30%) | 36/36 (100%) | 12/36 (33%) | 0/72 (0%) |
| | tool calls per draft: 0.0 (search 0, read_page 0, wikidata 0) | | | | | | | | | |
| Qwen3-0.6B (lookup) | 13/36 (36%) | plain | 0/23 (0%) | 0/13 (0%) | 13/36 (36%) | 0/23 (0%) | 0/13 (0%) | - | - | 0/36 (0%) |
| Qwen3-0.6B (lookup) | 13/36 (36%) | strict | 23/23 (100%) | 12/13 (92%) | 10/36 (28%) | 0/23 (0%) | 3/13 (23%) | - | - | 0/36 (0%) |
| | tool calls per draft: 0.1 (search 0, read_page 0, wikidata 3) | | | | | | | | | |

## Drafts per question (✓ right / ✗ wrong, one mark per sample)

| question | coder/force | coder/free | coder/lookup | qwen3/force | qwen3/free | qwen3/lookup | qwen35/force | qwen35/free | qwen35/lookup |
|---|---|---|---|---|---|---|---|---|---|
| emma | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| uk_pm | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| wc2026 | ✗✗✗ | ✗✗✗ | ✗✓✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| pluto | ✗✗✓ | ✗✓✗ | ✓✗✓ | ✓✓✓ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| australia | ✓✗✓ | ✓✓✗ | ✓✓✓ | ✓✓✓ | ✓✓✗ | ✓✓✓ | ✓✓✓ | ✓✗✓ | ✓✓✓ |
| oppenheimer | ✗✓✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| kilimanjaro | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✗✗ | ✓✓✓ | ✗✗✗ | ✓✗✗ | ✓✓✓ |
| moons | ✓✗✓ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✓ | ✓✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ |
| frankenstein | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✗✗✗ | ✗✓✗ |
| platypus | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| berlin | ✗✓✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| un_sg | ✗✗✗ | ✗✗✗ | ✗✓✗ | ✓✓✓ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✗✓ | ✓✓✓ |
