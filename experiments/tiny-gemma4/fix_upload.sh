#!/bin/bash
# Fix the special tokens of a GGUF already on the Hub (fix_tokens.py) and upload it under a new name.
#   REPO=kealjones/tiny-gemma4-test SRC=tiny-gemma4-heal3-Q4_0.gguf DST=tiny-gemma4-heal3-v2-Q4_0.gguf bash fix_upload.sh
set -euo pipefail
python - <<PY
import os, shutil, subprocess
from huggingface_hub import hf_hub_download, HfApi
repo, src, dst = os.environ["REPO"], os.environ["SRC"], os.environ["DST"]
shutil.copy(hf_hub_download(repo, src), dst)
subprocess.run(["python", "fix_tokens.py", dst], check=True)
HfApi(token=os.environ["HF_TOKEN"]).upload_file(path_or_fileobj=dst, path_in_repo=dst, repo_id=repo,
    commit_message="Special tokens fixed (fix_tokens.py): turn markers are control tokens, <turn|> ends generation")
print("uploaded", dst, os.path.getsize(dst))
PY
