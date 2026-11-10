# LFM3-1.7B → MLC / WebLLM 0.2.87 (WebGPU)

Goal: a WebLLM-loadable MLC build of [LiquidAI/LFM3-1.7B](https://huggingface.co/LiquidAI/LFM3-1.7B) (q4f16_1 weights +
a WebGPU model library `.wasm` + `mlc-chat-config.json`) that loads on `@mlc-ai/web-llm` 0.2.87, for Squiggle's phone
path (`engine-webllm.js`, a model's `mlcRecord`). Target repos: `kealjones/LFM3-1.7B-q4f16_1-MLC` (and `-q4f32_1-MLC`,
which SwiftShader can run for a headless check).


## Where it stands: **LFM3 1.7B runs in Safari on an iPhone 16 through WebLLM at 13.7 tokens a second (4-bit, our own MLC build); a 3-bit build loses its judgement, and a long task still runs out of the tab's ~1.9 GB.**
## Why a from-source toolchain

- Upstream mlc-llm has no LFM2/LFM3. NakliTechie's fork (Kiln) adds `lfm2` (LIV short conv in an `RNNState` ring
  buffer next to the `PagedKVCache`, no custom TVM op) on a May 2026 base; its LFM2.5 build loads on WebLLM 0.2.86 only.
- WebLLM 0.2.87 (2026-10-30) ships `@mlc-ai/web-runtime` 0.28.0-dev1 whose tvmjs expects the renamed runtime
  functions (`runtime.TensorAllocWithScope`, not `runtime.TVMTensorAllocWithScope`); its own model libs carry
  `tvm-release-e345029-20261030`. apache/tvm `e345029` (2026-10-23) is exactly mlc-llm `44fd06d`'s `3rdparty/tvm`
  (mlc-ai/relax `629cc65`) minus two CI-only commits.
- The prebuilt wheels on mlc.ai are stale: `mlc_ai_nightly_cpu` 0.26.dev246 is TVM `837cb9de1` from 2026-09-02 (old
  names), `mlc_llm_nightly_cpu` 0.26.dev6 from 2026-09-02; the TIRx package (`tvm_tirx`, which mlc-llm 44fd06d
  imports) only has a cu130 wheel, and `apache-tvm-tirx==0.1.0a2` (what TVM e345029 pins) is not on PyPI (a3+ are).
  So the earlier tiny-gemma4 attempt's "overlay mlc-llm source on the nightly wheel" cannot work.
- Hence `toolchain.sh`: build TVM e345029 in-tree with its `3rdparty/tvm-tirx` (and tvm-ffi) on a CPU box with Debian's
  LLVM 16 (wasm32 host codegen), emscripten for TVM's web runtime `.bc` files, mlc-llm 44fd06d's Python package
  (no libmlc_llm: `register_lfm3.py` makes the `serve`/tokenizer native bits optional).

## Files

- `lfm3_model.py` / `lfm3_loader.py` / `lfm3_conv.py`: the architecture for mlc-llm 44fd06d (also traces on the Sep
  nightly wheel). Conv layers (kernel 7, state `(6, hidden)` in RNNState), attention with QK-RMSNorm, a per-head
  sigmoid output gate, RoPE computed in the model (`RopeMode.NONE`): global layers rotate half the head (zero-tail
  layout: pairs `(i, i+64)` for `i < 32`, theta 1e6), sliding layers the full head (theta 1e4) with a 256-token window
  applied per layer by the cache (`attn_kind` `mha_sliding`, like mlc-llm's Gemma 3, so `prefill_chunk_size` ≤ 256:
  the ragged in-chunk kernel only masks causally). Sandwich norms. Weights: q/k/v fused into `c_attn`, w1/w3 into
  `gate_up_proj`, `conv.conv.weight` → `conv1d_weight` (kept f16), `embedding_norm` → `model.norm`.
- `register_lfm3.py`: installs the above into an mlc_llm tree and patches the registries.
- `trace_test.py`: tiny-config trace, KV-cache kinds, loader mapping, quantized export (passes locally on the Sep wheel
  with two local patches to the wheel: the 6th KV-cache shape arg and `T.meta_var` in rnn_state.py — the wheel's
  TVMScript segfaults on annotated assignments here, and its Dlight pass segfaults on any model, Gemma 3 included,
  so the full compile could only be checked in the job).
- `toolchain.sh`, `build_lfm3.sh`, `job.sh`: the Hugging Face Jobs build (image `python:3.12-bookworm`, `cpu-upgrade`).

## Log

- 2026-11-09: job `lfm3-mlc-1` queued (toolchain + q4f16_1 + q4f32_1 in one job, 180 min cap, under $0.10).
- 2026-11-09: jobs 1-3: CMake too old (pip cmake), -j64 OOM (cap to 10), then the TVM+TIRx build worked (15 min) and convert_weight/gen_config passed, but the WebGPU compile died linking the wasm host code (emsdk 7.0.0 clang vs TVM's LLVM-16 bitcode). Job 4 (retry with an object-file fallback) died in 1 minute: the reused toolchain needs libLLVM-16.so.1. Job 5 installs llvm-16-dev in the reuse path.
- 2026-11-09: job 5 (LLVM libs installed): convert_weight + gen_config pass and the model compiles; the wasm link fails both ways. bc: clang 24 refuses the LLVM-16 module's DataLayout (lacks f128:64). o: wasm-ld misses libc++ symbols because TVM links with emcc. Job 6 links with em++ and tries o first.
- 2026-11-09: job 6 worked (exit 0, 8 min): `o` object format linked with em++, q4f16_1 and q4f32_1 compiled and uploaded to kealjones/LFM3-1.7B-q4f16_1-MLC and -q4f32_1-MLC (946 MB each, 6.7 MB wasm). Job 7 builds q3f16_1 + q3f32_1 (Keal's call, to see if 4-bit is too big on the phone).
- 2026-11-09: job 7: q3f16_1 built, compiled and uploaded to kealjones/LFM3-1.7B-q3f16_1-MLC (769 MB, 6.8 MB wasm); MLC pads the 3-bit groups (size 40) against LFM3's 2048-wide layers without trouble. q3f32_1 does not exist in MLC (convert_weight rejects it: only q3f16_0/q3f16_1 at 3 bits), so there is no 3-bit build SwiftShader can run. Both builds are wired into Squiggle (WLF3, WLF3Q3). Output unchecked: headless Chromium (SwiftShader, 8 GB sandbox) loads the 4-bit f32 build and VM fine, then the GPU process is OOM-killed (exit 9, ~6 GB used) on the first generation.
- 2026-11-10: on Keal's iPhone in Squiggle the 4-bit build (q4f16_1) greets normally with the full prompt and tools
  (first word 15 s, 13.7 tok/s) and picks the right tool, but runs out of memory mid-task; the 3-bit build runs but
  overthinks even "Hii" (400 tokens of "likely a placeholder…"), with or without Squiggle's prompt, so the port is right
  and plain 3-bit rounding is what broke it. Job 8 (`QAD=1`): `qad_to_mlc.py` puts Liquid's quantization-aware-trained
  4-bit weights (LFM3-1.7B-QAD-Q4_0.gguf) into the q4f16_1 layout exactly (Q4_0 `(k-8)*d` = MLC `(q-7)*s` with
  q = 15-k, s = -d; checked bit-exact on every layer kind; 0.99 correlation with our rounded weights, ~13% mean
  difference), embedding (Q6_K in the GGUF) and norms kept from our build. It also compiles a library with
  `max_batch_size=1`: the default 128 reserves ~81 MB of scratch in each of batch_prefill and batch_decode (wasm
  `_metadata` memory_usage), mostly logits for 128 sequences. Uploads kealjones/LFM3-1.7B-QAD-q4f16_1-MLC; the
  original repo is untouched.
- 2026-11-10: the results collector had committed job 5's 31 model shards (~800 MB) to this repo (each under its
  50 MB per-file cap). Removed from the tree; `hf/bridge.py` now also caps a job at 100 MB in total. They're still in
  git history (cleaning that needs a force push, which is Keal's call).
- 2026-11-10: job 9 (`QAD=1 QAD_QUANT=q4f32_1`): the QAD weights in the q4f32_1 layout, for GPUs without 16-bit
  floats (shader-f16), where Squiggle would otherwise fall back to the CPU. q4f32_1 packs the 4-bit integers the same
  way but its fp32 scales sit on disk as bf16 (records tagged `f32-to-bf16`, widened when WebLLM loads them), so the
  QAD scales round to bf16 (≤0.4%, next to 4-bit rounding's ~13%); the integers stay exact. `qad_to_mlc.py` now
  writes each record in its template's own dtype and on-disk format; checked locally on layer 0 of
  kealjones/LFM3-1.7B-q4f32_1-MLC (within bf16 rounding on every layer kind, corr 0.99 with our rounded build).
  Uploads kealjones/LFM3-1.7B-QAD-q4f32_1-MLC.
