# source this with TC=/path/to/unpacked/toolchain
export TVM_HOME="$TC/tvm" TVM_SOURCE_DIR="$TC/tvm" MLC_LLM_SOURCE_DIR="$TC/mlc-llm"
export TVM_LIBRARY_PATH="$TC/tvm/build/lib" TVM_TIRX_LIBRARY_PATH="$TC/tvm/build/lib"
export PYTHONPATH="$TC/mlc-llm/python:$TC/tvm/python:$TC/tvm/3rdparty/tvm-tirx/python:${PYTHONPATH:-}"
export SKIP_LOADING_MLCLLM_SO=1
