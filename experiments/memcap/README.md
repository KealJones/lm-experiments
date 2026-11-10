# How much memory does a phone's browser tab get?

**Question (Keal, 2026-11-09):** on-device models in Squiggle keep killing the Safari tab on Keal's iPhone 16. Apple
doesn't publish how much memory a web page may use before iOS kills it. How much is it, is it one budget or separate
ones for JavaScript, WebAssembly and the GPU, and is it the phone or the browser?

## Setup

- **The page:** [memcap](https://kealjones.com/lm-experiments/demos/memcap/), a copy of Squiggle's `app/memcap.html`
  (squiggle commit `39ecb55`). It fills the tab with one kind of memory until the browser stops it, writing its
  progress to `localStorage` before every step, so when the tab is killed the reloaded page knows how far it got.
  Probes: plain JavaScript arrays, WebAssembly memory, WebGPU buffers, and JavaScript plus GPU filled in turns (to see
  whether they share a budget). Several rounds of each, because the limit moves with what else the phone is doing.
- **A cap:** the test stops itself at a cap (now 16 GB on phones, 2 GB on computers, changeable under Options) so a
  phone that never kills the tab doesn't run forever. A run that reaches the cap is a floor, not a limit.
- **Phones:** Keal's iPhone 16 in Safari (5 rounds) and Greg's Android 17 phone in Firefox 160 (2 rounds, plus one
  more WebAssembly run), 9 Nov 2026.

## Results (memcap, 9 Nov 2026, lowest and best of the rounds)

**iPhone Safari gives a tab about 1.9 GB, one budget shared by JavaScript, WebAssembly and the GPU; Firefox on Greg's Android phone went past every cap the test had.**

| Memory | Keal: iPhone 16, Safari | Greg: Android 17, Firefox 160 |
|---|---|---|
| JavaScript | 1.88 – 1.94 GB | 6.13 – ≥ 8.00 GB (8 GB was the test's cap then) |
| WebAssembly | 1.90 – 1.94 GB | ≥ 4.00 GB (WebAssembly's own 4 GB ceiling, 1 run) |
| GPU (WebGPU) | 1.88 – 1.91 GB | not tested: no WebGPU in this Firefox |
| JS + GPU together | 1.84 – 1.89 GB (middle run: 992 MB JS + 936 MB GPU) | not tested |

**What it says:**

- iPhone Safari gives a tab about **1.9 GB, and it's one budget.** Every kind of memory stops at the same place, and
  JavaScript and the GPU filled together stop there too, so a model's weights on the GPU come out of the same 1.9 GB as
  the page around it.
- **It's steady:** five rounds on the iPhone landed within about 0.1 GB of each other.
- **It's Safari on iOS, not phones:** Greg's Android phone in Firefox went past every cap the test had, at least three
  times the iPhone's limit for plain JavaScript.
- For models: a 1 GB model doesn't fit in 1.9 GB just because it's smaller. What counts is everything the runtime
  holds while it loads and runs it. See the [LFM3 in iPhone Safari](https://kealjones.com/lm-experiments/demos/lfm3-webllm/)
  demo for what that meant for LFM3 1.7B.

## Test your own phone

Open https://kealjones.com/lm-experiments/demos/memcap/ on the phone, tap Start and leave it awake. The tab will die
and reload several times; that's the test. "Share results" or "Save JSON" at the end gives you the numbers. Nothing
leaves the phone unless you share it. The page is the same origin as Squiggle's copy, so results from either show up in
both.
