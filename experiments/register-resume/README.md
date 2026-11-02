# Register resume: a save game for a borrowed model

**Status:** plan only. Nothing has been run or spent. Launching any paid step needs Keal's budget first.

**Question:** if a stock small model gets a few trained memory slots (the `registers-v2` design) plus a LoRA, can it
pick up a half-finished plan from a fresh, nearly empty prompt using only the slots? The goal is to get close to
re-reading the whole transcript, while spending a fraction of the prompt tokens.

This is the cheap, testable core of Tern's one surviving new idea: the slots form a contract on the model's state,
and that state can be saved and restored like a checkpoint.

## Why this and not the untrained version

On 2026-11-02 we tried the zero-training version on stock Qwen3.5-0.8B. We read a note ("The secret word is
pineapple"), kept only the delta-rule recurrent state, dropped the text and the attention KV, and asked for the word
from a fresh prompt.

| condition | recalled |
| --- | --- |
| full text in the prompt | 10/10 |
| restored delta-rule state only | 0/10 |
| nothing | 0/10 |

A stock model keeps exact recall in attention, not in its recurrent state, which matches the Tern brief (finding 7).
So hand-saving a stock model's state does not work as a save game.

`registers-v2` already showed that *trained* slots work. On a 3.6M-parameter GPT planning in the skins world, slots
updated at every word took messy long plans from 0% to 72% (taught) and 64% (self-taught, no simulator labels), and cut
bookkeeping failures from 289 to 61–80. This experiment asks whether that result carries over to a real pretrained
model.

## Task: Blocksworld

Blocks sit on a table or on each other. You can pick up a block only if nothing is on top of it, and you hold one block
at a time. A problem gives a start and a goal, and the plan is the sequence of
`pickup / putdown / stack / unstack` moves. A simulator checks every move exactly, so there's no hand grading.
Difficulty grows with the block count.

- **Training data:** our own generator (random start and goal states). Plans come from a deterministic planner in code:
  BFS for up to 6 blocks, and the standard "unstack everything, then build" plan for more (valid but not optimal).
  No model writes training text, so this fits the repo's data rule.
- **Test data:** PlanBench Blocksworld instances ([karthikv792/LLMs-Planning](https://github.com/karthikv792/LLMs-Planning)),
  bucketed as easy (3–4 blocks), medium (5–6) and hard (7+). These are never used for training.
- **Checker:** our own simulator (already written in the starter script): illegal moves fail the plan, and the goal
  must hold at the end.

## Stage 0: base bake-off (inference only, no training)

Pick the base on evidence rather than habit. Each candidate plans from scratch on about 150 PlanBench problems (50 per
bucket) with its own chat template and a fixed few-shot prompt. We also rerun `findout2`'s v3 tool world, so the result
lines up with earlier numbers.

| candidate | size | notes |
| --- | --- | --- |
| Qwen3.5-0.8B | 0.87B (with vision) | findout2: 22% right, 2% strict; loops |
| Qwen3-0.6B | 0.6B | best raw-text bits per byte in `tiny-gemma4` stage 1 |
| LFM2-700M | 0.7B | Liquid; beat Qwen3-0.6B on MobileLLM-Flash's nine-task average (48.5 vs 44.3) |
| MobileLLM-R1.5-950M | 0.95B | Meta, reasoning-tuned (maths and code); non-commercial-style license |
| Granite 4.0 1B | 1B | IBM, Apache-2.0 |
| LFM2.5-350M | 0.35B | took fine-tuning best in `squiggle-ft`; floor check |
| Qwen3.5-2B (ceiling) | 2B | findout2: 46% right, 37% strict; not a phone candidate yet |

Keep the best two at or under 1B for Stage 1, plus the 2B as the ceiling.

**Cost estimate (mine):** about 1,000 short generations per model on an L4 ($0.80/hr) is roughly 2–3 hours total,
**about $2**.

## Stage 1: registers on the borrowed model

**Adapter** (ported from `rv2.py`):

- **Slots:** 8 slots, each the model's hidden width. That's 16 KB of state at width 1,024 in bf16, and it's the whole
  save game.
- **Write:** at every token, a minGRU-style gate updates the slots from the hidden state at layer L/2:
  `s ← g·s + (1 − g)·c`.
- **Read:** the layers above L/2 cross-attend over the slots. The result is added to the residual through a
  zero-initialised gate, so the untrained adapter is a no-op.
- **LoRA:** rank 16 on attention and MLP. The base weights stay frozen.

**Training episodes:**

1. Segment 1 is the problem statement, the plan, and the moves executed up to a random cut point. Slots update
   throughout.
2. Segment 2 is a fresh prompt containing only `Continue.`, with the slots carried over from segment 1. The loss is on
   the remaining moves.
3. Backprop runs through the boundary, so the gradient teaches segment 1 what to write.

There are two variants, as in `registers-v2`:

- **taught:** 3 slots are supervised for a few early steps to hold the true state (what's on each block, what's in the
  hand, the next goal block). That supervision fades out by 80% of training.
- **self:** no state labels.

## Conditions at test

The same model and the same problems are used throughout; only what the resume prompt carries changes.

| | resume prompt has | measures |
| --- | --- | --- |
| A | full transcript (problem, plan, moves so far) | upper bound |
| B | problem plus the plan re-pasted as text | the usual "text summary" approach |
| C | `Continue.` plus restored slots | **the bet** |
| D | `Continue.` only, base model | lower bound (about 0%) |
| E | `Continue.` only, LoRA trained the same way **without** slots | rules out the LoRA alone doing the work |

## Metrics

- Goal reached (simulator), per difficulty bucket.
- Illegal moves (bookkeeping failures), as in `registers-v2`.
- Prompt tokens at resume for each condition.
- **Taught variant only:** after training, can a linear probe still read the true state from the slots?

## Go / no-go

- **Pilot gate:** after 500 steps on one seed, C must beat E by at least 15 points on easy. If not, stop and report.
- **Go:** C within 10 points of A on easy and medium, C at least 30 points above E, and C's resume prompt under 10% of
  B's tokens.
- **No-go:** C ≈ E, meaning the slots carry nothing. Write up why (router collapse, gate stuck shut) before trying
  anything bigger.

## Cost estimate (mine, not measured)

- **Stage 1 pilot:** about 5,000 episodes × ~600 tokens × 2 epochs is about 6M tokens. On an A100 ($2.50/hr) at the
  ~4K tokens/s the `tiny-gemma4` heal probe got at 1.5B, that's under an hour including eval, **about $2–4** per base.
- **Full run** (3 seeds × 2 variants × 2 bases): about $15–25. Only if the pilot passes.
- **Qwen3.5-2B ceiling run:** about $5–8, only after a go on a ≤1B base.

## Known risks

- **Positions:** the fresh prompt restarts at position 0 while the slots came from a longer context. The slots have no
  positions, which is part of the point, but watch for it.
- **The gate stays shut:** the zero-init gate never opens and the model learns to ignore the slots (the brief's top
  risk, "router collapses to no-op"). The taught variant and the E control are the hedges.
- **Narrow training distribution:** slots trained only on Blocksworld may not say anything about other tasks. That's
  fine for a first yes/no.
