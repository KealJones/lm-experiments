# lm-experiments

My small-language-model experiments: the models behind [Squiggle](https://github.com/KealJones/squiggle)
(a browser-only agent that runs on your own device), a cut-down Gemma 4 for phones, studies of how a small model
learns to find things out, and the earlier toki pona transfer work.

The write-ups are co-written with Claude, which ran most of the jobs.

Moved here on 2026-10-29 from [tp-parse](https://github.com/KealJones/tp-parse), which is now just the toki pona
parser; the history of every moved file came along.

## Experiments

- [`answers`](experiments/answers/) — Answers: 18 of my real messages with pass rules written first; Qwen3 0.6B, 1.7B and 4B answer in their own words and are graded by hand
- [`askfirst`](experiments/askfirst/) — Ask first: find out what someone needs before answering
- [`basic-english`](experiments/basic-english/) — Basic English → toki pona hub map
- [`canvas-blend`](experiments/canvas-blend/) — Canvas blend: a one-million-weight language model run by 2D canvas blend modes, with weights as pictures and the activation as a colour gradient
- [`context-packets`](experiments/context-packets/) — Context packets: answer from a ~360-word packet instead of the whole conversation
- [`context`](experiments/context/) — Context: how Qwen3 0.6B copes with running out of room, resuming, context picking, step size, a normal agent and a memdoor-style team (none made it a working coding agent; word-overlap context picking and harness-checked "done" helped most)
- [`findout`](experiments/findout/) — Finding out: teach a small borrowed model the loop, not the facts
- [`findout2`](experiments/findout2/) — Findout pilot (v2)
- [`factcheck`](experiments/factcheck/) — Draft -> fact-check: small models answer with Wikipedia/Wikidata tools, then review (and fix) their own answer; Haiku baseline
- [`finetune`](experiments/finetune/) — Fine-tune test
- [`gemma-traces`](experiments/gemma-traces/) — Gemma traces: what Gemma 4 E4B and E2B think on 38 messy, real-style prompts, as input to Squiggle's training template
- [`gpu-loss`](experiments/gpu-loss/) — GPU loss and recovery: what happens when a phone browser takes the GPU away
- [`goals`](experiments/goals/) — Goals + lookup
- [`harness`](experiments/harness/) — Harness, first cut
- [`kaggle-smoke`](experiments/kaggle-smoke/) — Kaggle smoke test: a GPU notebook that checks the Kaggle bridge works end to end
- [`lfm3-mlc`](experiments/lfm3-mlc/) — LFM3 1.7B on MLC / WebLLM (WebGPU)
- [`loop-concept`](experiments/loop-concept/) — Loop concept vs loop syntax: does a looked-up snippet let a small model write loops in a language it never saw?
- [`memcap`](experiments/memcap/) — How much memory does a phone's browser tab get?
- [`notes-cleanup`](experiments/notes-cleanup/) — Notes cleanup: can a pass over finished notes drop the stale lines without losing facts?
- [`notes-search`](experiments/notes-search/) — Notes search: can LFM3's own notes plus a dumb search be Squiggle's fresh context?
- [`random-weights`](experiments/random-weights/) — Random weights: tiny untrained GPT-2, Qwen3 and Gemma 4 with four ways to fill their weights at random
- [`real`](experiments/real/) — Simple language first, with real data
- [`register-resume`](experiments/register-resume/) — Register resume: a save game for a borrowed model
- [`registers-v2`](experiments/registers-v2/) — Registers v2
- [`registers`](experiments/registers/) — Registers: a state table inside a small model
- [`skins`](experiments/skins/) — Skins: the lesson without the nouns
- [`starting-weights`](experiments/starting-weights/) — Starting weights: a tiny network learning a spiral in the browser, started from zeros, equal, tiny, scaled and huge random weights
- [`squiggle-ft`](experiments/squiggle-ft/) — squiggle-ft: a small phone model for Squiggle's harness
- [`tiny-gemma4`](experiments/tiny-gemma4/) — Tiny Gemma 4
- [`tiny`](experiments/tiny/) — Tiny toki pona transfer experiments
- [`tokzoo`](experiments/tokzoo/) — Tokenizer zoo: a plan (not built yet) to compare 20 ways of cutting text into tokens on the same small GPT setup as `weird`
- [`traces`](experiments/traces/) — Human finding-out traces
- [`weird`](experiments/weird/) — Weird maths in a transformer
- [`whiteboard`](experiments/whiteboard/) — Whiteboard: can LFM3 1.7B keep its own notes well enough to drop the chat history?

Highlights: [`context-packets`](experiments/context-packets/), where a ~360-word packet did as well as the full
5,400-word history with Claude models answering; [`squiggle-ft`](experiments/squiggle-ft/) trained Squiggle Small
(LFM2.5 350M on Squiggle's harness format, [kealjones/squiggle-small](https://huggingface.co/kealjones/squiggle-small)),
a no-go against the bar set before training; [`tiny-gemma4`](experiments/tiny-gemma4/) prunes Gemma 4 E2B to a 0.6B
core and heals it by distillation, not usable yet
([kealjones/tiny-gemma4-test](https://huggingface.co/kealjones/tiny-gemma4-test)).

## The lab site

[`site/`](site/README.md) builds a page for every experiment (and hand-built demos, starting with
[`loop-concept`](site/demos/loop-concept/)) and publishes it to GitHub Pages on each push. New experiment folders
show up there on their own.

## Running things

Jobs run on rented GPUs from this repo, started by pushing a job file:

- **Hugging Face Jobs** ([`hf/`](hf/README.md)): a JSON file in `hf/queue/` starts a job; results come back into the
  job's `out` folder. Needs the `HF_TOKEN` secret in a GitHub environment named `HUGGINGFACE`. Raw outputs and
  checkpoints go to the private dataset `kealjones/tp-parse-runs` (the name predates the move).
- **Kaggle** ([`kaggle/`](kaggle/README.md)): free GPU notebooks. Needs `KAGGLE_API_TOKEN` in an environment named
  `KAGGLE` (`KAGGLE_USERNAME` defaults to `kealinit`).

## Rules for training data

Claude (the assistant that helps run these) doesn't write training examples: model outputs used for training
come from open models (Gemma 4, Apache-2.0) or people. Claude does design, checkers, evaluation and reviews.

## License

MIT (see [LICENSE](LICENSE)); datasets and models keep their own licenses, noted in each experiment.
