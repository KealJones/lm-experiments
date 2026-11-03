# Random weights

Keal: "i wanna make a really small model... but instead of training it lets just throw random numbers in the weights."

A 2-layer GPT-2 (width 128, 2 heads, 6.9M parameters, nearly all of them the GPT-2 embedding) that never sees a training step. Four ways to fill the weights, same seed each time:

- **default**: what transformers does before training, normal(0, 0.02) with LayerNorm at 1/0
- **normal 1.0** and **normal 10**: every parameter, LayerNorm included, from normal(0, std)
- **uniform -1..1**: every parameter from uniform(-1, 1)

Each one is scored on the first 10,240 tokens of WikiText-2 test and asked to continue three prompts (20 sampled tokens, 12 greedy).

Run: `uv run experiments/random-weights/random_weights.py` (CPU, under a minute after the download). Spend: $0.

## Results (local CPU, 2026-11-03)

Guessing every token with equal odds gives loss ln(50257) = **10.825**.

| init | WikiText-2 loss | distinct top-1 tokens over 10,240 positions |
|---|---|---|
| default (normal 0.02) | **10.834** | 4,250 |
| uniform -1..1 | 23.5 | 125 |
| normal 1.0 | 66.1 | 59 |
| normal 10 | 6,608 | 62 |

Sample outputs:

- default, greedy: `The cat sat on the the an an advances advances advances advances...`
- default, sampled: `The cat sat on the upset Woo Casropy rightfullyGall UNDER savvy Publishing...`
- normal 1.0, greedy: `The cat sat on the PIViewViewoeuv PIViewoeuvViewoeuv PIViewoeuv`
- uniform, greedy: `Once upon a time DeVos skirt recount,'",'"wan recount,'"wanwanwanwan`

- **No random weights beat a blind guess.** The best one, the standard init, lands 0.009 above uniform odds: the logits are so small that the model is close to "every token equally likely", which is why it's the least wrong.
- **Bigger random numbers make a confident idiot.** At std 1 or 10 the logits blow up and the model bets everything on a few tokens (59 to 62 different top picks across all 10,240 positions: `sonian`, `View`, `orthodox`, `PI`). It's wrong with huge confidence, so the loss goes far past the blind guess.
- **It barely reads the prompt.** The default init's sampled continuations are almost the same string for all three prompts. With near-flat logits, the random draws decide the output, not the input. Greedy loops on one token after a few steps.
- normal 1.0 and normal 10 share a seed, so they're the same direction scaled up; that's why they favour the same tokens.

Takeaway: random weights give you a tokenizer-flavoured noise machine. Everything a model "knows" is in training; the architecture alone gives nothing measurable here.
