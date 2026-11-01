# Loop concept vs loop syntax

**Question (Keal, 2026-10-31):** is knowing *what a for loop does* different from knowing *how to spell one*? If a small
model already gets the concept (loop over this, step by that, body does X), then looking up a syntax snippet should be
enough to write loops in a language it's never really seen. Free first test, no training.

## Setup

- Models: Qwen3 0.6B and Qwen3 1.7B, untouched, thinking off.
- 25 small loop tasks (sum 1..100, countdown, FizzBuzz, primes, running totals, nested pairs, index + value, ...).
  Expected output is computed in Python ([`run.py`](run.py)).
- Three languages:
  - **Python**: the model knows it, so this shows whether it has the concept at all.
  - **Zig 0.17**: real, but newer than the models and fussy (`x % 2` on a signed int is a compile error; you need `@mod`).
  - **Plink**: a made-up language ([`plink.py`](plink.py)), so its syntax can't have been memorised.
    `count i from 1 to 10 by 2 ... end`, `for each x in xs ... end`, `show x`.
- Two arms per language: **cold** (just the task) and **snippet** (the task plus a generic syntax snippet for that
  language, the kind you'd look up; it shows loops, if/else, printing, nothing about the task).
- Every answer is run and its output compared exactly. Failures split into **syntax** (won't compile/parse) and
  **wrong** (ran, wrong output / crash / timeout). 1 greedy + 4 sampled answers per task per cell.
- The key number: of the tasks a model solves in plain Python, how many does it also solve in Zig/Plink with the snippet?

`python run.py check` runs reference programs through the graders (including a Python program fed to the Plink
grader, which must fail as syntax). Run on Kaggle (free T4 x2) via [`loop_concept.ipynb`](loop_concept.ipynb),
built by [`make_notebook.py`](make_notebook.py). No training data involved: this is evaluation only.

## Results (Kaggle, 2x T4, 0.6 h, free)

Raw strict scores: [`kaggle-out/RESULTS.md`](kaggle-out/RESULTS.md). The strict grader was too harsh on Python
(my "print each value on its own line" made models print the input list; "Steps taken: 111" failed), so
[`regrade.py`](regrade.py) re-runs every answer and accepts it if the right answer is the last line(s), labels allowed.
Lenient numbers:

| model | language | cold: pass / syntax fail | snippet: pass / syntax fail | tasks solved with snippet, of those solved in Python | snippet answers that paste the snippet's example |
|---|---|---|---|---|---|
| Qwen3 0.6B | Python | 66% / 0% | 44% / 1% | 18 / 22 | 22% |
| Qwen3 0.6B | Zig 0.17 | 0% / 100% | 0% / 74% | 0 / 22 | 36% |
| Qwen3 0.6B | Plink | 0% / 100% | 1% / 63% | 1 / 22 | 66% |
| Qwen3 1.7B | Python | 80% / 0% | 71% / 0% | 20 / 21 | 0% |
| Qwen3 1.7B | Zig 0.17 | 0% / 100% | 11% / 65% | 3 / 21 | 3% |
| Qwen3 1.7B | Plink | 0% / 100% | 18% / 46% | 5 / 21 | 26% |

**What it says:**
- Both models have the loop concept: they solve 21-22 of 25 tasks in Python.
- A looked-up snippet does **not** let them carry that concept into a new spelling. With the snippet, Qwen3 0.6B
  solves 0 of those tasks in Zig and 1 in Plink; Qwen3 1.7B solves 3 in Zig and 5 in Plink.
- The snippet roughly halves syntax failures, but they mostly turn into *wrong output*, not passes. The main reason:
  the model treats the snippet as the answer to imitate, not as a template to fill. 0.6B pastes the snippet's own
  example (`list(3, 1, 4)`, `"even"`) into 66% of its Plink answers. It even hurts plain Python for 0.6B (66% -> 44%).
- 1.7B's Zig errors show the same gap: the snippet says signed ints need `@mod`, and it still writes `i % 2`
  (31 compile errors). It reads the example's shape, not its rules.
- Bigger helps a little (0.6B -> 1.7B), but at this size "know the loop, look up the spelling" does not come for free.
  The next step is the trained version: fine-tune on "here is a template, fill these slots" pairs mined from real code,
  then rerun this exact test.

## Round 2: from scratch, with tools (Qwen3 0.6B only)

Keal: skip the snippet, just ask plain Qwen to do it and let it use tools. [`agent.py`](agent.py): plain Qwen3 0.6B
(thinking off) gets only the task, plus tools to `list_files`, `grep` and `read` the language's docs and `run` code,
for up to 15 turns; 3 sampled attempts per task. Docs: the real Zig 0.17 language reference as plain text
([`docs/zig/langref.txt`](docs/zig/langref.txt), built by [`build_zig_docs.py`](build_zig_docs.py) from
codeberg.org/ziglang/zig tag 0.17.0, MIT) and a written Plink reference ([`docs/plink/reference.txt`](docs/plink/reference.txt)).
Graded leniently. Notebook: [`agent_from_scratch.ipynb`](agent_from_scratch.ipynb).

A 2-task CPU pilot showed the shape already: both times it wrote JavaScript/Python, ran it once, got a syntax error,
and gave up without ever searching the docs.

### Round 2 results (Kaggle, 0.7 h, free): [`kaggle-out-agent/AGENT_RESULTS.md`](kaggle-out-agent/AGENT_RESULTS.md)

| | tasks solved | attempts that ever searched/read the docs | avg turns | avg runs |
|---|---|---|---|---|
| Zig 0.17 | 0 / 25 | 0 / 75 | 3.6 | 2.7 |
| Plink | 0 / 25 | 0 / 75 | 7.3 | 6.4 |

- **It never looked anything up.** 150 attempts, zero calls to grep, read or list_files. It only ever used `run`.
- On Zig it mostly didn't even try: 50 of 75 attempts answered in one turn with made-up Zig
  (`const even_numbers = 0..20 step 2;`) and never ran it.
- On Plink it wrote Python or JavaScript, ran it, got `syntax error: line 1`, said "Let me fix the code", and
  resubmitted **the identical code**, up to 15 times. 29 of 75 attempts hit the turn limit doing that.
- So plain Qwen3 0.6B has the loop concept (it solves the same tasks in Python) and can call tools, but it has no
  habit of "I don't know this, go look it up" and can't use an error message to change course. Those are behaviours
  to train, not knowledge it lacks. That lines up with Squiggle's findout experiments (teach the loop, not the facts).


## Round 3: same test, Gemma (Gemma 4 E2B and Keal's tiny Gemma 4)

[`gemma_agent.py`](gemma_agent.py): identical task, system prompt, tools, docs, limits and grading as round 2, but the
models run on llama.cpp (llama-server) in Gemma 4's native tool format: Gemma 4 E2B-it (unsloth Q8_0 GGUF) and
Keal's tiny Gemma 4 from [`tiny-gemma4`](../tiny-gemma4/) (heal 3, 0.6B body, the `tiny-gemma4-heal3-v2-Q4_0.gguf`
phone build; the full checkpoint is in a private dataset Kaggle can't reach). Sampling: Gemma's recommended
temperature 1.0, top-p 0.95, top-k 64. Notebook: [`agent_gemma.ipynb`](agent_gemma.ipynb).

Local CPU pilot (tiny Gemma, 4 attempts): same shape as Qwen. It never called a tool and answered in Python every
time (once with an empty reply).

First Kaggle try (2026-11-01) failed before any model ran: CMake on Kaggle couldn't find the CUDA driver library; the notebook now points it at libcuda directly and builds in /tmp.

Results: pending (`kaggle-out-gemma/AGENT_RESULTS.md`).
