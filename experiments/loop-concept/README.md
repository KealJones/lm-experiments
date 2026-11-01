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

## Results

Pending: `kaggle-out/RESULTS.md` when the run finishes.
