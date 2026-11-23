# Gradient Decent: a language model run by colour blending on a 2D canvas

Started as "a CSS-based LLM engine" and a hunt for native browser features that can do the maths of a small model
without WebGPU. Two people had already done an LLM in CSS (qwennie, and Shubham Patil's GPT-2 in CSS with fonts), so
this went looking for an engine nobody had used.

**Question:** can a 2D canvas, using only blend modes and image scaling, run a real language model fast enough to watch?

It now has its own repo, [KealJones/gradient-decent](https://github.com/KealJones/gradient-decent). A copy of the demo is [`site/demos/gradient-decent/`](../../site/demos/gradient-decent/index.html). The model is
[hidude562/tiny-tiny-stories](https://huggingface.co/hidude562/tiny-tiny-stories) (MIT): 998,784 weights, 5 layers,
width 128, a 192-token vocabulary, ternary {-1, 0, +1} weights in every attention and feed-forward matrix.

How one matrix multiply works:

- **The weights are a picture.** One pixel per weight: red where it is +1, green where it is -1. The 35 ternary
  matrices are 8-bit PNGs; the output head (full-precision embeddings) is one float16 picture.
- **The input is a strip.** A 2-pixel-tall strip holds the input vector, positive parts in one channel and negative
  parts in the other, stretched over the weight picture with the `multiply` blend mode.
- **The sum is a squash.** The product image is halved in width again and again with smoothing on, which averages
  each row down to one pixel. One `getImageData` reads every output at once.
- **The activation is a gradient.** SiLU is a canvas linear gradient with 1,025 colour stops, rendered once and
  read back as a lookup table.

Still plain JavaScript: the norms, rotary positions, the attention softmax over cached keys and values, and sampling.
All 36 matrix multiplies per token go through the canvas. `export.py` turns the checkpoint into the pictures and a
reference run; `window.selfTest()` on the demo page compares the canvas against that reference. Spend: $0.

## Results (headless Chrome 153, CPU only, no GPU; free)

**The canvas picks the same token as a plain numpy reference on all 60 tokens of a greedy run, at about 20 tokens a second with the live tiles on and about 30 with them off.**

| check | result |
|---|---|
| greedy tokens matching the reference | 60 of 60 |
| largest logit error | 0.022 on values up to 14.5 |
| gradient lookup error (SiLU) | 0.0036 |
| time per token, tiles off | 33 ms |
| whole bundle (36 pictures + tokenizer) | 743 KB |

- It needs a float16 canvas. In an 8-bit canvas the same multiply is about 5% off; in float16 about 0.2%.
- Squashing the image to one pixel in a single `drawImage` gives garbage. Halving the width step by step is what
  makes the sum right.
- A plain JavaScript loop is still about 25 times faster for the same multiply on this machine (0.07 ms against
  1.9 ms for 128×128). The canvas is here because it is funny and you can watch it, not because it is quick.
- Not tried yet: Safari, a phone, or a machine with a real GPU.

## What else was tried on the way

All in the same headless Chrome, all free.

| idea | what happened |
|---|---|
| one flat CSS `calc()` per output, 64×64 layer | 3.55 ms; 1.6 ms with ternary weights (adds only) |
| the same layer as CSS layout (flex rows read back with `100cqw`) | 11.7 to 18 ms: layout loses to `calc()` for sums |
| pure-CSS clock (the x86CSS animation latch) | exact at 10 ticks a second, breaks faster than that |
| the same latch ticked by a few lines of JS | about 6,700 ticks a second |
| softmax as `flex-grow: exp(x)` over 192 items | widths match the true probabilities to about 1 part in a million |
| embedding lookup as a keyframe table | works, 60 ms; a plain `if()` chain is 14 ms |
| `hypot()` for the norm | fine up to 64 arguments, fails at 128 |
| matrix multiply as a Web Audio convolver | exact to float precision, but 3.5 s for 1024×1024 |

A pure-CSS version (ternary `calc()`, flexbox softmax, the latch clock) could run the same weights; it is not built.
