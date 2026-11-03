# /// script
# requires-python = ">=3.10"
# dependencies = ["torch", "transformers"]
# ///
"""Chat with the untrained random-weights GPT-2.

Run: uv run experiments/random-weights/chat.py [default|normal1|normal10|uniform] [--seed N]
"""
import argparse

import torch
from transformers import GPT2Config, GPT2LMHeadModel, GPT2TokenizerFast

FILL = {
    "default": None,
    "normal1": lambda p: p.normal_(0, 1.0),
    "normal10": lambda p: p.normal_(0, 10.0),
    "uniform": lambda p: p.uniform_(-1, 1),
}

ap = argparse.ArgumentParser()
ap.add_argument("init", nargs="?", default="default", choices=FILL)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()

torch.manual_seed(args.seed)
tok = GPT2TokenizerFast.from_pretrained("gpt2")
model = GPT2LMHeadModel(GPT2Config(n_layer=2, n_head=2, n_embd=128, n_positions=256)).eval()
if FILL[args.init]:
    with torch.no_grad():
        for p in model.parameters():
            FILL[args.init](p)

print(f"random-weights GPT-2 ({args.init}, seed {args.seed}). Ctrl-D to quit.")
history = ""
while True:
    try:
        msg = input("\nyou> ")
    except EOFError:
        break
    history += f"User: {msg}\nBot:"
    x = tok(history, return_tensors="pt").input_ids[:, -200:]
    with torch.no_grad():
        out = model.generate(x, max_new_tokens=30, do_sample=True, top_k=50, pad_token_id=tok.eos_token_id)
    reply = tok.decode(out[0, x.shape[1]:])
    print(f"bot> {reply.strip()}")
    history += f"{reply}\n"
