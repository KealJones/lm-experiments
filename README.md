# lm-experiments

Keal's small-language-model experiments: the models behind [Squiggle](https://github.com/KealJones/squiggle)
(a browser-only agent that runs on your own device), a cut-down Gemma 4 for phones, studies of how a small model
learns to find things out, and the earlier toki pona transfer work.

Moved here on 2026-10-29 from [tp-parse](https://github.com/KealJones/tp-parse), which is now just the toki pona
parser; the history of every moved file came along.

## Experiments

- [`answers`](experiments/answers/)
- [`askfirst`](experiments/askfirst/) — Ask first: find out what someone needs before answering
- [`basic-english`](experiments/basic-english/) — Basic English → toki pona hub map
- [`findout`](experiments/findout/) — Finding out: teach a small borrowed model the loop, not the facts
- [`findout2`](experiments/findout2/) — Findout pilot (v2)
- [`finetune`](experiments/finetune/) — Fine-tune test
- [`gemma-traces`](experiments/gemma-traces/)
- [`goals`](experiments/goals/) — Goals + lookup
- [`harness`](experiments/harness/) — Harness, first cut
- [`kaggle-smoke`](experiments/kaggle-smoke/)
- [`real`](experiments/real/) — Simple language first, with real data
- [`registers-v2`](experiments/registers-v2/) — Registers v2
- [`registers`](experiments/registers/) — Registers: a state table inside a small model
- [`skins`](experiments/skins/) — Skins: the lesson without the nouns
- [`squiggle-ft`](experiments/squiggle-ft/) — squiggle-ft: a small phone model for Squiggle's harness
- [`tiny-gemma4`](experiments/tiny-gemma4/) — Tiny Gemma 4
- [`tiny`](experiments/tiny/) — Tiny toki pona transfer experiments
- [`tokzoo`](experiments/tokzoo/)
- [`traces`](experiments/traces/) — Human finding-out traces
- [`weird`](experiments/weird/) — Weird maths in a transformer

Highlights: [`squiggle-ft`](experiments/squiggle-ft/) trained Squiggle Small (LFM2.5 350M on Squiggle's harness format,
[kealjones/squiggle-small](https://huggingface.co/kealjones/squiggle-small)); [`tiny-gemma4`](experiments/tiny-gemma4/)
prunes Gemma 4 E2B to a 0.6B core and heals it by distillation
([kealjones/tiny-gemma4-test](https://huggingface.co/kealjones/tiny-gemma4-test)).

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
