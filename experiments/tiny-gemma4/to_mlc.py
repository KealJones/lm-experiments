"""Package a healed tiny-Gemma-4 checkpoint (heal.py's ckpt/: Gemma4TextModel + pruned tokenizer.json) the way
MLC-LLM's gemma4 loader expects a Hugging Face checkpoint, so `mlc_llm convert_weight` can read it:
  - weights renamed to model.language_model.* (MLC maps the conditional-generation layout; tied lm_head)
  - config nested as text_config under model_type "gemma4", architectures Gemma4ForConditionalGeneration,
    with "text_only": true for patch_mlc.py (tiny Gemma has no audio or vision weights)
  - FFN padded with zero channels to a multiple of 32 (2580 -> 2592) so 4-bit groups of 32 divide every
    linear; a zero gate/up row feeds a zero into a zero down column, so outputs are identical (as to_gguf.py)
  - tokenizer files rebuilt around the pruned tokenizer.json with E2B-it's special tokens and chat template

    python to_mlc.py CKPT_DIR OUT_DIR [BASE_MODEL]

DRAFT (2026-11-02): written against mlc-llm's python/mlc_llm/model/gemma4 at commit 44fd06d; not run yet.
"""
import json, os, shutil, sys

ckpt, out = sys.argv[1], sys.argv[2]
base = sys.argv[3] if len(sys.argv) > 3 else "google/gemma-4-E2B-it"
os.makedirs(out, exist_ok=True)

import torch
from safetensors.torch import load_file, save_file
sd = load_file(os.path.join(ckpt, "model.safetensors"))
text = json.load(open(os.path.join(ckpt, "config.json")))

I = text["intermediate_size"]
Ip = -(-I // 32) * 32
if Ip != I:
    for k in list(sd):
        w = sd[k]
        if k.endswith(("mlp.gate_proj.weight", "mlp.up_proj.weight")) and w.shape[0] % 32:
            sd[k] = torch.cat([w, w.new_zeros(-(-w.shape[0] // 32) * 32 - w.shape[0], w.shape[1])], 0)
        elif k.endswith("mlp.down_proj.weight") and w.shape[1] % 32:
            sd[k] = torch.cat([w, w.new_zeros(w.shape[0], -(-w.shape[1] // 32) * 32 - w.shape[1])], 1)
    text["intermediate_size"] = Ip
    print("FFN padded", I, "->", Ip)

def rename(k):
    k = k[len("model."):] if k.startswith("model.") else k
    return "model.language_model." + k
save_file({rename(k): v.contiguous() for k, v in sd.items()}, os.path.join(out, "model.safetensors"), metadata={"format": "pt"})

text["model_type"] = "gemma4_text"
text.pop("architectures", None)
cfg = {
    "architectures": ["Gemma4ForConditionalGeneration"],
    "model_type": "gemma4",
    "text_config": text,
    "text_only": True,
    "tie_word_embeddings": True,
}
json.dump(cfg, open(os.path.join(out, "config.json"), "w"), indent=1)

from transformers import AutoTokenizer, PreTrainedTokenizerFast
from tokenizers import Tokenizer
src = AutoTokenizer.from_pretrained(base)
t = PreTrainedTokenizerFast(tokenizer_object=Tokenizer.from_file(os.path.join(ckpt, "tokenizer.json")),
                            bos_token=src.bos_token, eos_token=src.eos_token, pad_token=src.pad_token, unk_token=src.unk_token)
t.chat_template = src.chat_template
t.save_pretrained(out)
try:
    from huggingface_hub import hf_hub_download
    shutil.copy(hf_hub_download(base, "generation_config.json"), os.path.join(out, "generation_config.json"))
except Exception:
    pass
print("packaged", out, {k: text.get(k) for k in ("hidden_size", "num_hidden_layers", "num_kv_shared_layers", "intermediate_size", "vocab_size")})
