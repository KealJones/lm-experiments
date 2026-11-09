#!/bin/bash
# Build the MLC/TVM toolchain that matches WebLLM 0.2.87's own model libraries, on a CPU box
# (Hugging Face Jobs, image python:3.12-bookworm), and pack it as a tarball for build jobs:
#   TVM apache/tvm e345029 (= mlc-llm 44fd06d's 3rdparty/tvm minus two CI commits; the string
#   "tvm-release-e345029-20261030" sits inside WebLLM 0.2.87's .wasm libs), built in-tree with its
#   standalone TIRx (3rdparty/tvm-tirx) and tvm-ffi, LLVM 16 (Debian) for the wasm32 host codegen;
#   TVM's web runtime (.bc files, emscripten) and mlc-llm's (empty) wasm runtime .bc;
#   mlc-llm 44fd06d's Python package with the LFM3 architecture registered.
# Everything lands in $OUT/toolchain.tar.zst plus $OUT/env.sh. Steps log to $OUT/steps.txt; the job
# stops at the first failure.
#   bash toolchain.sh OUT_DIR
set -euo pipefail
OUT=$(realpath "${1:-out}"); mkdir -p "$OUT"
ROOT=$(pwd)
TVM_COMMIT=${TVM_COMMIT:-e345029cedf0be76a087fcad9c89a97bed4f7204}
MLC_COMMIT=${MLC_COMMIT:-44fd06d04f22c87820e205b0f2b2e5e6a1f6ca85}
EMSDK_VERSION=${EMSDK_VERSION:-latest}
JOBS=${JOBS:-$(nproc)}
step() { echo "== $(date -u +%H:%M:%S) $*" | tee -a "$OUT/steps.txt"; }
trap 'echo "FAILED at: $(tail -1 "$OUT/steps.txt")" | tee -a "$OUT/steps.txt"' ERR

step "apt ($(nproc) cores, $(free -g | awk '/Mem/{print $2}') GB)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends build-essential cmake ninja-build git curl ca-certificates \
  llvm-16-dev libzstd-dev zlib1g-dev libedit-dev libxml2-dev zstd xz-utils >/dev/null
cmake --version | head -1 | tee -a "$OUT/steps.txt"
gcc --version | head -1 | tee -a "$OUT/steps.txt"
/usr/bin/llvm-config-16 --version | tee -a "$OUT/steps.txt"
/usr/bin/llvm-config-16 --targets-built | tr ' ' '\n' | grep -i webassembly | tee -a "$OUT/steps.txt"

step "python deps"
pip install -q -U pip setuptools wheel cython scikit-build-core setuptools-scm numpy ml_dtypes typing_extensions packaging psutil cloudpickle tornado \
  fastapi openai pydantic prompt_toolkit requests shortuuid tiktoken uvicorn tqdm safetensors 2>&1 | tail -1

step "clone tvm $TVM_COMMIT"
git clone -q --filter=blob:none --no-checkout https://github.com/apache/tvm tvm
git -C tvm checkout -q "$TVM_COMMIT"
git -C tvm submodule update -q --init --recursive 3rdparty/tvm-tirx
git -C tvm log -1 --format='%H %cd %s' | tee -a "$OUT/steps.txt"
git -C tvm/3rdparty/tvm-tirx log -1 --format='tirx %H %cd' | tee -a "$OUT/steps.txt"
git -C tvm/3rdparty/tvm-tirx/3rdparty/tvm-ffi log -1 --format='tvm-ffi %H %cd' | tee -a "$OUT/steps.txt"

step "tvm-ffi python (from the pinned submodule)"
pip wheel -q --no-deps -w "$OUT/wheels" tvm/3rdparty/tvm-tirx/3rdparty/tvm-ffi 2>&1 | tail -2
pip install -q --no-deps "$OUT"/wheels/apache_tvm_ffi-*.whl
pip install -q "apache-tvm-ffi-orcjit>=0.1.2" 2>&1 | tail -1 || true
python -c "import tvm_ffi; print('tvm_ffi', tvm_ffi.__version__)" | tee -a "$OUT/steps.txt"

step "cmake tvm (in-tree tirx, LLVM 16, no GPU)"
mkdir -p tvm/build && cd tvm/build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DTVM_TIRX_USE_LLVM=/usr/bin/llvm-config-16 -DTVM_TIRX_USE_CUDA=OFF -DTVM_TIRX_USE_Z3=OFF \
  -DTVM_USE_GTEST=OFF -DTVM_TIRX_BUILD_TESTS=OFF -DTVM_HIDE_PRIVATE_SYMBOLS=ON 2>&1 | tail -15
step "ninja -j$JOBS"
ninja -j"$JOBS" 2>&1 | grep -v "^\[" | tail -20 || true
ls -la lib | tee -a "$OUT/steps.txt"
test -f lib/libtvm_compiler.so || test -f lib/libtvm.so
cd "$ROOT"

step "tvm python check"
export TVM_LIBRARY_PATH="$ROOT/tvm/build/lib" TVM_TIRX_LIBRARY_PATH="$ROOT/tvm/build/lib"
export PYTHONPATH="$ROOT/tvm/python:$ROOT/tvm/3rdparty/tvm-tirx/python:${PYTHONPATH:-}"
python -c "import tvm_tirx, tvm; print('tvm ok', tvm.__file__); from tvm_tirx import tirx; from tvm import relax; print('relax ok')" | tee -a "$OUT/steps.txt"
python - <<'EOF' | tee -a "$OUT/steps.txt"
import tvm_tirx
from tvm_tirx.target import Target
print("webgpu target:", Target({"kind": "webgpu", "host": {"kind": "llvm", "mtriple": "wasm32-unknown-unknown-wasm"}}))
EOF

step "emscripten $EMSDK_VERSION"
git clone -q --depth 1 https://github.com/emscripten-core/emsdk.git
./emsdk/emsdk install "$EMSDK_VERSION" >/dev/null && ./emsdk/emsdk activate "$EMSDK_VERSION" >/dev/null
source ./emsdk/emsdk_env.sh >/dev/null
emcc --version | head -1 | tee -a "$OUT/steps.txt"

step "tvm web runtime (.bc)"
(cd tvm/web && TVM_HOME="$ROOT/tvm" make dist/wasm/wasm_runtime.bc dist/wasm/tvmjs_support.bc dist/wasm/webgpu_runtime.bc 2>&1 | tail -5)
ls -la tvm/web/dist/wasm | tee -a "$OUT/steps.txt"

step "mlc-llm $MLC_COMMIT python + wasm runtime (.bc)"
git clone -q --filter=blob:none --no-checkout https://github.com/mlc-ai/mlc-llm mlc-llm
git -C mlc-llm checkout -q "$MLC_COMMIT"
(cd mlc-llm/web && TVM_SOURCE_DIR="$ROOT/tvm" make dist/wasm/mlc_wasm_runtime.bc 2>&1 | tail -3)
ls -la mlc-llm/web/dist/wasm | tee -a "$OUT/steps.txt"
python register_lfm3.py "$ROOT/mlc-llm/python/mlc_llm" | tee -a "$OUT/steps.txt"
PYTHONPATH="$ROOT/mlc-llm/python:$PYTHONPATH" SKIP_LOADING_MLCLLM_SO=1 python -c "import mlc_llm.interface.compile, mlc_llm.interface.convert_weight, mlc_llm.interface.gen_config; from mlc_llm.model import MODELS; print('mlc_llm imports ok, lfm3 registered:', 'lfm3' in MODELS)" | tee -a "$OUT/steps.txt"

step "pack"
cat > "$OUT/env.sh" <<'EOF'
# source this with TC=/path/to/unpacked/toolchain
export TVM_HOME="$TC/tvm" TVM_SOURCE_DIR="$TC/tvm" MLC_LLM_SOURCE_DIR="$TC/mlc-llm"
export TVM_LIBRARY_PATH="$TC/tvm/build/lib" TVM_TIRX_LIBRARY_PATH="$TC/tvm/build/lib"
export PYTHONPATH="$TC/mlc-llm/python:$TC/tvm/python:$TC/tvm/3rdparty/tvm-tirx/python:${PYTHONPATH:-}"
export SKIP_LOADING_MLCLLM_SO=1
EOF
tar --zstd -cf "$OUT/toolchain.tar.zst" \
  tvm/build/lib tvm/python tvm/3rdparty/tvm-tirx/python tvm/web/dist tvm/web/emcc tvm/web/Makefile tvm/include tvm/3rdparty/tvm-tirx/include tvm/3rdparty/tvm-tirx/3rdparty/tvm-ffi/include tvm/3rdparty/tvm-tirx/3rdparty/tvm-ffi/3rdparty/dlpack/include tvm/3rdparty/tvm-tirx/3rdparty/compiler-rt \
  mlc-llm/python mlc-llm/web
ls -la "$OUT" | tee -a "$OUT/steps.txt"
step "done"
