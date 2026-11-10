#!/bin/bash
# Convert LiquidAI/LFM3-1.7B to an MLC/WebLLM package (q4f16_1 and, if QUANTS says so, q4f32_1) with
# the toolchain from toolchain.sh, compile the WebGPU model library (.wasm) and upload each quantization
# to its own model repo (kealjones/LFM3-1.7B-<quant>-MLC). CPU only.
#   TOOLCHAIN=<slug>/<job_id>   folder in the results dataset holding toolchain.tar.zst + wheels/ (from a
#                               toolchain job), or "local" when toolchain.sh ran in this job (./tvm, ./mlc-llm)
#   QUANTS="q4f16_1 q4f32_1"    quantizations to build (default q4f16_1)
#   REPO_PREFIX=kealjones/LFM3-1.7B   HF repo id prefix (repo = $REPO_PREFIX-<quant>-MLC)
#   bash build_lfm3.sh OUT_DIR
set -euo pipefail
OUT=$(realpath "${1:-out}"); mkdir -p "$OUT"
ROOT=$(pwd)
MODEL=${MODEL:-LiquidAI/LFM3-1.7B}
NAME=${NAME:-LFM3-1.7B}
QUANTS=${QUANTS:-q4f16_1}
REPO_PREFIX=${REPO_PREFIX:-kealjones/LFM3-1.7B}
CONTEXT=${CONTEXT:-4096}
PREFILL_CHUNK=${PREFILL_CHUNK:-256}
EMSDK_VERSION=${EMSDK_VERSION:-latest}
RESULTS=${RESULTS:-kealjones/tp-parse-runs}
step() { echo "== $(date -u +%H:%M:%S) $*" | tee -a "$OUT/steps.txt"; }
trap 'echo "FAILED at: $(tail -1 "$OUT/steps.txt")" | tee -a "$OUT/steps.txt"' ERR

if [ "${TOOLCHAIN:-local}" != "local" ]; then
  step "toolchain from $RESULTS:$TOOLCHAIN"
  export DEBIAN_FRONTEND=noninteractive
  # the same runtime libraries toolchain.sh built TVM against: tvm_tirx loads libLLVM-16.so.1 (job lfm3-mlc-4 failed without it)
  apt-get update -qq && apt-get install -y -qq --no-install-recommends build-essential git curl ca-certificates \
    llvm-16-dev libzstd-dev zlib1g-dev libedit-dev libxml2-dev zstd xz-utils >/dev/null
  pip install -q -U huggingface_hub 2>&1 | tail -1
  python - <<EOF
import os
from huggingface_hub import snapshot_download
d = snapshot_download("$RESULTS", repo_type="dataset", allow_patterns=["$TOOLCHAIN/toolchain.tar.zst", "$TOOLCHAIN/wheels/*", "$TOOLCHAIN/env.sh"], token=os.environ["HF_TOKEN"])
os.symlink(os.path.join(d, "$TOOLCHAIN"), "tc-dl")
EOF
  mkdir -p tc && tar --zstd -xf tc-dl/toolchain.tar.zst -C tc
  pip install -q --no-deps tc-dl/wheels/apache_tvm_ffi-*.whl 2>&1 | tail -1
  TC="$ROOT/tc"
else
  TC="$ROOT"
fi
export TC
export TVM_HOME="$TC/tvm" TVM_SOURCE_DIR="$TC/tvm" MLC_LLM_SOURCE_DIR="$TC/mlc-llm"
export TVM_LIBRARY_PATH="$TC/tvm/build/lib" TVM_TIRX_LIBRARY_PATH="$TC/tvm/build/lib"
export PYTHONPATH="$TC/mlc-llm/python:$TC/tvm/python:$TC/tvm/3rdparty/tvm-tirx/python:${PYTHONPATH:-}"
export SKIP_LOADING_MLCLLM_SO=1

step "python deps"
pip install -q -U numpy ml_dtypes typing_extensions packaging psutil cloudpickle tornado safetensors "transformers>=4.51" \
  huggingface_hub tqdm pandas datasets fastapi openai prompt_toolkit requests sentencepiece shortuuid tiktoken uvicorn pydantic 2>&1 | tail -1
pip install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -1
pip install -q "apache-tvm-ffi-orcjit>=0.1.2" 2>&1 | tail -1 || true
python -c "import torch, tvm_ffi; print('torch', torch.__version__, 'tvm_ffi', tvm_ffi.__version__)" | tee -a "$OUT/steps.txt"
python -c "import tvm_tirx, tvm, mlc_llm.interface.compile, mlc_llm.interface.convert_weight, mlc_llm.interface.gen_config; from mlc_llm.model import MODELS; print('mlc_llm ok, lfm3 registered:', 'lfm3' in MODELS)" | tee -a "$OUT/steps.txt"

if ! command -v emcc >/dev/null; then
  step "emscripten $EMSDK_VERSION"
  [ -d emsdk ] || git clone -q --depth 1 https://github.com/emscripten-core/emsdk.git
  ./emsdk/emsdk install "$EMSDK_VERSION" >/dev/null && ./emsdk/emsdk activate "$EMSDK_VERSION" >/dev/null
  source ./emsdk/emsdk_env.sh >/dev/null
fi
emcc --version | head -1 | tee -a "$OUT/steps.txt"

if [ "${QAD:-0}" = 1 ]; then
  # Liquid's quantization-aware-trained 4-bit weights (LFM3-1.7B-QAD-Q4_0.gguf) put exactly into our q4f16_1 build
  # (qad_to_mlc.py), plus a model library compiled for one conversation at a time (max_batch_size=1: the default
  # 128 reserves two ~81 MB scratch buffers, mostly logits for 128 sequences, that WebLLM never uses). Both .wasm
  # files go in the new repo; the original kealjones/LFM3-1.7B-q4f16_1-MLC is left alone. The package is built
  # outside $OUT so the results upload only gets the small files.
  # QAD_QUANT: q4f16_1 (default) or q4f32_1, for GPUs without 16-bit floats (fp32 scales, stored as bf16 like
  # every MLC q4f32 build). The template is our own build of that quantization.
  QQ=${QAD_QUANT:-q4f16_1}
  pip install -q gguf 2>&1 | tail -1
  step "download the template build and Liquid's QAD GGUF"
  python - <<PYEOF | tee -a "$OUT/steps.txt"
import os
from huggingface_hub import snapshot_download, hf_hub_download
t = snapshot_download("$REPO_PREFIX-$QQ-MLC"); os.symlink(t, "tpl")
g = hf_hub_download("LiquidAI/LFM3-1.7B-GGUF", "LFM3-1.7B-QAD-Q4_0.gguf"); os.symlink(g, "qad.gguf")
print("template", t, "gguf", g)
PYEOF
  QPKG="$ROOT/qad-pkg"
  step "QAD weights into the $QQ layout"
  python -I qad_to_mlc.py tpl qad.gguf "$QPKG" | tee -a "$OUT/steps.txt"
  WASM_B1="$QPKG/$NAME-$QQ-b1-webgpu.wasm"
  step "compile webgpu $QQ with max_batch_size=1"
  TVM_WASM_OBJ=o python compile_wasm.py "$QPKG/mlc-chat-config.json" --device webgpu --overrides "max_batch_size=1" \
    -o "$WASM_B1" > "$OUT/compile-b1.log" 2>&1 || { tail -40 "$OUT/compile-b1.log"; false; }
  for w in "$QPKG"/*.wasm; do
    echo "$(basename "$w"): $(strings "$w" | grep -o '"memory_usage": {[^}]*}' | head -1)" | tee -a "$OUT/steps.txt"
  done
  ls -la "$QPKG" | tee -a "$OUT/steps.txt"
  step "upload"
  python - "$QPKG" "$REPO_PREFIX-QAD-$QQ-MLC" "$QQ" <<'PYEOF' | tee -a "$OUT/steps.txt"
import os, sys
from huggingface_hub import HfApi
pkg, repo, quant = sys.argv[1:4]
api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
api.upload_folder(repo_id=repo, folder_path=pkg, path_in_repo=".", commit_message=f"LFM3 1.7B with Liquid's QAD 4-bit weights, MLC {quant}")
print("uploaded", f"https://huggingface.co/{repo}")
PYEOF
  mkdir -p "$OUT/keep-qad" && cp "$QPKG"/*.json "$OUT/keep-qad/"
  step "done"
  exit 0
fi

step "download $MODEL"
python - <<EOF | tee -a "$OUT/steps.txt"
import os
from huggingface_hub import snapshot_download
d = snapshot_download("$MODEL", allow_patterns=["*.json", "*.safetensors", "*.jinja", "*.txt", "*.model"], token=os.environ.get("HF_TOKEN"))
os.symlink(d, "hf-model"); print("model at", d)
EOF
ls -la hf-model/ | tee -a "$OUT/steps.txt"

for Q in $QUANTS; do
  PKG="$OUT/$NAME-$Q-MLC"; WASM="$OUT/$NAME-$Q-webgpu.wasm"
  step "convert_weight $Q"
  python -m mlc_llm convert_weight hf-model --quantization "$Q" --model-type lfm3 -o "$PKG" 2>&1 | grep -v "Warning: Cannot parse" | tail -15
  step "gen_config $Q"
  python -m mlc_llm gen_config hf-model --quantization "$Q" --model-type lfm3 --conv-template lfm3 \
    --context-window-size "$CONTEXT" --prefill-chunk-size "$PREFILL_CHUNK" -o "$PKG" 2>&1 | grep -v "Warning: Cannot parse" | tail -15
  python - "$PKG/mlc-chat-config.json" <<'EOF' | tee -a "$OUT/steps.txt"
import json, sys
c = json.load(open(sys.argv[1]))
print("mlc-chat-config:", {k: c.get(k) for k in ["model_type", "quantization", "context_window_size", "sliding_window_size", "prefill_chunk_size", "vocab_size", "temperature", "repetition_penalty"]})
print("conv stop:", c["conv_template"]["stop_token_ids"], c["conv_template"].get("system_prefix_token_ids"))
EOF
  step "compile webgpu $Q"
  ok=0
  for fmt in ${OBJFMTS:-o bc}; do
    step "compile webgpu $Q, host object format $fmt"
    rm -f "$WASM"
    if TVM_WASM_OBJ=$fmt python compile_wasm.py "$PKG/mlc-chat-config.json" --device webgpu -o "$WASM" > "$OUT/compile-$Q-$fmt.log" 2>&1; then
      ok=1; grep -v "Warning: Cannot parse" "$OUT/compile-$Q-$fmt.log" | tail -8; break
    fi
    echo "compile with $fmt failed; log tail:" | tee -a "$OUT/steps.txt"
    grep -v "Warning: Cannot parse\|^#[0-9]* 0x" "$OUT/compile-$Q-$fmt.log" | grep -i -B3 -A12 "error\|fatal\|assert\|LLVM ERROR" | head -80
  done
  [ "$ok" = 1 ]
  ls -la "$WASM" "$PKG" | tee -a "$OUT/steps.txt"
  strings "$WASM" | grep -o "tvm-release-[a-z0-9-]*" | head -1 | tee -a "$OUT/steps.txt" || true
  du -sh "$PKG" | tee -a "$OUT/steps.txt"
  step "upload $Q"
  python - "$PKG" "$WASM" "$REPO_PREFIX-$Q-MLC" <<'EOF' | tee -a "$OUT/steps.txt"
import os, sys
from huggingface_hub import HfApi
pkg, wasm, repo = sys.argv[1:4]
api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
api.upload_folder(repo_id=repo, folder_path=pkg, path_in_repo=".", commit_message="MLC package")
api.upload_file(repo_id=repo, path_or_fileobj=wasm, path_in_repo=os.path.basename(wasm), commit_message="WebGPU model library")
print("uploaded", f"https://huggingface.co/{repo}")
EOF
  # keep the small files in the job output; the shards stay in the model repo
  mkdir -p "$OUT/keep-$Q" && cp "$PKG"/*.json "$WASM" "$OUT/keep-$Q/" && rm -rf "$PKG" "$WASM"
done
step "done"
