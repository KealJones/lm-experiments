"""Rerun experiments/random-weights on CPU and save everything the demo page shows.

  python3 site/demos/random-weights/record.py [gpt2 qwen3 gemma4]
  (needs torch, transformers>=5, datasets; free, a few minutes on a laptop CPU)

Uses the experiment's own model.py (same architectures, inits and seed) and the same scoring as
random_weights.py: the first 40 x 256 tokens of WikiText-2 test, the same three prompts, 20 sampled tokens
(seed 1) and 12 greedy ones. The only change is that the loss is summed one 256-token row at a time, so
the 262k-vocabulary Gemma 4 fits in memory; the rows are independent sequences, so the number is the same.

Writes into data/:
  recorded.json        per architecture and init: loss, distinct top-1 tokens, the tokens it bets on most,
                       loss on the first row alone, and every sample
  gpt2-tokenizer.json  GPT-2's vocab (by id) and merges, for the in-browser tokenizer
  passage.json         the first 256-token row (ids and text), which the page scores live
"""
import collections
import json
import math
import pathlib
import sys

import torch
from datasets import load_dataset

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "experiments" / "random-weights"))
from model import ARCHS, FILL, build  # noqa: E402

OUT = HERE / "data"
PROMPTS = ["The cat sat on the", "Once upon a time", "def add(a, b):"]
LABELS = {"gpt2": "GPT-2", "qwen3": "Qwen3", "gemma4": "Gemma 4"}


def record(arch, text):
    out = {"label": LABELS[arch], "inits": {}}
    for init in FILL:
        tok, model = build(arch, init)
        V = model.config.vocab_size
        ids = tok(text, return_tensors="pt").input_ids[0][:256 * 40].view(40, 256)
        n = sum(p.numel() for p in model.parameters())
        total, count, first_row = 0.0, 0, None
        top1 = collections.Counter()
        with torch.no_grad():
            for r in range(40):
                logits = model(ids[r:r + 1]).logits.float()[0]
                ce = torch.nn.functional.cross_entropy(logits[:-1], ids[r, 1:], reduction="sum").item()
                total += ce
                count += 255
                if r == 0:
                    first_row = ce / 255
                top1.update(logits.argmax(-1).tolist())
        loss = total / count
        pad = tok.pad_token_id or tok.eos_token_id
        samples = []
        for p in PROMPTS:
            x = tok(p, return_tensors="pt").input_ids
            torch.manual_seed(1)
            s = model.generate(x, max_new_tokens=20, do_sample=True, top_k=0, pad_token_id=pad)
            g = model.generate(x, max_new_tokens=12, do_sample=False, pad_token_id=pad)
            cut = x.shape[1]
            samples.append({
                "prompt": p,
                "sampled": [tok.decode([t]) for t in s[0, cut:].tolist()],
                "greedy": [tok.decode([t]) for t in g[0, cut:].tolist()],
                "sampled_text": tok.decode(s[0], skip_special_tokens=True),
                "greedy_text": tok.decode(g[0], skip_special_tokens=True),
            })
        favourites = [{"token": tok.decode([t]), "share": c / (40 * 256)} for t, c in top1.most_common(8)]
        out["params"] = n
        out["vocab"] = V
        out["inits"][init] = {"loss": loss, "above_blind": loss - math.log(V), "distinct_top1": len(top1),
                              "first_row_loss": first_row, "favourites": favourites, "samples": samples}
        print(f"{arch:7} {init:9} {n / 1e6:5.1f}M  V {V}  loss {loss:9.3f}  ({loss - math.log(V):+9.3f})  "
              f"distinct {len(top1):5}  row0 {first_row:.3f}", flush=True)
    return out


def tokenizer_files():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(ARCHS["gpt2"])
    vocab = tok.get_vocab()
    by_id = [None] * len(vocab)
    for t, i in vocab.items():
        by_id[i] = t
    merges = json.loads(tok.backend_tokenizer.to_str())["model"]["merges"]
    merges = [m if isinstance(m, str) else " ".join(m) for m in merges]
    tests = ["The cat sat on the", "Once upon a time", "def add(a, b):", " = Valkyria Chronicles III = \n",
             "naïve café — 東京 🙂 it's 2,048 tokens!!   ok", "Keal's small-model lab"]
    json.dump({"vocab": by_id, "merges": merges, "tests": [{"text": t, "ids": tok(t).input_ids} for t in tests]},
              open(OUT / "gpt2-tokenizer.json", "w"), separators=(",", ":"), ensure_ascii=False)
    return tok


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    archs = sys.argv[1:] or list(ARCHS)
    text = "\n\n".join(load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")["text"])
    path = OUT / "recorded.json"
    data = json.load(open(path)) if path.exists() else {}
    if "gpt2" in archs:
        tok = tokenizer_files()
        row = tok(text, return_tensors="pt").input_ids[0][:256].tolist()
        json.dump({"ids": row, "text": tok.decode(row)}, open(OUT / "passage.json", "w"), ensure_ascii=False)
    for arch in archs:
        data[arch] = record(arch, text)
        json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)
    for f in sorted(OUT.glob("*.json")):
        print(f.name, f"{f.stat().st_size / 1e6:.2f} MB")
