# Tiny Gemma 4

Goal (Keal, 2026-10-28/29): a Gemma 4 small enough for an iPhone browser tab (wllama, CPU), by surgery on
Gemma 4 E2B plus a short heal (distillation from Gemma itself; no Claude-written data).

Plan, from the "Model compression and vocab pruning" chat: vocab ~262K → ~80K (chosen from public text),
drop the middle layers that change the residual least (keeping the KV-source layers the shared layers reuse),
narrow the FFN, later hidden 1536 → 1024; heal on ~85% generic text, ~10% chat, ~5% Squiggle-format prompts.
Gemma 4 has no MatFormer nesting (unlike 3n), so there is no free slice.

Phone measurements that set the target (2026-10-28, iPhone Safari, wllama 3.8.1 compatibility build):
a tab survived ~1.9 GB; speed tracks the body size (Squiggle Small 350M: 16-18 tok/s on 4 cores or GPU;
Qwen3 0.6B: 9.3 tok/s on 4 cores). wllama's llama.cpp (b11364) supports gemma4.

## Stage 1 (`stage1.py`, no training)

Bits per byte on held-out FineWeb-Edu, code (codeparrot) and Squiggle teacher episodes for: full E2B-it,
pruned vocab, vocab + skipped layers, vocab + narrower FFN, combinations; LFM2.5-350M and Qwen3-0.6B as
baselines. Writes `results.json`, `RESULTS.md`, `kept_ids.json`, `tokenizer_pruned.json`.

Keal's own token list (keal_tokenizer) is private and is not used here; its coverage is checked offline.

### Stage 1 results (2026-10-29, l4x1, 7.6 min, ~$0.15) — `hf-stage1/`

Bits per byte (lower is better), no healing:

| config | web | code | Squiggle | total params |
|---|---|---|---|---|
| full E2B-it | 1.42 | 1.03 | 1.59 | 4.63B |
| vocab 80K | 1.45 | 1.05 | 1.59 | 2.72B |
| vocab + FFN 66% | 1.51 | 1.29 | 1.42 | 2.19B |
| vocab + FFN 42% | 1.70 | 1.53 | 1.56 | 1.81B |
| vocab + skip 6 | 2.27 | 3.25 | 3.41 | 2.20B |
| vocab + skip 10 | 2.91 | 4.12 | 4.00 | 1.89B |
| vocab + skip 17 | 6.60 | 8.73 | 9.31 | 1.38B |
| LFM2.5-350M | 1.31 | 1.51 | 2.07 | 0.35B |
| Qwen3-0.6B | 0.92 | 0.56 | 1.07 | 0.60B |

- The vocab cut is nearly free: ~99.2% of counted text covered, +1% tokens, samples identical, 4.63B → 2.72B.
  (Offline: 2.0% of Keal's own writing uses tokens outside the 80K, mostly emoji and slang.)
- Layers that change the residual least are 25–33, the KV-shared ones; skipping them breaks the model before
  healing (garbled samples from skip 6 on). FFN 66% still writes correctly; FFN 42% collapses ("model\nmodel…").
- The scorer matches transformers' own loss exactly (checked on a tiny random Gemma 4).
- Qwen3-0.6B models raw text far better than E2B-it (partly because E2B-it is chat-tuned).
- `surgery.py` physically cuts layers/FFN/vocab; verified identical to the simulated cuts on a tiny model.

### Heal probe (2026-10-29, a100-large, ~21 min training, `hf-heal-probe2/`)

Student: 80K vocab, layers 28–33 dropped (29 kept), FFN 42% → **1.50B params**. Distilled from uncut E2B-it
(KL over the kept vocab + 0.1 × next-token loss), batch 4 × 1024, lr 2e-4, ~4K tokens/s → **4.3M tokens**.
Checkpoint (bf16, 3 GB) is in the private results repo `kealjones/tp-parse-runs` under
`tiny-gemma4-heal-probe2/6ae3018c3fb22a235dd557a6/ckpt/` (too big for git).

| | web bpb | Squiggle bpb |
|---|---|---|
| teacher (E2B-it, 80K vocab) | 1.49 | 1.58 |
| student, cut, before healing | 2.66 | 2.84 |
| step 150 (0.6M tokens) | 1.47 | 0.88 |
| step 600 (2.5M tokens) | 1.31 | 0.59 |
| end, step 1062 (4.3M tokens) | 1.24 | 0.54 |

Read with care:
- **Squiggle bpb is contaminated**: teacher episodes share long, near-identical harness prompts, and the training
  mix cycled the other ~150 episodes many times, so the student memorised the harness text. Hold out whole
  episodes and strip shared system prompts before using this number.
- **Student < teacher on web** means it is learning raw web text (the 0.1 next-token term) rather than staying
  faithful to the chat-tuned teacher. No chat samples were taken, so it's unknown how much instruction-following
  survived. Next time: KD only (or much smaller CE weight) and greedy chat samples at every eval.
- Real signal: un-healed garbage (2.66) recovers past the teacher's raw-text level within ~0.6M tokens.
- 1.5B total (body ~0.8B) is still too slow for the phone target; the body needs to come down to ~0.2–0.4B.

Cost: stage 1 $0.10; probe 1 $1.25 (crashed at 2 min on zero-padded per-layer config keys, then hung on
streaming threads until the 30-min limit; both fixed: `surgery.py` key parsing, hard `os._exit` in both
scripts); probe 2 $1.11. Total **$2.46**.

Next, if continuing: (1) fix the eval (episode-level hold-out, chat samples, KD-only); (2) try a smaller
student (drop more of 25–33 plus FFN ~35%, body ~0.4B); (3) only then a longer heal on an H200.
Also compare against simply fine-tuning Qwen3-0.6B, which already runs at 9.3 tok/s on the iPhone and scores
far better than E2B-it on raw-text bpb.

### Stage 1b: direct importance, Minitron-style (2026-10-29, l4x1, 10.7 min, ~$0.15) — `hf-analyze/`

Per-layer removal (bpb change on web / Gemma replies, one layer at a time) disagrees with stage 1's angular-distance
proxy. Harmless or slightly helpful to remove: **12, 11, 2, 6, 7, 9** (12 and 11 lower web bpb by ~0.19).
Costly: **1 (+1.6), 3 (+1.6), 4 (+0.55), 23 (+0.53), 33 (+0.33)**. Layers 25–32 cost little one at a time;
stage 1's "skip 6" also removed 33, which is part of why it collapsed. Top 1024 of 1536 hidden channels carry 75%
of the activation mass.

Width-heavy candidates, physically cut, before healing (teacher web 1.47 / code 1.08 / Gemma replies 1.61):

| candidate | body | total | web | code | replies |
|---|---|---|---|---|---|
| FFN 50% | 1.10B | 1.94B | 1.63 | 1.69 | 1.86 |
| hidden 1280, FFN 50% | 0.92B | 1.73B | 1.70 | 1.85 | 1.91 |
| hidden 1024, FFN 50% | 0.73B | 1.53B | 2.12 | 2.42 | 2.43 |
| hidden 1024, FFN 42%, drop 2/6/11/12 | 0.60B | 1.31B | 2.46 | 3.71 | 3.18 |
| hidden 1024, FFN 35%, drop 6 | 0.50B | 1.17B | 3.09 | 5.19 | 4.31 |
| hidden 768, FFN 42% | 0.49B | 1.27B | 2.64 | 3.62 | 3.43 |

Most of the remaining "total" is per-layer embeddings (80K × layers × 256 ≈ 0.6–0.7B): cheap lookups, but memory.
Shrinking or dropping them is the next lever after the body.

**Heal 1** (`hf-heal1/`): hidden 1024, FFN 42%, layers 2/6/11/12 removed (0.60B body), distillation only.
Result (a100-large, 68.8 min, $2.87, 16M tokens, KD only): web bpb 2.58 → **1.34** (teacher 1.49), Gemma replies from
held-out episodes 3.13 → **1.14** (teacher 1.61: the student learns Squiggle's format, which E2B-it never saw).
Greedy chat samples went from blank lines to chat-shaped answers that drift and loop ("The capital of France is
**Gemma de France…", "The sky is a blue and the sky is a blue."): 85% raw web teaches text, not answering.
Checkpoint: `kealjones/tp-parse-runs` → `tiny-gemma4-heal1/6ae32a7041e90535df78a3ff/ckpt/` (bf16, 2.6 GB).

**Heal 2** (`hf-heal2-chat/`): continue from heal 1 with 35% OpenAssistant oasst1 chat contexts (human-written,
Apache-2.0; distillation targets come from the teacher), lr 1e-4, ~22 min.
Result (a100-large, 22.8 min, $0.95, 4.9M tokens): web 1.34 → 1.34, Gemma replies 1.14 → 1.11. Greedy samples now
answer like an assistant ("The capital of France is **Paris…", "Here is a Python function that reverses a string.
```python def reverse_string…", "Here is a breakdown of why the sky is blue…") but still drift into wrong facts and
repetition. Checkpoint: `kealjones/tp-parse-runs` → `tiny-gemma4-heal2-chat/6ae33bbe41e90535df78b7d7/ckpt/`.

### Where it stands (2026-10-29 morning)

- A 0.60B-body Gemma 4 (1.31B total, 80K vocab, hidden 1024, FFN 42%, 31 of 35 layers) heals well on text
  (bpb below the chat-tuned teacher's) after ~21M tokens, and has started answering in chat form, but is far
  from coherent. Minitron-scale heals use billions of tokens; this was ~0.02B.
- Spend for this stretch (Keal's $5): analysis $0.15, heal 1 $2.87, heal 2 $0.95 = **$3.97**. Earlier tonight:
  stage 1 $0.10, probes $2.36.
- Next options: (1) a longer heal on an H200 (~3× A100 throughput per the earlier estimate) with ~30% chat
  contexts, ~$5 per hour → ~300–400M tokens; (2) drop or shrink the per-layer embeddings (most of the 0.7B
  non-body parameters) to cut phone memory; (3) GGUF export of the checkpoint and a phone test (needs llama.cpp's
  converter to accept the cut config and the 80K tokenizer). Samples should use a repetition penalty when judging
  quality, as the app does.

### Heal 3: E2B's own answers (2026-10-29, h200, 78 min, ~$6.55) — `hf-heal3b/`

On-policy data first (`gen.py`, Gemma 4 E2B-it on vLLM answering questions only, never the datasets' answers):
gen2 (a100, 15 min, ~$0.61) answered 10,686 prompts (Hermes function-calling requests with their tools in
Gemma's native format + SmolTalk maths/code/general) and kept 6,395; 40% hit the 1,024-token cap. gen3 (a100,
28.5 min, ~$1.19) answered 17,000 new SmolTalk questions with a 2,048 cap and kept 14,126. Together ~20.5k
conversations (2,668 with tool calls), ~20M tokens. (gen1 failed on a missing C compiler; heal3 died in 18 s on
an old `brotli` the Hub client now needs, so the job pins `brotli>=1.2.0`.)

Heal 3 resumed heal 2: distillation only, lr 1e-4, batch 12 × 1024, mix 38% E2B answers, 10% E2B tool calls,
15% FineMath, 10% Squiggle episodes, 13% web, 7% code, 7% oasst1. 3,841 steps, 47.2M tokens.

| | web bpb | agent replies bpb |
|---|---|---|
| teacher (E2B-it) | 1.49 | 1.61 |
| heal 2 (start) | 1.34 | 1.11 |
| heal 3 | 1.33 | 1.10 |

bpb barely moved, but behaviour changed a lot:

| prompt | heal 2 | heal 3 |
|---|---|---|
| capital of France (greedy) | "The capital of France is **** France** (or ** France**)…" | "The capital of France is **Paris** (or **Parisian**).<turn\|>" — stops |
| weather in Phoenix, `get_weather` tool | "I am **not a large language model…" | `<\|tool_call>call:get_weather{city:<\|"\|>Phoenix<\|"\|>}<tool_call\|>` — a correct native call |
| 17 × 23 | "Please provide the answer…" | "**1. Set up the equation** … 17 × (20 + 3) = …" |
| reverse a string | broken signature | "Here are a few ways… 1. Using `reversed()`" |

Still wrong in places (the sky "reflects light from the sun"; greedy decoding repeats `<|tool_response>`
after a call, which the runtime should stop on). Checkpoint: `kealjones/tp-parse-runs` →
`tiny-gemma4-heal3b/6ae371135ddcdc083026213d/ckpt/`. GGUF: `kealjones/tiny-gemma4-test`,
`tiny-gemma4-heal3-v2-Q4_0.gguf` (use this one, see below).

**GGUF special-token bug (found on heal 3, fixed).** In the browser the heal-3 GGUF echoed questions back, even
given the exact training prompt. Pruning had shifted token ids by one, and llama.cpp's converter marked the wrong
tokens as control tokens: `<|turn>`, `<turn|>`, `<|tool>`, `<tool|>` came out as plain text (so a prompt's turn
markers were split into text pieces: 86 tokens instead of 72), and generation ended on `<eos>` instead of `<turn|>`.
Every earlier GGUF had it too. `fix_tokens.py` sets the types by token text as in the official E2B GGUF (unsloth's)
and `gguf_job.sh` now runs it; `fix_upload.sh` fixed heal 3's file in place of a rebuild. After the fix, wllama's
chat completion with a `get_weather` tool returns the call `{"city": "Phoenix"}`.

Spend for the $10 bigger-heal stretch: gen1 ~$0.16, gen2 ~$0.61, gen3 ~$1.19, GGUF builds ~$0.06, heal3 crash
~$0.05, heal 3 ~$6.55 = **~$8.62**.

### Heal 4 prep: real multi-turn tool data (2026-11-02, CPU only, $0) — `prep_tools.py`, `heal4.json`

What heal 3 got wrong in the browser (Keal's screenshots, small-model mode on): it ignored a detail given in a
later turn ("just use web_search for patrick stewart" → "they have not provided any names"), wrote
"Tool Call Plan (Simulated): `web_search(...)`" in its thinking instead of calling, asked menus of questions
("For example, are you looking for: 1. … 2. …"), and wrote nothing after a tool result. Causes, from the data:

- **Every training conversation was one turn.** gen.py took only each dataset's first user message; the model
  never saw a later user turn carry the detail it needs.
- **No tool call ever got a result.** The Hermes examples end at the call, so "call → result → answer from it"
  was never seen.
- **The loss covered everything,** including user turns and (for distillation) the teacher's guesses at text it
  never writes. The Squiggle episodes were also joined as plain text without turn markers, in Squiggle Small's
  fenced `<think>` format, which isn't how tiny Gemma is prompted.
- The filter only checked that an answer finished. In fact few answers were bad: re-filtering drops 19 of
  20,521 (13 calls written as text, 6 question menus). The "simulated" thinking and the question menus are E2B's
  own habits, which the student copied; the fix is mostly the missing data, not the filter.

Changes:
- **Toucan-1.5M SFT** (Agent-Ark, Apache-2.0; tasks by open models, answers by GPT-OSS 120B / Kimi K2 / Qwen3 32B,
  tools really executed on MCP servers). Rendered with E2B's own chat template, so calls and results use Gemma 4's
  native tokens and match what wllama sends at inference. Conversations over 2,000 tokens are cut after the last whole model
  turn that fits (or dropped; tool results were first cut to 1,200 characters, since changed, see below); the "irrelevant" subset (answer
  without a tool) kept at 15%. Dry run on 8,000 rows: 53% kept (36% multi-turn, 32% single, 17% diversified,
  15% irrelevant), median 1,149 tokens, 90th percentile 1,836; 40% of tokens are the model's own.
- **nvidia/When2Call left out:** its SFT split has no tool calls, and most answers refuse ordinary requests
  ("Apologies, I'm unable to create a Facebook ad copy"). Salesforce APIGen-MT is non-commercial, also left out.
- **MASK=1:** chat-format sources train only on what the model writes (thinking, text, calls, the
  `<|tool_response>` stop token, `<turn|>`), not the system prompt, declarations, user turns or tool results.
  Segments split at special tokens, so the ids match encoding the whole text (checked: 0 mismatches in 1,000).
- **SEQ 2048** (batch 6, same tokens per step) so a conversation fits one row.
- Squiggle fenced-format episodes dropped from the training mix (still the `agent_replies` eval).
- New eval: `tools_replies` bpb on 120 held-out Toucan conversations (model tokens only), and three probes from
  the screenshots: the detail-in-turn-2 search, answering from a tool result, "What do you remember about me?"
  (tools: `web_search`, `recall`).

**Review of the plan (Keal shared a second opinion, 2026-11-02); what it caught and what changed:**
- *Conversations could still straddle rows* (right: `Packer` sliced the stream every SEQ tokens, so a 1,500-token
  conversation after another one was split and its answers trained without their turns). Now chat records are
  never split: whole conversations share a row while they fit, the rest is masked padding (`PACK_CONVS=0`: one
  per row). Plain text still streams.
- *Cut tool results can hide the evidence an answer used* (right: 1,200-character cuts touched 16% of kept
  conversations). Results are no longer cut; conversations that don't fit are dropped (kept share 53% → 47%).
- *Multi-turn records can lose their follow-ups* (right: fitting to 2,000 tokens left 30% of "multi-turn"
  conversations with one user turn; 70% keep two or more). Now counted in the prep stats.
- *KD alone learns E2B's guesses on Toucan's text, not Toucan's answers.* `CE_SRC` adds next-token loss per
  source (e.g. `{"toucan": 1.0}`) without touching web/maths/code. Which is better is what the pilots decide.
- *Keep heal 3 and keep dated checkpoints* (heal 3's checkpoint is in its own run folder and is only read).
  `CKPT_KEEP` keeps the last two `ckpt-step<N>` copies besides `ckpt`.
- *Score behaviour, not just bpb.* Probes now pass/fail: a search with the detail given in turn 2, a name given in
  turn 2, answering from a result, **the same call with a different result** (the answer must change), a tool
  error (no invented answer), and "what do you remember about me" (no web search). Reported as `probes_greedy`
  and `probes_app` at every eval, next to the old sky/Python/maths samples to catch regressions.
- *Add Squiggle's own workflow* (find, plan, done, fresh step contexts) — agreed, not in this round: it needs E2B
  run through the real harness in native format, a generation run of its own. Generic multi-turn tool use first.

**Second review (2026-11-02), also applied:**
- *Probe checks were too loose* (an empty reply passed "remember about me"; a reply with both 61 and 97 passed
  both weather probes; a half-written call counted as a search). Calls are now parsed: one complete
  `web_search` whose query has the right words; weather answers need the right number and not the other one, and
  no call; a tool error passes on a retry or a plain "it failed" with no made-up temperature; "remember about me"
  needs a `recall` call or a plain "nothing saved". 18/18 hand-made good/bad replies scored correctly.
- *Equal minutes isn't equal training* (the clock included loading, prep and the first eval, and drove the LR
  schedule). `STEPS` now fixes the step count and schedule; `MINUTES` is only a spending cap, and a run stopped
  by the cap says so in its log and summary.
- *"Whole conversations" wasn't literal*: a too-long one was cut, and packed conversations can attend to the one
  before them. A conversation longer than a row is now dropped, and the pilots use one conversation per row.
- Correction to the notes above: tool results are no longer cut, but a conversation over 2,000 tokens is still
  shortened to its last whole exchange that fits (only dropped if not even the first fits). 70% of kept
  "multi-turn" conversations still have two or more user turns.
- Passing the pilots shows generic multi-turn tool use; it won't show Squiggle's `find → plan → steps → done`.

**Next, needs budget:** two pilots on an H200 from heal 3, same data, seed and **750 steps** each (~16 min of
training, ~8 min of loading/prep/eval): `heal4-pilot-kd.json` (distillation only) and `heal4-pilot-ce.json`
(plus next-token loss on Toucan's answers), about $2 each, hard cap ~$3.30. Then `heal4.json` (2,400 steps,
~$5.50) with the winner, then GGUF and WebLLM exports (below) and the same probes in Squiggle. To launch one: copy it to `hf/queue/` and push.

### Heal 4 also ships as a WebLLM build (plan, 2026-11-02) — `to_mlc.py`, `patch_mlc.py`, `mlc_job.sh`

Why: on Keal's iPhone, WebLLM (MLC on WebGPU) ran stock models 5-12x faster than wllama's CPU build (Llama 3.2 1B
~30 tok/s vs ~2.6; Squiggle `app/memtest.html`), and Squiggle now has a WebLLM path for phones
(`engine-webllm.js`). Tiny Gemma 4 on WebLLM should land near Qwen3 0.6B's ~34 tok/s instead of CPU speed.

What WebLLM needs: weights in MLC's format (`mlc_llm convert_weight` + `gen_config`, from the safetensors
checkpoint, not the GGUF) and a model library compiled for WebGPU (`mlc_llm compile --device webgpu`, a .wasm).
MLC-LLM added a `gemma4` architecture (commit 44fd06d, 2026-10-30) and WebLLM 0.2.87 (same day) loads its
token-id artifact contract (prefill_tokens / decode_tokens), which Gemma 4's per-layer embeddings need.

Fit with the cut model (checked against heal 3b's config): 31 layers, `num_kv_shared_layers` 20 with both layer
types among the first 11, sliding window 512, hidden 1024, vocab 79,997: MLC's config checks pass on paper.
Two things need handling:
- **FFN 2580** isn't a multiple of 32 (4-bit groups): `to_mlc.py` pads with zero channels to 2592, as `to_gguf.py` does.
- **MLC's gemma4 always builds E2B's audio tower** and expects its weights; tiny Gemma has none, and E2B's audio
  projector outputs 1536 wide, not 1024. `patch_mlc.py` adds a `text_only` switch to the installed mlc_llm
  (skip the audio modules, the `audio_embed` export, the artifact's audio input and the loader's audio
  parameters). Checked that it applies cleanly and repeatably to commit 44fd06d and still compiles; not run.

Plan: `mlc-smoke.json` on heal 3's checkpoint now (CPU, under ~$0.05) to prove the pipeline; `mlc_job.sh` stops
at the first failing step and `steps.txt` names it. Then heal 4 runs as planned, and `heal4-mlc.json` exports
it next to the GGUF job. Squiggle gets a model entry pointing at `kealjones/tiny-gemma4-test-MLC` (custom
WebLLM appConfig) plus a Gemma 4 tool-call writer/parser in `engine-webllm.js`, like the Qwen ones.
Risks: the .wasm must match WebLLM 0.2.87's TVM web runtime (pin the MLC wheels with `MLC_SPEC` if the nightly
has moved on), and the Emscripten version MLC wants (`EMSDK_VERSION`, default 3.1.56) may need adjusting.

### Heal 4 pilots (2026-11-02, h200, 750 steps each, ~$2.10 each) — `hf/done/tiny-gemma4-heal4-pilot-*`

First, heal 3 measured in the browser with `squiggle/tests/e2e/model-probes.mjs` (the app's wllama runtime and the
GGUF's own template; pairs that differ in one thing). Clean prompt: 2/10. It passes a name given in turn 2
(`web_search("Patrick stewart")`), so it *can* read later turns; it fails every tool result (empty reply), searches the
web for weather text the user pasted, and picks `web_search` even with `recall` declared (its thinking only lists the
first two tools). With the app's small-model prompt the same turn-2 test becomes `plan(steps: ["Find where the login
form is defined"])` (copied from plan's own example) and a tool result becomes "For example, are you looking for: …":
that prompt produced Keal's screenshots. A reworded prompt ("look things up with web_search…") still failed: it called
`find`, i.e. it takes the first-declared tools whatever the prompt says. Gemma 4 E2B (the teacher) on the same tests:
passes turn 2, answers from 61°F and 97°F results correctly, retries after an error, calls `recall` when declared.

Pilots, both resumed from heal 3, same data (Toucan 40%, E2B answers 26%, rest maths/web/code/oasst1), 750 steps,
masked to model tokens, one conversation per row:

| | heal 3 | A: distillation | B: + next-token loss on Toucan |
|---|---|---|---|
| probes greedy / sampled | 2/6 / 2/6 | **5/6 / 5/6** | 3/6 / 3/6 |
| answers from a 61°F result | empty | "currently **61°F** … light rain" | ✓ |
| same call, 97°F result | empty | "currently **97°F** … clear skies" | quotes the high (101°F) instead ✗ |
| tool error | empty | says the search had an issue ✓ | ✓ greedy, ✗ sampled |
| Star Trek, detail in turn 2 | ✓ | ✓ | ✗ greedy ("I don't have access to real-time…") |
| "what do you remember about me" (recall declared) | `web_search` | `web_search("me")` ✗ | "I remember to be a person." ✗ |
| held-out Toucan answers (bpb) | 0.993 | 0.928 | 0.768 (trained on that text) |
| web (bpb) | 1.327 | 1.399 | 1.397 |
| E2B agent replies (bpb) | 1.101 | 1.165 | 1.154 |

- **A wins on behaviour.** It now reads tool results (the answer changes with the result) and handles an error without
  inventing weather. B's lower Toucan bpb is just learning Toucan's own text; it behaves worse.
- **Both regressed on general text:** web +0.07 bpb, and the greedy 17 × 23 sample went from 391 to wrong steps; the sky
  answer is still nonsense. 750 steps of a 40%-tool mix pulls the model away from plain text: a full heal needs more
  E2B answers / web in the mix, or a smaller LR.
- **Tool choice is still by position:** with `recall` declared after `web_search`, both still search the web. Toucan's
  examples are mostly "the first tool fits"; this needs examples where the right tool isn't first.
- Spend: ~$4.15 of Keal's $10. Checkpoints: `kealjones/tp-parse-runs` → `tiny-gemma4-heal4-pilot-kd/6ae969b60e0338d1bb7ee4cb/ckpt/`
  (A), `tiny-gemma4-heal4-pilot-ce/6ae96ed50e0338d1bb7ee913/ckpt/` (B). `gguf-heal4a.json`: draft GGUF of A (~$0.03).

### Later: vision (Keal, 2026-10-29)

The cut keeps only Gemma 4's text model: E2B's vision and audio encoders were never copied, and the GGUF has no
image projector, so tiny Gemma 4 is text-only (Squiggle's OCR still reads text in photos). E2B's vision encoder
can't simply be reattached either: its projector feeds the language model at E2B's width (1536) and the cut
model is 1024 wide. To bring vision back: slice the projector's output to the kept hidden channels (the same
`hidden_keep` indices as `surgery.cut`), then heal on image–text pairs with E2B as the teacher, and export the
encoder + projector as a llama.cpp mmproj file for wllama. Its own project; on the list for after the text heals.
