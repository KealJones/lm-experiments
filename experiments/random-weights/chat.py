# /// script
# requires-python = ">=3.10"
# dependencies = ["torch", "transformers>=5"]
# ///
"""Chat with an untrained random-weights model.

Run: uv run experiments/random-weights/chat.py [gpt2|qwen3|gemma4] [default|normal1|normal10|uniform] [--seed N]
"""
import argparse

import torch

from model import ARCHS, FILL, build

ap = argparse.ArgumentParser()
ap.add_argument("arch", nargs="?", default="gpt2", choices=ARCHS)
ap.add_argument("init", nargs="?", default="default", choices=FILL)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()

tok, model = build(args.arch, args.init, args.seed)
pad = tok.pad_token_id or tok.eos_token_id


def prompt(history):
    # Qwen3 and Gemma 4 have chat templates; GPT-2 gets a plain transcript.
    if tok.chat_template:
        return tok.apply_chat_template(history, add_generation_prompt=True, return_tensors="pt", return_dict=True).input_ids
    text = "".join(f"{'User' if m['role'] == 'user' else 'Bot'}: {m['content']}\n" for m in history) + "Bot:"
    return tok(text, return_tensors="pt").input_ids


print(f"random-weights {args.arch} ({args.init}, seed {args.seed}). Ctrl-D to quit.")
history = []
while True:
    try:
        msg = input("\nyou> ")
    except EOFError:
        break
    history.append({"role": "user", "content": msg})
    x = prompt(history)[:, -200:]
    with torch.no_grad():
        out = model.generate(x, max_new_tokens=30, do_sample=True, top_k=50, pad_token_id=pad)
    reply = tok.decode(out[0, x.shape[1]:], skip_special_tokens=True).strip()
    print(f"bot> {reply}")
    history.append({"role": "assistant", "content": reply})
