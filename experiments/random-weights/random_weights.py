# /// script
# requires-python = ">=3.10"
# dependencies = ["torch", "transformers>=5", "datasets"]
# ///
"""Tiny models that never train: fill the weights with random numbers and see what comes out.

Run: uv run experiments/random-weights/random_weights.py [gpt2 qwen3 gemma4]
"""
import math
import sys

import torch
from datasets import load_dataset

from model import ARCHS, FILL, build

archs = sys.argv[1:] or list(ARCHS)
text = "\n\n".join(load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")["text"])
PROMPTS = ["The cat sat on the", "Once upon a time", "def add(a, b):"]

for arch in archs:
    for init in FILL:
        tok, model = build(arch, init)
        V = model.config.vocab_size
        ids = tok(text, return_tensors="pt").input_ids[0][:256 * 40].view(40, 256)
        n = sum(p.numel() for p in model.parameters())
        with torch.no_grad():
            logits = model(ids).logits.float()
            loss = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, V), ids[:, 1:].reshape(-1)).item()
            # How many different tokens does it ever predict as top-1?
            distinct = logits.argmax(-1).unique().numel()
        print(f"== {arch} / {init}  ({n/1e6:.1f}M params, vocab {V}, ln(V) {math.log(V):.3f})")
        print(f"   WikiText-2 loss {loss:.3f}  (vs ln(V) {loss - math.log(V):+.3f})  distinct top-1 tokens {distinct}")
        pad = tok.pad_token_id or tok.eos_token_id
        for p in PROMPTS:
            x = tok(p, return_tensors="pt").input_ids
            torch.manual_seed(1)
            out = model.generate(x, max_new_tokens=20, do_sample=True, top_k=0, pad_token_id=pad)
            greedy = model.generate(x, max_new_tokens=12, do_sample=False, pad_token_id=pad)
            print(f"   sample: {tok.decode(out[0], skip_special_tokens=True)!r}")
            print(f"   greedy: {tok.decode(greedy[0], skip_special_tokens=True)!r}")
        print(flush=True)
