#!/bin/bash
# Build a WebLLM (MLC, WebGPU) package of a tiny-Gemma-4 checkpoint for Squiggle's phone path
# (squiggle app/src/engine-webllm.js) and upload it to a public model repo:
#   CKPT=repo:path/to/ckpt REPO=kealjones/tiny-gemma4-test-MLC NAME=tiny-gemma4-heal4 bash mlc_job.sh OUT_DIR
# Steps: package (to_mlc.py) -> text-only patch (patch_mlc.py) -> convert_weight q4f16_1 -> gen_config
# (4K context; MLC clamps Gemma 4's prefill chunk to its 512 sliding window) -> compile --device webgpu -> upload.
# CPU only. DRAFT (2026-11-02), not run yet: every step logs to $OUT/steps.txt and the job stops at the first
# failure, so a first run on heal 3 says which step needs work before heal 4 lands.
set -euo pipefail
OUT=${1:-out}; mkdir -p "$OUT"
step() { echo "== $(date -u +%H:%M:%S) $*" | tee -a "$OUT/steps.txt"; }
trap 'echo "FAILED at: $(tail -1 "$OUT/steps.txt")" | tee -a "$OUT/steps.txt"' ERR

step "tools"
(command -v gcc && command -v cmake && command -v git) >/dev/null || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gcc g++ make cmake git xz-utils >/dev/null)
# The compiled .wasm has to match the TVM web runtime inside the WebLLM version Squiggle loads (0.2.87).
# MLC_SPEC pins the wheels; the default is the nightly CPU build.
pip install -q --pre ${MLC_SPEC:-mlc-ai-nightly-cpu mlc-llm-nightly-cpu} -f https://mlc.ai/wheels 2>&1 | tail -2
# The nightly mlc-llm wheel (0.26.dev6 on 2026-11-03) predates Gemma 4, so its Python package is replaced with
# mlc-llm's own source at MLC_COMMIT (Gemma 4 + the artifact manifest WebLLM 0.2.87 reads); the wheel's
# compiled libraries stay. The first run on heal 4 failed here without this (no model/gemma4 in the wheel).
step "mlc-llm python at ${MLC_COMMIT:-44fd06d04f22c87820e205b0f2b2e5e6a1f6ca85}"
git clone -q --depth 1 https://github.com/mlc-ai/mlc-llm mlc-src
git -C mlc-src fetch -q --depth 1 origin ${MLC_COMMIT:-44fd06d04f22c87820e205b0f2b2e5e6a1f6ca85} && git -C mlc-src checkout -q FETCH_HEAD
SITE=$(python -c "import mlc_llm, os; print(os.path.dirname(mlc_llm.__file__))")
cp -r mlc-src/python/mlc_llm/. "$SITE"/
python -c "import mlc_llm.model.gemma4, mlc_llm.protocol.artifact_manifest; print('gemma4 ok')" | tee -a "$OUT/steps.txt"
python -c "import mlc_llm, tvm; print('mlc_llm', getattr(mlc_llm, '__version__', '?'), 'tvm', tvm.__version__)" | tee -a "$OUT/steps.txt"
# WebGPU compile needs Emscripten (the version MLC's docs pin) and TVM's prebuilt web runtime.
git clone -q --depth 1 https://github.com/emscripten-core/emsdk.git
./emsdk/emsdk install ${EMSDK_VERSION:-3.1.56} >/dev/null && ./emsdk/emsdk activate ${EMSDK_VERSION:-3.1.56} >/dev/null
source ./emsdk/emsdk_env.sh >/dev/null

step "download checkpoint"
python - <<EOF
import os
from huggingface_hub import snapshot_download
repo, path = os.environ["CKPT"].split(":", 1)
d = snapshot_download(repo, repo_type="dataset", allow_patterns=[f"{path}/*"], token=os.environ.get("HF_TOKEN"))
os.symlink(os.path.join(d, path), "ckpt")
EOF

step "package for MLC"
python to_mlc.py ckpt pkg | tee -a "$OUT/steps.txt"

step "text-only patch"
python patch_mlc.py | tee -a "$OUT/steps.txt"

step "convert_weight"
mlc_llm convert_weight pkg --quantization q4f16_1 -o "$OUT/$NAME-q4f16_1-MLC" 2>&1 | tail -20

step "gen_config"
mlc_llm gen_config pkg --quantization q4f16_1 --conv-template ${CONV:-gemma4_instruction} --context-window-size 4096 \
  -o "$OUT/$NAME-q4f16_1-MLC" 2>&1 | tail -20

step "fix stop tokens and marker decoding for the pruned vocab"
# gemma4_instruction hard-codes E2B's ids (1 <eos>, 106 <turn|>, 50 <|tool_response>); the pruned vocab moved them.
# The tool and channel markers are made non-special so decoding keeps them in the text (they're still single
# tokens when encoding): Squiggle parses <|tool_call>…<tool_call|> and <|channel>…<channel|> out of the reply.
python - "$OUT/$NAME-q4f16_1-MLC" <<'PY' | tee -a "$OUT/steps.txt"
import json, sys, os
d = sys.argv[1]
tj = json.load(open(os.path.join(d, "tokenizer.json")))
ids = {a["content"]: a["id"] for a in tj["added_tokens"]}
stop = [ids["<eos>"], ids["<turn|>"], ids["<|tool_response>"]]
cfg_path = os.path.join(d, "mlc-chat-config.json")
cfg = json.load(open(cfg_path))
cfg["conv_template"]["stop_token_ids"] = stop
cfg["eos_token_id"] = stop
cfg["bos_token_id"] = ids["<bos>"]
cfg["conv_template"]["system_prefix_token_ids"] = [ids["<bos>"]]
json.dump(cfg, open(cfg_path, "w"), indent=2)
keep = {"<|tool_call>", "<tool_call|>", "<|tool_response>", "<tool_response|>", '<|"|>', "<|channel>", "<channel|>", "<|tool>", "<tool|>"}
for a in tj["added_tokens"]:
    if a["content"] in keep:
        a["special"] = False
json.dump(tj, open(os.path.join(d, "tokenizer.json"), "w"), ensure_ascii=False)
print("stop", stop, "bos", ids["<bos>"], "markers kept in decoded text:", sorted(keep))
PY

step "compile webgpu"
mlc_llm compile "$OUT/$NAME-q4f16_1-MLC/mlc-chat-config.json" --device webgpu -o "$OUT/$NAME-q4f16_1-webgpu.wasm" 2>&1 | tail -30
ls -la "$OUT" "$OUT/$NAME-q4f16_1-MLC" | tee -a "$OUT/steps.txt"

step "upload"
python - <<EOF
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
repo, name, out = os.environ["REPO"], os.environ["NAME"], "$OUT"
api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
api.upload_folder(repo_id=repo, folder_path=f"{out}/{name}-q4f16_1-MLC", path_in_repo=f"{name}-q4f16_1-MLC")
api.upload_file(repo_id=repo, path_or_fileobj=f"{out}/{name}-q4f16_1-webgpu.wasm", path_in_repo=f"{name}-q4f16_1-webgpu.wasm")
print("uploaded", f"https://huggingface.co/{repo}")
EOF
step "done"
