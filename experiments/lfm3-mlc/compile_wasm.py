"""mlc_llm compile with the host object format chosen by TVM_WASM_OBJ ("bc", the default, or "o").

TVM's wasm32 host code goes to emcc as LLVM bitcode by default (`emcc.create_wasm.object_format`). When the TVM
build's LLVM (Debian 16) is much older than emscripten's clang (24 in emsdk 7.0.0), clang can crash reading that
bitcode; "o" makes TVM's own LLVM emit a wasm32 object file instead, which wasm-ld links as is.
("bc" with emsdk 7.0.0 fails differently: clang 24 refuses the LLVM-16 module's DataLayout, which lacks f128:64.)
The full emcc output is printed on failure (mlc_llm only shows a tail).

  python compile_wasm.py <mlc_llm compile args...>
"""

import os
import sys

from tvm.contrib import emcc

emcc.create_wasm.object_format = os.environ.get("TVM_WASM_OBJ", "bc")
# TVM links with `emcc`, which does not add libc++/libc++abi; its web runtime (wasm_runtime.cc) is C++ and needs
# std::bad_alloc / ostringstream (job lfm3-mlc-5: "undefined symbol: typeinfo for std::bad_alloc ... Try linking
# with 'em++'"). Defaults of create_wasm are (options, cc, libs): keep the same function object, since
# export_library reads `object_format` off it.
emcc.create_wasm.__defaults__ = (None, os.environ.get("TVM_WASM_CC", "em++"), None)
print("compile_wasm: host object format", emcc.create_wasm.object_format, "linker", emcc.create_wasm.__defaults__[1], flush=True)

from mlc_llm.cli import compile as cli  # noqa: E402  pylint: disable=wrong-import-position

try:
    cli.main(sys.argv[1:])
except RuntimeError as e:
    text = str(e)
    print(text[:20000], flush=True)
    raise
