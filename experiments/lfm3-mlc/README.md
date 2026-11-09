# LFM3-1.7B → MLC / WebLLM 0.2.87 (WebGPU)

Goal: a WebLLM-loadable MLC build of [LiquidAI/LFM3-1.7B](https://huggingface.co/LiquidAI/LFM3-1.7B) (q4f16_1 weights +
a WebGPU model library `.wasm` + `mlc-chat-config.json`) that loads on `@mlc-ai/web-llm` 0.2.87, for Squiggle's phone
path (`engine-webllm.js`, a model's `mlcRecord`). Target repos: `kealjones/LFM3-1.7B-q4f16_1-MLC` (and `-q4f32_1-MLC`,
which SwiftShader can run for a headless check).

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
