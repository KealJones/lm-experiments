"""Build the lfm3-webllm demo's weight data from the real weights.

  python3 site/demos/lfm3-webllm/build_data.py LFM3-1.7B-QAD-Q4_0.gguf

Reads 256 rows of three weight matrices straight from LiquidAI/LFM3-1.7B's model.safetensors (HTTP range requests,
~3 MB, not the 3.5 GB file) and the same rows from Liquid's quantization-aware-trained LFM3-1.7B-QAD-Q4_0.gguf
(a local copy, 1 GB), then writes data/weights.json:
  - stats: for each matrix, the average rounding error of plain llama.cpp 4-bit (Q4_0), MLC's plain 4-bit (q4f16_1,
    what our first build did), Liquid's trained 4-bit and MLC's 3-bit (q3f16_1), and how many weights the training
    moved to a different level than plain rounding would have used
  - groups: a few groups of 32 weights (the original values, and Liquid's trained levels and scale) for the
    rounding demo, which redoes MLC's rounding in the browser at any bit width
The rounding formulas are MLC's (mlc_llm/quantization/group_quantization.py) and llama.cpp's (quantize_row_q4_0_ref).
"""
import json
import pathlib
import struct
import sys
import urllib.request

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "data"
ST = "https://huggingface.co/LiquidAI/LFM3-1.7B/resolve/main/model.safetensors"
ROWS = 256
MATRICES = [  # (label, safetensors name, gguf name)
    ("Layer 2, attention: queries", "model.layers.2.self_attn.q_proj.weight", "blk.2.attn_q.weight"),
    ("Layer 2, attention: output", "model.layers.2.self_attn.o_proj.weight", "blk.2.attn_output.weight"),
    ("Layer 0, feed-forward: gate", "model.layers.0.feed_forward.w1.weight", "blk.0.ffn_gate.weight"),
]


def get(url, start, end):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def original_rows(name):
    n = struct.unpack("<Q", get(ST, 0, 7))[0]
    header = json.loads(get(ST, 8, 7 + n))
    t = header[name]
    assert t["dtype"] == "BF16"
    cols = t["shape"][1]
    start = 8 + n + t["data_offsets"][0]
    raw = get(ST, start, start + ROWS * cols * 2 - 1)
    u = np.frombuffer(raw, dtype=np.uint16).astype(np.uint32) << 16
    return u.view(np.float32).reshape(ROWS, cols)


def q4_0_rows(t):
    n_in, n_out = int(t.shape[0]), int(t.shape[1])
    raw = np.asarray(t.data).view(np.uint8).reshape(n_out, n_in // 32, 18)[:ROWS]
    d = raw[:, :, :2].copy().view(np.float16).reshape(ROWS, n_in // 32).astype(np.float32)
    qs = raw[:, :, 2:]
    k = np.concatenate([qs & 0x0F, qs >> 4], axis=2).reshape(ROWS, n_in)
    return k, d


def mlc_round(w, group, bits):
    """MLC group quantization: scale = max|w| / max_int in fp16, q = clip(round(w / scale) + max_int, 0, 2 * max_int)."""
    max_int = 2 ** (bits - 1) - 1
    w16 = w.astype(np.float16).astype(np.float32)
    rows, cols = w.shape
    ng = -(-cols // group)
    g = np.pad(w16, ((0, 0), (0, ng * group - cols))).reshape(rows, ng, group)
    s = (np.abs(g).max(axis=2, keepdims=True).astype(np.float16) / np.float16(max_int)).astype(np.float16).astype(np.float32)
    s[s == 0] = 1
    q = np.clip(np.round(g / s + max_int), 0, 2 * max_int)
    return ((q - max_int) * s).reshape(rows, -1)[:, :cols]


def q4_0_round(w):
    """llama.cpp Q4_0: d = (value with the largest magnitude) / -8, k = min(15, int(w / d + 8.5))."""
    g = w.reshape(w.shape[0], -1, 32)
    mx = np.take_along_axis(g, np.abs(g).argmax(axis=2)[..., None], axis=2)
    d = (mx / -8).astype(np.float16).astype(np.float32)
    inv = np.where(d != 0, 1 / np.where(d != 0, d, 1), 0)
    k = np.clip((g * inv + 8.5).astype(np.int64), 0, 15)
    return ((k - 8) * d).reshape(w.shape), k.reshape(w.shape), d.reshape(w.shape[0], -1)


def main(gguf_path):
    from gguf import GGUFReader
    tensors = {t.name: t for t in GGUFReader(gguf_path).tensors}
    stats, groups = [], []
    for label, st_name, gg_name in MATRICES:
        o = original_rows(st_name)
        k, d = q4_0_rows(tensors[gg_name])
        qad = ((k.astype(np.float32) - 8).reshape(ROWS, -1, 32) * d[:, :, None]).reshape(ROWS, -1)
        plain_q40, k_plain, d_plain = q4_0_round(o)
        m = np.abs(o).mean()
        err = lambda x: float(np.abs(x - o).mean() / m)
        stats.append({
            "matrix": label, "shape": f"{ROWS} of {tensors[gg_name].shape[1]} rows x {o.shape[1]}",
            "q4_0_plain": err(plain_q40), "mlc4_plain": err(mlc_round(o, 32, 4)), "qad": err(qad),
            "mlc3_plain": err(mlc_round(o, 40, 3)), "moved": float(np.mean(k != k_plain)),
            "new_scale": float(np.mean(~np.isclose(d, d_plain))),
        })
        # groups for the rounding demo: same scale as plain rounding (so the moved weights are the training's nudges,
        # not a different grid), the two with the most nudges and a typical one, plus one where the scale changed
        moved = (k != k_plain).reshape(ROWS, -1, 32).sum(axis=2)
        same = np.isclose(d, d_plain)
        cand = np.where(same.ravel() & (moved.ravel() > 0))[0]
        by_moved = cand[np.argsort(-moved.ravel()[cand], kind="stable")]
        typical = cand[np.argsort(np.abs(moved.ravel()[cand] - np.median(moved.ravel()[cand])), kind="stable")]
        rescaled = np.where(~same.ravel())[0]
        picks = [int(by_moved[0]), int(typical[0]), int(rescaled[0])]
        for p in picks:
            r, gi = divmod(int(p), moved.shape[1])
            sl = slice(gi * 32, gi * 32 + 32)
            groups.append({
                "matrix": label, "row": r, "cols": [gi * 32, gi * 32 + 31],
                "w": [float(f"{x:.6g}") for x in o[r, sl]],
                "qad_k": [int(x) for x in k[r, sl]], "qad_d": float(d[r, gi]),
                "plain_k": [int(x) for x in k_plain[r, sl]],
                "moved": int(moved[r, gi]), "plain_d": float(d_plain[r, gi]), "same_scale": bool(same[r, gi]),
            })
    OUT.mkdir(exist_ok=True)
    (OUT / "weights.json").write_text(json.dumps({"stats": stats, "groups": groups}, indent=1))
    for s in stats:
        print(f"{s['matrix']}: Q4_0 {s['q4_0_plain']:.1%}  MLC 4-bit {s['mlc4_plain']:.1%}  QAD {s['qad']:.1%}  "
              f"MLC 3-bit {s['mlc3_plain']:.1%}  moved {s['moved']:.1%}  new scale {s['new_scale']:.1%}")
    print(f"{len(groups)} groups -> {OUT / 'weights.json'}")


if __name__ == "__main__":
    main(sys.argv[1])
