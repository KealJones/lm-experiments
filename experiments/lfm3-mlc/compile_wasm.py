"""mlc_llm compile with the host object format chosen by TVM_WASM_OBJ ("bc", the default, or "o").

TVM's wasm32 host code goes to emcc as LLVM bitcode by default (`emcc.create_wasm.object_format`). When the TVM
build's LLVM (Debian 16) is much older than emscripten's clang (24 in emsdk 7.0.0), clang can crash reading that
bitcode; "o" makes TVM's own LLVM emit a wasm32 object file instead, which wasm-ld links as is.
The full emcc output is printed on failure (mlc_llm only shows a tail).

  python compile_wasm.py <mlc_llm compile args...>
"""

import os
import sys

from tvm.contrib import emcc

emcc.create_wasm.object_format = os.environ.get("TVM_WASM_OBJ", "bc")
print("compile_wasm: host object format", emcc.create_wasm.object_format, flush=True)

from mlc_llm.cli import compile as cli  # noqa: E402  pylint: disable=wrong-import-position

try:
    cli.main(sys.argv[1:])
except RuntimeError as e:
    text = str(e)
    print(text[:20000], flush=True)
    raise
