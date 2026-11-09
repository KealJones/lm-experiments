#!/bin/bash
# One job: build the toolchain (toolchain.sh), then convert + compile + upload LFM3 (build_lfm3.sh).
# The toolchain tarball lands in the output folder first, so a later job can reuse it with TOOLCHAIN=<slug>/<job_id>.
set -euo pipefail
OUT=${1:-out}
bash toolchain.sh "$OUT"
TOOLCHAIN=local bash build_lfm3.sh "$OUT"
