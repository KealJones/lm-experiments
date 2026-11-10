"""Put Liquid's quantization-aware-trained 4-bit LFM3 weights (LFM3-1.7B-QAD-Q4_0.gguf) into our MLC q4f16_1 or
q4f32_1 build, exactly, without rounding them again. (q4f32_1 packs the same way with fp32 scales, for GPUs without
16-bit floats; the GGUF's fp16 scales widen to fp32 exactly.)

Both formats keep 4-bit integers with one fp16 scale per 32 inputs, so the values map one to one:
  GGUF Q4_0   w = (k - 8) * d      k in 0..15 (low nibbles = inputs 0..15 of the block, high = 16..31)
  MLC q4f16_1 w = (q - 7) * s      q in 0..15, element i of a uint32 at bits 4*i (group_quantization.py)
With q = 15 - k and s = -d:  (15 - k - 7) * (-d) = (k - 8) * d.  MLC's dequantize doesn't clip q (its quantizer
only ever writes 0..14), and a negative scale is just a number, so every weight comes out bit-for-bit as the GGUF's.

Only the Q4_0 linear layers are replaced (attention q/k/v, output, gate; conv in/out; FFN gate/up/down). Everything
else stays as in the template build: the embedding (Q6_K in the GGUF, not QAD), norms and conv kernels (full
precision in both). The template is the existing q4f16_1 build, so names, shapes, shards and offsets stay the same
and the same .wasm runs it.

usage: python -I qad_to_mlc.py TEMPLATE_DIR GGUF OUT_DIR       (TEMPLATE_DIR = kealjones/LFM3-1.7B-q4f16_1-MLC or -q4f32_1-MLC)
       python -I qad_to_mlc.py --check TEMPLATE_DIR GGUF SHARD...  (compare only, no output)
"""
import hashlib
import json
import os
import shutil
import sys

import numpy as np
from gguf import GGUFReader


def q4_0_parts(t):
    """A Q4_0 GGUF tensor -> (k uint8 [out, in], d float16 [out, in/32])."""
    n_in, n_out = int(t.shape[0]), int(t.shape[1])
    raw = np.asarray(t.data).view(np.uint8).reshape(n_out, n_in // 32, 18)
    d = raw[:, :, :2].copy().view(np.float16).reshape(n_out, n_in // 32)
    qs = raw[:, :, 2:]
    k = np.concatenate([qs & 0x0F, qs >> 4], axis=2).reshape(n_out, n_in)
    return k, d


def dequant_gguf(k, d):
    return (k.astype(np.float32) - 8).reshape(k.shape[0], -1, 32) * d.astype(np.float32)[:, :, None]


def bf16_on_disk(r):
    """A float32 record tagged "f32-to-bf16" sits on disk as bf16 bits (the tag also appears on uint32 q_weight
    records, which stay raw)."""
    return r.get('format') == 'f32-to-bf16' and r['dtype'] == 'float32'


def to_bf16_bits(x):
    """float32 -> bf16 bits (uint16), round to nearest even: how MLC stores an "f32-to-bf16" record on disk."""
    b = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    return ((b + np.uint32(0x7FFF) + ((b >> np.uint32(16)) & np.uint32(1))) >> np.uint32(16)).astype(np.uint16)


def from_bf16_bits(u):
    return (u.astype(np.uint32) << np.uint32(16)).view(np.float32)


def to_mlc(k, d, rec=None):
    """q4f16_1 keeps the scales in fp16. q4f32_1 packs the same way but its fp32 scales sit on disk as bf16
    (record format "f32-to-bf16", widened to fp32 when WebLLM loads them), so there the GGUF's fp16 scales round to
    bf16: up to ~0.4% per scale, next to 4-bit rounding's ~10%. The weights' 4-bit integers stay exact either way."""
    q = (15 - k.astype(np.uint32)).reshape(k.shape[0], -1, 8)
    packed = np.zeros(q.shape[:2], dtype=np.uint32)
    for i in range(8):
        packed |= q[:, :, i] << np.uint32(4 * i)
    s = (-d).astype(np.float32)
    if rec and bf16_on_disk(rec):
        return packed, to_bf16_bits(s)
    return packed, s.astype(np.dtype(rec['dtype']) if rec else np.float16)


def dequant_mlc(qw, qs):
    if qs.dtype == np.uint16:   # bf16 bits (an "f32-to-bf16" record)
        qs = from_bf16_bits(qs)
    q = np.stack([(qw >> np.uint32(4 * i)) & np.uint32(0xF) for i in range(8)], axis=2).reshape(qw.shape[0], -1)
    return (q.astype(np.float32) - 7).reshape(qw.shape[0], -1, 32) * qs.astype(np.float32)[:, :, None]


def sources(mlc_base):
    """MLC tensor (without .q_weight/.q_scale) -> GGUF tensors whose rows it concatenates, or None."""
    parts = mlc_base.split('.')
    if parts[0] != 'model' or parts[1] != 'layers':
        return None
    i, rest = parts[2], '.'.join(parts[3:])
    return {
        'self_attn.c_attn': [f'blk.{i}.attn_q.weight', f'blk.{i}.attn_k.weight', f'blk.{i}.attn_v.weight'],
        'self_attn.o_proj': [f'blk.{i}.attn_output.weight'],
        'self_attn.gate_proj': [f'blk.{i}.attn_gate.weight'],
        'feed_forward.gate_up_proj': [f'blk.{i}.ffn_gate.weight', f'blk.{i}.ffn_up.weight'],
        'feed_forward.down_proj': [f'blk.{i}.ffn_down.weight'],
        'conv.in_proj': [f'blk.{i}.shortconv.in_proj.weight'],
        'conv.out_proj': [f'blk.{i}.shortconv.out_proj.weight'],
    }.get(rest)


def load_gguf(path):
    r = GGUFReader(path)
    return {t.name: t for t in r.tensors}


def qad_tensor(gg, names):
    ks, ds = [], []
    for n in names:
        t = gg[n]
        assert t.tensor_type.name == 'Q4_0', (n, t.tensor_type.name)
        k, d = q4_0_parts(t)
        ks.append(k)
        ds.append(d)
    return np.concatenate(ks, axis=0), np.concatenate(ds, axis=0)


def all_records(cache):
    """name -> (shard, record) across every shard (a tensor's q_weight and q_scale can sit in different shards)."""
    return {r['name']: (s, r) for s in cache['records'] for r in s['records']}


def read_rec(buf, r):
    dt = np.uint16 if bf16_on_disk(r) else np.dtype(r['dtype'])
    a = np.frombuffer(buf, dtype=dt, count=int(np.prod(r['shape'])), offset=r['byteOffset'])
    return a.reshape(r['shape'])


def plan(cache, gg, only=None):
    """[(base, q_weight record + shard, q_scale record + shard, new q_weight, new q_scale)] for every QAD layer."""
    recs = all_records(cache)
    out = []
    for name, (shard, r) in recs.items():
        if not name.endswith('.q_weight'):
            continue
        base = name[:-len('.q_weight')]
        src = sources(base)
        if src is None:
            continue
        ss, rs = recs[base + '.q_scale']
        if only is not None and shard['dataPath'] not in only and ss['dataPath'] not in only:
            continue
        k, d = qad_tensor(gg, src)
        qw, qs = to_mlc(k, d, rs)   # the template record's own dtype and on-disk format (fp16, or fp32 stored as bf16)
        assert list(qw.shape) == r['shape'] and list(qs.shape) == rs['shape'], (name, qw.shape, qs.shape)
        assert qw.nbytes == r['nbytes'] and qs.nbytes == rs['nbytes'], name
        out.append((base, (shard, r), (ss, rs), qw, qs, k, d))
    return out


def check(template, gguf_path, shards):
    cache = json.load(open(os.path.join(template, 'tensor-cache.json')))
    gg = load_gguf(gguf_path)
    bufs = {}
    def buf(sh):
        if sh['dataPath'] not in bufs:
            bufs[sh['dataPath']] = open(os.path.join(template, sh['dataPath']), 'rb').read()
        return bufs[sh['dataPath']]
    for base, (sw, rw), (ss, rs), qw, qs, k, d in plan(cache, gg, shards):
        if sw['dataPath'] not in shards or ss['dataPath'] not in shards:
            print(f'{base}: split across a shard not downloaded, skipped')
            continue
        ref = dequant_gguf(k, d)
        mine = dequant_mlc(qw, qs)
        # Bit-exact into fp16 scales; into bf16 ones (q4f32_1), each weight within bf16's rounding of its scale.
        exact = np.array_equal(mine, ref) if qs.dtype != np.uint16 else bool(np.all(np.abs(mine - ref) <= np.abs(ref) * 2.0 ** -8 + 1e-12))
        ours = dequant_mlc(read_rec(buf(sw), rw), read_rec(buf(ss), rs))
        corr = np.corrcoef(ours.ravel(), ref.ravel())[0, 1]
        rel = np.abs(ours - ref).mean() / np.abs(ref).mean()
        print(f'{base}: {qw.shape}  QAD round trip {"exact" if qs.dtype != np.uint16 else "within bf16"}: {exact}  vs our old build: corr {corr:.4f}, mean diff {rel:.1%}')
        assert exact and corr > 0.98, base


def convert(template, gguf_path, out):
    os.makedirs(out, exist_ok=True)
    cache = json.load(open(os.path.join(template, 'tensor-cache.json')))
    gg = load_gguf(gguf_path)
    edits = {}
    jobs = plan(cache, gg)
    for base, (sw, rw), (ss, rs), qw, qs, k, d in jobs:
        edits.setdefault(sw['dataPath'], []).append((rw, qw.tobytes()))
        edits.setdefault(ss['dataPath'], []).append((rs, qs.tobytes()))
    for shard in cache['records']:
        buf = bytearray(open(os.path.join(template, shard['dataPath']), 'rb').read())
        for r, b in edits.get(shard['dataPath'], []):
            assert len(b) == r['nbytes']
            buf[r['byteOffset']:r['byteOffset'] + r['nbytes']] = b
        shard['md5sum'] = hashlib.md5(buf).hexdigest()
        with open(os.path.join(out, shard['dataPath']), 'wb') as f:
            f.write(buf)
    json.dump(cache, open(os.path.join(out, 'tensor-cache.json'), 'w'))
    for f in os.listdir(template):
        if not f.startswith('params_shard_') and f != 'tensor-cache.json' and os.path.isfile(os.path.join(template, f)):
            shutil.copy(os.path.join(template, f), os.path.join(out, f))
    print(f'replaced {len(jobs)} linear layers with QAD weights; wrote {out}')
    return len(jobs)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--check':
        check(a[1], a[2], set(a[3:]))
    else:
        n = convert(a[0], a[1], a[2])
        assert n == 13 * 4 + 11 * 5, n   # conv layers: in, out, gate_up, down; attention: c_attn, o, gate, gate_up, down
