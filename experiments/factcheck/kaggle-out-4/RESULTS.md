# Draft -> fact-check: results

12 questions, 3 sampled drafts each, tools = Wikipedia search, Wikipedia page, Wikidata. Each draft is reviewed twice by the same model in a fresh chat: **plain** (Keal's wording) and **strict** (fact-checker, assume it's wrong).

**Own drafts** = the model reviews its own answers. **Planted** = it reviews a known-wrong answer per question (e.g. 'The capital of Australia is Sydney').

| model | draft right | review | caught wrong own drafts | false alarms on right drafts | final right | fixed (wrong->right) | broke (right->wrong) | planted caught | planted fixed | no verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder-1.5B-Instruct (read) | 11/36 (31%) | plain | 2/25 (8%) | 0/11 (0%) | 4/36 (11%) | 3/25 (12%) | 10/11 (91%) | 2/36 (6%) | 4/36 (11%) | 55/72 (76%) |
| Qwen2.5-Coder-1.5B-Instruct (read) | 11/36 (31%) | strict | 2/25 (8%) | 0/11 (0%) | 5/36 (14%) | 2/25 (8%) | 8/11 (73%) | 2/36 (6%) | 3/36 (8%) | 53/72 (74%) |
| | tool calls per draft: 3.4 (search 38, read_page 83, wikidata 0) | | | | | | | | | |
| Llama-3.2-1B-Instruct (force) | 4/36 (11%) | plain | 17/32 (53%) | 3/4 (75%) | 1/36 (3%) | 0/32 (0%) | 3/4 (75%) | - | - | 0/36 (0%) |
| Llama-3.2-1B-Instruct (force) | 4/36 (11%) | strict | 31/32 (97%) | 4/4 (100%) | 9/36 (25%) | 6/32 (19%) | 1/4 (25%) | - | - | 0/36 (0%) |
| | tool calls per draft: 4.9 (search 69, read_page 50, wikidata 56) | | | | | | | | | |
| Llama-3.2-1B-Instruct (free) | 2/36 (6%) | plain | 26/34 (76%) | 2/2 (100%) | 5/36 (14%) | 5/34 (15%) | 2/2 (100%) | 36/36 (100%) | 5/36 (14%) | 1/72 (1%) |
| Llama-3.2-1B-Instruct (free) | 2/36 (6%) | strict | 34/34 (100%) | 1/2 (50%) | 1/36 (3%) | 1/34 (3%) | 2/2 (100%) | 36/36 (100%) | 0/36 (0%) | 1/72 (1%) |
| | tool calls per draft: 3.8 (search 50, read_page 64, wikidata 23) | | | | | | | | | |
| Llama-3.2-1B-Instruct (lookup) | 3/36 (8%) | plain | 24/33 (73%) | 2/3 (67%) | 3/36 (8%) | 2/33 (6%) | 2/3 (67%) | - | - | 0/36 (0%) |
| Llama-3.2-1B-Instruct (lookup) | 3/36 (8%) | strict | 30/33 (91%) | 3/3 (100%) | 3/36 (8%) | 3/33 (9%) | 3/3 (100%) | - | - | 0/36 (0%) |
| | tool calls per draft: 3.9 (search 41, read_page 53, wikidata 46) | | | | | | | | | |
| Llama-3.2-1B-Instruct (read) | 5/36 (14%) | plain | 0/31 (0%) | 0/5 (0%) | 5/36 (14%) | 0/31 (0%) | 0/5 (0%) | 0/36 (0%) | 1/36 (3%) | 0/72 (0%) |
| Llama-3.2-1B-Instruct (read) | 5/36 (14%) | strict | 12/31 (39%) | 0/5 (0%) | 5/36 (14%) | 0/31 (0%) | 0/5 (0%) | 24/36 (67%) | 3/36 (8%) | 0/72 (0%) |
| | tool calls per draft: 6.3 (search 52, read_page 52, wikidata 122) | | | | | | | | | |
| Qwen3.5-0.8B (read) | 24/36 (67%) | plain | 2/12 (17%) | 0/24 (0%) | 23/36 (64%) | 1/12 (8%) | 2/24 (8%) | 8/36 (22%) | 14/36 (39%) | 20/72 (28%) |
| Qwen3.5-0.8B (read) | 24/36 (67%) | strict | 4/12 (33%) | 1/24 (4%) | 21/36 (58%) | 1/12 (8%) | 4/24 (17%) | 22/36 (61%) | 21/36 (58%) | 10/72 (14%) |
| | tool calls per draft: 2.0 (search 36, read_page 36, wikidata 0) | | | | | | | | | |
| Qwen3.5-0.8B (think) | 27/36 (75%) | plain | 0/9 (0%) | 0/27 (0%) | 22/36 (61%) | 0/9 (0%) | 5/27 (19%) | 11/36 (31%) | 15/36 (42%) | 22/72 (31%) |
| Qwen3.5-0.8B (think) | 27/36 (75%) | strict | 2/9 (22%) | 1/27 (4%) | 22/36 (61%) | 1/9 (11%) | 6/27 (22%) | 12/36 (33%) | 15/36 (42%) | 20/72 (28%) |
| | tool calls per draft: 1.7 (search 45, read_page 11, wikidata 6) | | | | | | | | | |
| Qwen3-0.6B (read) | 24/36 (67%) | plain | 1/12 (8%) | 1/24 (4%) | 24/36 (67%) | 0/12 (0%) | 0/24 (0%) | 1/36 (3%) | 5/36 (14%) | 0/72 (0%) |
| Qwen3-0.6B (read) | 24/36 (67%) | strict | 12/12 (100%) | 23/24 (96%) | 19/36 (53%) | 0/12 (0%) | 5/24 (21%) | 36/36 (100%) | 18/36 (50%) | 0/72 (0%) |
| | tool calls per draft: 2.0 (search 36, read_page 36, wikidata 0) | | | | | | | | | |
| Qwen3-0.6B (think) | 12/36 (33%) | plain | 3/24 (12%) | 0/12 (0%) | 12/36 (33%) | 0/24 (0%) | 0/12 (0%) | 8/36 (22%) | 5/36 (14%) | 0/72 (0%) |
| Qwen3-0.6B (think) | 12/36 (33%) | strict | 9/24 (38%) | 0/12 (0%) | 14/36 (39%) | 2/24 (8%) | 0/12 (0%) | 17/36 (47%) | 9/36 (25%) | 0/72 (0%) |
| | tool calls per draft: 0.5 (search 10, read_page 0, wikidata 8) | | | | | | | | | |

## Drafts per question (✓ right / ✗ wrong, one mark per sample)

| question | coder/read | llama/force | llama/free | llama/lookup | llama/read | qwen3/read | qwen3/think | qwen35/read | qwen35/think |
|---|---|---|---|---|---|---|---|---|---|
| emma | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ |
| uk_pm | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✓✗ |
| wc2026 | ✓✗✓ | ✗✗✓ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✗✗ |
| pluto | ✓✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✓ | ✗✗✗ | ✓✓✓ | ✗✗✗ | ✓✓✓ | ✓✓✓ |
| australia | ✗✗✗ | ✗✓✗ | ✗✓✗ | ✓✗✗ | ✗✗✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| oppenheimer | ✓✓✗ | ✗✗✗ | ✓✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✗✗✗ | ✓✓✓ | ✓✓✓ |
| kilimanjaro | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✓ | ✗✗✗ | ✓✓✓ |
| moons | ✓✓✓ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✗✗✗ | ✓✓✓ | ✓✓✓ |
| frankenstein | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| platypus | ✗✗✓ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✗✗✗ | ✓✓✓ | ✓✗✗ |
| berlin | ✓✗✓ | ✓✗✗ | ✗✗✗ | ✗✗✓ | ✗✗✗ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| un_sg | ✗✗✗ | ✗✓✗ | ✗✗✗ | ✗✗✗ | ✗✗✗ | ✓✓✓ | ✓✓✗ | ✓✓✓ | ✓✓✓ |
