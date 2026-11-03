# /// script
# requires-python = ">=3.10"
# dependencies = ["torch", "transformers", "datasets"]
# ///
"""A tiny GPT-2 that never trains: fill the weights with random numbers and see what comes out.

Run: uv run experiments/random-weights/random_weights.py
"""
import math

import torch
from datasets import load_dataset
from transformers import GPT2Config, GPT2LMHeadModel, GPT2TokenizerFast

torch.manual_seed(0)
tok = GPT2TokenizerFast.from_pretrained("gpt2")
V = len(tok)

# About 6.6M parameters, almost all of them the embedding.
config = GPT2Config(n_layer=2, n_head=2, n_embd=128, n_positions=256)


def init_default(m):
    # What transformers does before training: normal(0, 0.02), LayerNorm at 1/0.
    return m


def init_gauss(std):
    def f(m):
        with torch.no_grad():
            for p in m.parameters():
                p.normal_(0, std)
        return m
    return f


def init_uniform(m):
    with torch.no_grad():
        for p in m.parameters():
            p.uniform_(-1, 1)
    return m


INITS = {
    "default (normal 0.02)": init_default,
    "normal 1.0": init_gauss(1.0),
    "normal 10": init_gauss(10.0),
    "uniform -1..1": init_uniform,
}

text = "\n\n".join(load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")["text"])
ids = tok(text, return_tensors="pt").input_ids[0][:256 * 40].view(40, 256)

PROMPTS = ["The cat sat on the", "Once upon a time", "def add(a, b):"]

print(f"vocab {V}, uniform-guess loss ln(V) = {math.log(V):.3f}\n")
for name, init in INITS.items():
    torch.manual_seed(0)
    model = init(GPT2LMHeadModel(config)).eval()
    n = sum(p.numel() for p in model.parameters())
    with torch.no_grad():
        loss = model(ids, labels=ids).loss.item()
        # How many different tokens does it ever predict as top-1?
        top = model(ids).logits.argmax(-1)
        distinct = top.unique().numel()
    print(f"== {name}  ({n/1e6:.1f}M params)")
    print(f"   WikiText-2 loss {loss:.3f}  (ppl {math.exp(min(loss, 700)):.3g})  distinct top-1 tokens {distinct}")
    for p in PROMPTS:
        x = tok(p, return_tensors="pt").input_ids
        torch.manual_seed(1)
        out = model.generate(x, max_new_tokens=20, do_sample=True, top_k=0, pad_token_id=tok.eos_token_id)
        greedy = model.generate(x, max_new_tokens=12, do_sample=False, pad_token_id=tok.eos_token_id)
        print(f"   sample: {tok.decode(out[0])!r}")
        print(f"   greedy: {tok.decode(greedy[0])!r}")
    print()
