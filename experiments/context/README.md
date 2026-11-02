# Context: how Qwen3 0.6B copes with running out of room, resuming, and agent setups

Oct 31 – Nov 1, 2026. Question: when a small model runs out of context mid-task, what harness lets it pick up and
finish? Then: does curating context, changing step size, a normal long-context agent, or a multi-agent team help?

**Short answer: no setup made stock Qwen3 0.6B a working coding agent.** The bottleneck is per-step competence and
honest "done", not context. Details and what *did* help below.

**Spend:** $0. Everything ran locally on CPU (llama-cpp-python 0.3.36, 2 threads).

Model: Qwen3 0.6B (Q8_0, llama.cpp). Sections 1–3: 4,096-token window, junk "Brightleaf" system prompt (~880 tokens) +
3 fake tools. Task: TypeScript browser tic-tac-toe with minimax AI, score counter, restart. The sandbox
(`sbx/run.mjs`) type-checks, runs in jsdom, clicks 5 cells. Score 0–5 = compiles, runs, board, clicks work, computer
moves (the hand-written `t/good.ts` scores 5/5).

**Baseline for the repair tasks (sections 2–4):** the untouched broken file (one function emptied) already scores
winner 4, minimax 3, bestMove 3, render 2, play 3 — **avg 3.0**. Anything below 3.0 means the model made the file worse
than doing nothing.

## 0. Pilots (`early/`)

First tries before the harness in `exp/`: a plain relay at 4K ("can you complete this games code" + the pasted code,
no history) until it says done, then the same with a JS sandbox tool and filler in the system prompt, then thinking on
with a harder task, then plan-first-then-chunks (`plan_chunks*.py`, each step only sees what its plan step needs).
None produced a working game; they led to the systematic comparison in section 1.

## 1. Resume strategies (19 runs, thinking off vs capped at 800 tokens) — `exp/strategies.py`, `exp/run.py`, `exp/runs/`

A relay ("can you complete this games code" + pasted code), B file + computed outline + tail, C skeleton then fill per
function, D fill-in-the-middle (Qwen2.5-Coder 0.5B Instruct — invalid, the instruct model just repeats skeleton lines),
E NOTES.md + tail, F context shift, G squeeze at 80%, H edits not rewrites, I tests as brief, J combined.

- Every run scored 0–1/5. No working game.
- The resume machinery almost never fired: the model quits, refuses ("I don't have access to a sandbox") or calls
  `finish` on broken code long before 4K. B/E ignored the file tool and wrote code in the reply.
- Skeletons must be enforced in code (it never leaves bodies empty) and fills broke more than they fixed.
- Thinking: 1 point total on vs 1 off across 9 pairs. On writes more code and gives up less, but takes 2–5× longer
  and is the main thing that fills the window.
- Conclusion: at 0.6B the bottleneck is single-turn competence and honest "done", not memory between turns.

## 2. Context curator (5 functions emptied, 3 tries each, thinking off) — `exp/curator.py`, `exp/curator_results.json`

Menu of 15 items (outline, full source, each other function, types, NOTES.md, file tail, plus junk: style guide,
pricing, weather docs, CSS, old chat, holidays).

| Method | Fully fixed (of 15) | Avg score |
|---|---|---|
| Word overlap, top 4 | 6 | 3.67 |
| Qwen3 0.6B picks from menu | 3 | 3.00 |
| Nothing extra | 2 | 2.47 |
| Everything that fits (~2.1K tokens) | 0 | 2.80 |
| Qwen3-Reranker 0.6B, top 4 | 0 | 2.60 |

- Only word overlap beat the do-nothing baseline (3.0).
- The 0.6B curator answered "12" (page.css) all 15 times — degenerate, not curating; its wins are noise.
- The reranker scored junk ~0 but nearly all code items 0.97–0.99, so its top 4 were summaries (outline, types,
  tail) — it never picked the full source; overlap almost always did. Seeing the actual code beat summaries.
- More context hurt: "everything" never fixed a function.
- `play()` was fixed 3/3 only with overlap picks; `winner()` and `render()` never.
- Caveat: 5/5 means the game works, not that minimax is unbeatable.

## 3. Granularity: how big a piece per turn (same 5 functions) — `exp/granular.py`, `exp/gran_{off,on}.json`

Every method gets the same thin brief: objective (one line per function), signature, list of types/variables/function
signatures. No source code.
- **whole:** one turn writes the function.
- **lines:** each turn writes the next 1–3 lines (sees locals so far, open blocks, last 3 lines); DONE rejected while
  blocks are open (max 2 times).
- **blocks:** top-down stepwise refinement: each turn fills one `/*HOLE*/` with ≤5 lines, leaving new holes for nested
  blocks; longer replies are cut to 5 lines plus a "continue" hole; repeated lines are dropped.

| Method | Thinking | Fixed | Avg score | Avg turns | Avg secs |
|---|---|---|---|---|---|
| whole | off | 0/15 | 2.40 | 1 | 27 |
| lines | off | 0/15 | 1.93 | 4.7 | 13 |
| blocks | off | 1/15 | 1.20 | 4.0 | 41 |
| whole | on (300-token cap) | 1/10 | 2.40 | 1 | 31 |
| lines | on (300-token cap) | 1/10 | **3.00** | 2.6 | 45 |
| blocks | on (300-token cap) | 0/10 | 1.50 | 3.7 | 83 |

- Thinking off: smaller pieces made it worse. In line mode it rewrote the whole function every turn (the harness kept
  3 lines) and tried DONE with blocks open 17 times.
- Thinking on: line mode was the best thin-brief method (avg 3.0, fixed `minimax` once) — but that only equals the
  do-nothing baseline. Small samples (10 per row).
- Block mode was worst in both: it sometimes left HOLEs but wrote 6–27 lines when allowed 5, and its holes were vague.

## 4. Normal coding agent — `exp/agent.py`, `exp/agent_{off,on}.json`

32K window, plain coding-assistant system prompt (no junk), real tools (`ls`, `grep`, `read_file`, `write_file`,
`edit_file`, `run_game`, `finish`), full conversation history, no resets. Tasks: build the game from scratch, and
repair each of the 5 emptied functions. 2 tries each, thinking off and on (uncapped). Stops on finish, a reply without
a tool call, a full window, 40 steps or 20 minutes.

| Thinking | Fixed | Avg score (fix tasks) | Build | How runs ended |
|---|---|---|---|---|
| off | 0/12 | 2.1 (baseline 3.0) | 0, 0 | 10 replied without a tool call, 1 finish, 1 hit 40 steps |
| on | 0/12 | 2.1 (baseline 3.0) | 0, 0 | 10 called finish, 2 replied without a tool call |

- The window was never the problem: max context used was ~9.8K of 32K (and only in a loop).
- It almost never looked: `grep` was used 0 times and `read_file` once (1 of 24 runs). It went straight to `edit_file`.
- Typical repair: `edit_file` replacing `// TODO` with nonsense like `function winner() { return 'Player 1'; }` (a
  function nested inside the function), then stop without running the game.
- Thinking on mostly changed *how* it lied: it called `finish` with "the function is fixed" — in two `play` runs
  without making any edit at all.
- Build, thinking off, try 2: wrote a game importing `./board`, then called `run_game` 38 times in a row saying "I see
  the issue again, let me fix it" without ever changing the file.
- 5 tool calls were malformed JSON (unescaped quotes inside code).
- On average its repairs made the file **worse than leaving it broken**.

## 5. memdoor team-solve port vs one call — `exp/team/`

Ported memdoor's [`examples/workflows/team-solve`](https://github.com/guregodevo/memdoor/tree/main/examples/workflows/team-solve)
(the "GVS5H method"): plan → ideator A → ideator B → solve → test (script) → review → repair → verify (script). Their
exact step prompts (read from a clone of memdoor at `ext/memdoor`); every agent step starts with a fresh context (16K
window, thinking on, their temperatures), the only channel between steps is files on disk (plan.md, notes.md), and a
script (`check-samples.sh`, copied from memdoor) decides pass/fail. Tools: ls, read_file, write_file, edit_file,
apply_patch (insert before a marker), bash. Each step ends on a reply with no tool call, 20 tool calls, or 15 minutes.
Baseline: one plain call with task.md, "reply with the complete solution.py in one code block". Python
competitive-programming problems (`exp/team/problems/`), 5 visible samples + 20 hidden tests checked against brute
force; reference solutions in `exp/team/ref/` pass everything. Qwen3 0.6B only, 1 try each (1.7B and 4B dropped).
Results: `exp/team/r_0.6b.json`.

| Problem | Single call | Team (8 steps) |
|---|---|---|
| Easy: second-largest distinct value | **solved**, 20/20 hidden, 1.7 min | failed, no solution.py, 67 min |
| Medium: count subarrays with sum K (prefix sum + hashmap) | failed, no code (16K tokens of thinking), 51 min | failed, no solution.py, 44 min |
| Hard: balanced a/b/c substrings (memdoor's sample) | failed 4/5 samples; "12/20 hidden" is fake (always prints 0, and 12 hidden answers are 0) | not finished (job hit the 2-hour limit) |

- The team never produced a solution file. Both times, solve and repair thought until the 8,192-token reply cap and
  never made a write call.
- Planning was fine: on easy, plan.md restated the problem correctly and named the right algorithm. Ideator A wrote
  nonsense pseudocode (sum 1..n).
- Review ran the tests, saw them fail, and wrote "This implementation correctly handles all edge cases" — the same
  fake "done" as section 4.
- Single call on medium: spent the entire 16K window re-checking a hand count ("Ah! Oh no! I think I made a
  mistake…") and never emitted code.
- Single call on hard wrote the right *shape* (prefix counts + dict) but keyed on raw counts instead of differences,
  so it can never match.
- **Test-set flaw:** 12 of 20 hidden hard tests have answer 0, so "always print 0" scores 12/20. Fix before reusing:
  score hidden tests only where the answer isn't trivial, or add more nonzero cases.
- At 0.6B, thinking runs away whenever a step needs real reasoning. More agents add more places for that to happen
  and no extra competence. Splitting into roles helps only if each role can finish its own step.

## Takeaways for Squiggle

- Stock Qwen3 0.6B is not a viable coding agent in any setup tried: short or long window, with or without history,
  thinking on or off, single agent or memdoor-style team. The bottleneck is per-step competence and honest
  self-checking, not context.
- A dedicated scorer beats the small model at choosing context, but the menu matters more: offer real code in
  function-sized chunks, prefer code over summaries, cap total context. Word overlap won.
- Given tools, it doesn't investigate on its own — the harness should pre-load the relevant real code (overlap-picked)
  instead of hoping it greps.
- Verify "done" against sandbox results; never trust the model's claim. Detect no-op loops (same tool, same result,
  no file change).
- Cap thinking per step and force the output out (e.g. stop thinking at N tokens, then prefill the code block or tool
  call). Uncapped thinking is the most common way a 0.6B step fails.
- Open: repeat the best setup (overlap-picked real code + harness-verified done + capped thinking) with Qwen3 1.7B and
  Squiggle Small v1 to separate size from training; a fair FIM test needs base Qwen2.5-Coder 0.5B.

## Files and running

```
exp/core.py           shared harness: model loading, sandbox + scoring, outline, workspace helpers
exp/strategies.py     resume strategies A–J;  exp/run.py runs them;  exp/runs/<strategy>-<think>/ logs + results
exp/curator.py        section 2          exp/granular.py  section 3          exp/agent.py  section 4
exp/team/team.py      section 5 (usage: python3 team.py <0.6b|1.7b|4b> <out.json> <tries> <problems...>)
exp/*.json            raw results per section (prompts, model outputs, scores)
sbx/run.mjs           TypeScript 5 + jsdom sandbox (npm install in sbx/; TypeScript 7 has no JS compiler API)
sbx/outline.mjs       TypeScript-AST outline of functions/variables/types
t/good.ts             correct reference game (5/5)
early/                pilot scripts and logs (section 0)
```

Scripts expect GGUF models in `model/` (git-ignored): `qwen3-0.6b-q8.gguf`, `qwen3-1.7b-q8.gguf`,
`qwen3-4b-q4km.gguf`, `qwen3-reranker-0.6b-q8.gguf`, `qwen25-coder-0.5b-instruct-q8.gguf`; section 5 also needs
`git clone --depth 1 https://github.com/guregodevo/memdoor ext/memdoor`. Paths in the raw JSON were rewritten from the
original scratch folder to `experiments/context`. The early pilots still use their original relative paths.
On CPUs that crash with SIGILL, rebuild llama-cpp-python with `CMAKE_ARGS="-DGGML_NATIVE=ON"`.
