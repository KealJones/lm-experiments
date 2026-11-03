"""Build a tiny, untrained model in a real model's architecture, with that model's tokenizer."""
import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

# Each arch copies the real model's config, then shrinks it to 2 layers at width 128.
ARCHS = {
    "gpt2": "openai-community/gpt2",
    "qwen3": "Qwen/Qwen3-0.6B",
    "gemma4": "google/gemma-4-E2B-it",
}
SMALL = dict(hidden_size=128, intermediate_size=512, num_hidden_layers=2,
             num_attention_heads=2, num_key_value_heads=1, head_dim=64)

FILL = {
    "default": None,  # the architecture's own init, normal(0, 0.02) for all three
    "normal1": lambda p: p.normal_(0, 1.0),
    "normal10": lambda p: p.normal_(0, 10.0),
    "uniform": lambda p: p.uniform_(-1, 1),
}


def build(arch="gpt2", init="default", seed=0):
    repo = ARCHS[arch]
    tok = AutoTokenizer.from_pretrained(repo)
    cfg = AutoConfig.from_pretrained(repo)
    cfg = getattr(cfg, "text_config", cfg)
    if arch == "gpt2":
        cfg.update(dict(n_layer=2, n_head=2, n_embd=128, n_positions=256))
    else:
        cfg.update(SMALL)
        cfg.layer_types = cfg.layer_types[-2:]  # keep one sliding + one full layer for Gemma 4
        if arch == "gemma4":
            # Gemma 4's per-layer embedding is vocab x layers x this; 256 would be 134M params.
            cfg.update(dict(hidden_size_per_layer_input=16, num_kv_shared_layers=0))
    torch.manual_seed(seed)
    model = AutoModelForCausalLM.from_config(cfg).eval()
    if FILL[init]:
        with torch.no_grad():
            for p in model.parameters():
                FILL[init](p)
    return tok, model
