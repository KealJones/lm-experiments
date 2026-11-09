"""Install the LFM3 architecture into an mlc_llm Python package (a wheel's site-packages copy or a
source checkout's python/mlc_llm): copies lfm3_model.py / lfm3_loader.py into model/lfm3/, the
conversation template into conversation_template/lfm3.py, and patches the three registries
(model/model.py, conversation_template/__init__.py, interface/gen_config.py CONV_TEMPLATES) plus
compile.py's kv_state_kind ("hybrid": KV cache + RNN state). Idempotent.

  python register_lfm3.py [/path/to/site-packages/mlc_llm]     (default: the importable mlc_llm)
"""

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def patch(path, old, new, marker):
    text = open(path).read()
    if marker in text:
        print("already patched:", path)
        return
    assert old in text, f"anchor not found in {path}: {old!r}"
    open(path, "w").write(text.replace(old, new, 1))
    print("patched:", path)


def main():
    if len(sys.argv) > 1:
        site = sys.argv[1]
    else:
        import mlc_llm  # pylint: disable=import-outside-toplevel

        site = os.path.dirname(mlc_llm.__file__)
    print("mlc_llm at", site)

    model_dir = os.path.join(site, "model", "lfm3")
    os.makedirs(model_dir, exist_ok=True)
    open(os.path.join(model_dir, "__init__.py"), "w").close()
    shutil.copy(os.path.join(HERE, "lfm3_model.py"), os.path.join(model_dir, "lfm3_model.py"))
    shutil.copy(os.path.join(HERE, "lfm3_loader.py"), os.path.join(model_dir, "lfm3_loader.py"))
    shutil.copy(os.path.join(HERE, "lfm3_conv.py"), os.path.join(site, "conversation_template", "lfm3.py"))

    # model registry
    patch(
        os.path.join(site, "model", "model.py"),
        "from .qwen3 import qwen3_loader, qwen3_model\n",
        "from .qwen3 import qwen3_loader, qwen3_model\nfrom .lfm3 import lfm3_loader, lfm3_model\n",
        "from .lfm3 import",
    )
    patch(
        os.path.join(site, "model", "model.py"),
        '    "qwen3_5": Model(\n',
        '    "lfm3": Model(\n'
        '        name="lfm3",\n'
        "        model=lfm3_model.Lfm3ForCausalLM,\n"
        "        config=lfm3_model.Lfm3Config,\n"
        "        source={\n"
        '            "huggingface-torch": lfm3_loader.huggingface,\n'
        '            "huggingface-safetensor": lfm3_loader.huggingface,\n'
        "        },\n"
        "        quantize=make_quantization_functions(\n"
        "            lfm3_model.Lfm3ForCausalLM,\n"
        "        ),\n"
        "    ),\n"
        '    "qwen3_5": Model(\n',
        '"lfm3": Model(',
    )

    # conversation template registry
    init = os.path.join(site, "conversation_template", "__init__.py")
    text = open(init).read()
    if "lfm3" not in text:
        new = re.sub(r"(\n\s+)llama,\n", r"\1lfm3,\1llama,\n", text, count=1)
        assert new != text, "could not add lfm3 to conversation_template/__init__.py"
        open(init, "w").write(new)
        print("patched:", init)
    patch(
        os.path.join(site, "interface", "gen_config.py"),
        '    "qwen3_5",\n',
        '    "lfm3",\n    "qwen3_5",\n',
        '"lfm3"',
    )

    # KV state kind: hybrid (PagedKVCache for the attention layers + RNNState for the conv layers)
    patch(
        os.path.join(site, "interface", "compile.py"),
        '    if "qwen3_5" in model_type:\n        return "hybrid"\n',
        '    if "qwen3_5" in model_type:\n        return "hybrid"\n    if "lfm3" in model_type:\n        return "hybrid"\n',
        '"lfm3" in model_type',
    )
    # Without libmlc_llm (a C++ build with Rust tokenizers and xgrammar) `import mlc_llm` dies in
    # serve/data.py registering "mlc.serve.Data"; compile/convert_weight/gen_config don't need serve.
    patch(
        os.path.join(site, "__init__.py"),
        "from . import protocol, serve\nfrom .libinfo import __version__\nfrom .serve import AsyncMLCEngine, MLCEngine\n",
        "from . import protocol\nfrom .libinfo import __version__\n\ntry:\n    from . import serve\n"
        "    from .serve import AsyncMLCEngine, MLCEngine\n"
        "except (ValueError, ImportError, OSError) as _e:  # no libmlc_llm: the compile tools still work\n"
        "    import sys as _sys\n\n    print('mlc_llm: serve not available:', _e, file=_sys.stderr)\n",
        "serve not available",
    )
    # gen_config imports mlc_llm.tokenizers, whose Tokenizer registers the C++ "mlc.Tokenizer" object at
    # import time, and calls its native DetectTokenizerInfo. Without libmlc_llm: a Python port of that
    # detection (cpp/tokenizers/tokenizers.cc) reading tokenizer.json (ByteLevel/ByteFallback decoder,
    # Prepend "▁" normalizer, Strip " " decoder).
    patch(
        os.path.join(site, "interface", "gen_config.py"),
        "from mlc_llm.tokenizers import Tokenizer\n",
        "try:\n    from mlc_llm.tokenizers import Tokenizer\nexcept (ValueError, ImportError, OSError):  # no libmlc_llm\n    Tokenizer = None\n\n\n"
        "def _detect_tokenizer_info_py(path: str) -> dict:\n"
        "    info = {\"token_postproc_method\": \"byte_fallback\", \"prepend_space_in_encode\": False, \"strip_space_in_decode\": False}\n"
        "    tj = Path(path) / \"tokenizer.json\"\n"
        "    if not tj.exists():\n        return info\n"
        "    obj = json.loads(tj.read_text(encoding=\"utf-8\"))\n"
        "    def _walk(node, key):\n"
        "        if not isinstance(node, dict):\n            return []\n"
        "        return node.get(key) or [] if node.get(\"type\") == \"Sequence\" else [node]\n"
        "    for d in _walk(obj.get(\"decoder\"), \"decoders\"):\n"
        "        if d.get(\"type\") == \"ByteLevel\":\n            info[\"token_postproc_method\"] = \"byte_level\"\n"
        "        elif d.get(\"type\") == \"ByteFallback\":\n            info[\"token_postproc_method\"] = \"byte_fallback\"\n"
        "        if d.get(\"type\") == \"Strip\" and d.get(\"content\") == \" \" and d.get(\"start\") == 1 and d.get(\"stop\") == 0:\n"
        "            info[\"strip_space_in_decode\"] = True\n"
        "    for n in _walk(obj.get(\"normalizer\"), \"normalizers\"):\n"
        "        if n.get(\"type\") == \"Prepend\" and n.get(\"prepend\") == \"\\u2581\":\n"
        "            info[\"prepend_space_in_encode\"] = True\n"
        "    return info\n",
        "_detect_tokenizer_info_py",
    )
    patch(
        os.path.join(site, "interface", "gen_config.py"),
        "    mlc_chat_config.tokenizer_info = asdict(Tokenizer.detect_tokenizer_info(str(output)))\n",
        "    mlc_chat_config.tokenizer_info = (\n        asdict(Tokenizer.detect_tokenizer_info(str(output)))\n"
        "        if Tokenizer is not None\n        else _detect_tokenizer_info_py(str(output))\n    )\n",
        "else _detect_tokenizer_info_py",
    )
    print("lfm3 registered")


if __name__ == "__main__":
    main()
