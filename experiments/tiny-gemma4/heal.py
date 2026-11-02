"""Tiny Gemma 4, stage 2: cut Gemma 4 E2B-it (surgery.py) and heal it by distillation from the uncut model.

The student learns to match the teacher's next-token distribution (KL over the kept vocab) on streamed
FineWeb-Edu, code and Squiggle-harness text written by Gemma 4. No labels, no Claude-written data.

Checkpoints (student weights + config + pruned tokenizer) are written to OUT/ckpt every CKPT_MIN minutes,
so a job that dies or hits its limit still leaves a usable model. Held-out bits per byte is logged to
OUT/metrics.jsonl as it trains.

    python heal.py OUT_DIR    env: MODEL, KEEP_LAYERS or SKIP, FFN, KEPT_IDS, TOKENIZER, MINUTES, LR, BATCH, SEQ

Heal 4 additions (prep_tools.py): a "toucan" source (multi-turn tool conversations with real results), the old
E2B answers re-filtered, and MASK=1: chat-format sources are trained only on what the model writes (not the
system prompt, tool declarations, user turns or tool results); plain text (web, code, maths) is trained everywhere.
"""
import gzip, json, math, os, random, sys, time
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from surgery import cut  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
MODEL = os.environ.get("MODEL", "google/gemma-4-E2B-it")
FFN = float(os.environ.get("FFN", 0.66))
MINUTES = float(os.environ.get("MINUTES", 60))           # training time; checkpoint + eval at the end
CKPT_MIN = float(os.environ.get("CKPT_MIN", 40))
LR = float(os.environ.get("LR", 2e-4))
BATCH = int(os.environ.get("BATCH", 8))
SEQ = int(os.environ.get("SEQ", 1024))
EVAL_EVERY = int(os.environ.get("EVAL_EVERY", 400))
MIX = json.loads(os.environ.get("MIX", '{"web": 0.85, "code": 0.10, "agent": 0.05}'))
CE_W = float(os.environ.get("CE_W", 0.0))                  # plain next-token loss weight (0 = distillation only)
CE_SRC = json.loads(os.environ.get("CE_SRC", "{}"))        # per-source next-token weight, e.g. {"toucan": 1.0}: learn the
                                                           # data's own answers there, distillation everywhere
PACK_CONVS = os.environ.get("PACK_CONVS", "1") == "1"      # whole conversations share a row while they fit
CKPT_KEEP = int(os.environ.get("CKPT_KEEP", 2))            # also keep this many dated checkpoints (ckpt-step<N>)
HIDDEN = int(os.environ.get("HIDDEN", 0))                   # keep this many hidden dims (0 = all)
RESUME = os.environ.get("RESUME", "")
GEN = os.environ.get("GEN", "")                            # "repo_id:path/gen.jsonl.gz": E2B's own answers (gen.py)                      # "repo_id:path/to/ckpt" in a dataset repo: continue from it
AGENT_FILE = os.environ.get("AGENT_FILE", "teacher_results.jsonl.gz")
MASK = os.environ.get("MASK", "0") == "1"                  # train chat sources only on the model's own tokens
TOOL_EVAL = int(os.environ.get("TOOL_EVAL", 120))           # held-out Toucan conversations for tools_replies bpb
DEV = "cuda" if torch.cuda.is_available() else "cpu"
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:6.1f} min]", *a, flush=True)


def load_json(path_env, default):
    p = os.environ.get(path_env, default)
    return json.load(open(p)) if p and os.path.exists(p) else None


# ── Data ─────────────────────────────────────────────────────────────────────

def web_stream(skip):
    from datasets import load_dataset
    ds = load_dataset("HuggingFaceFW/fineweb-edu", "sample-10BT", split="train", streaming=True)
    for i, r in enumerate(ds):
        if i >= skip and r["text"].strip():
            yield r["text"]


def chat_stream(template):
    """OpenAssistant (oasst1, human-written, Apache-2.0) English prompt/reply pairs in Gemma's chat format.
    Distillation only uses them as contexts: the targets are the teacher's own predictions on the reply."""
    from datasets import load_dataset
    rows = [r for r in load_dataset("OpenAssistant/oasst1", split="train") if r["lang"] == "en" and not r["synthetic"] and not r["deleted"]]
    by_id = {r["message_id"]: r for r in rows}
    pairs = []
    for r in rows:
        if r["role"] == "assistant" and r["parent_id"] in by_id and by_id[r["parent_id"]]["role"] == "prompter":
            pairs.append(chat_item(template(by_id[r["parent_id"]]["text"], r["text"])))
    random.Random(2).shuffle(pairs)
    log(f"chat pairs: {len(pairs)}")
    while True:
        for p in pairs:
            yield p


def smoltalk_stream(tok):
    """SmolTalk (Apache-2.0) multi-turn conversations in Gemma's chat format: contexts for distillation."""
    from datasets import load_dataset
    while True:
        for r in load_dataset("HuggingFaceTB/smoltalk", "all", split="train", streaming=True).shuffle(seed=3, buffer_size=2000):
            msgs = [m for m in r["messages"] if m.get("role") in ("user", "assistant", "system") and m.get("content")]
            if len(msgs) < 2:
                continue
            try:
                yield chat_item(tok.apply_chat_template(msgs, tokenize=False).removeprefix(tok.bos_token))
            except Exception:
                continue


def math_stream():
    """FineMath 4+ (ODC-By): maths and step-by-step reasoning text."""
    from datasets import load_dataset
    while True:
        for r in load_dataset("HuggingFaceTB/finemath", "finemath-4plus", split="train", streaming=True):
            if r["text"].strip():
                yield r["text"]


def gen_texts(tools=None):
    """On-policy conversations from gen.py: questions from Hermes/SmolTalk, answers written by E2B itself.
    tools=True: only the Hermes ones (E2B's native tool calls), False: everything else, None: all."""
    from huggingface_hub import hf_hub_download
    rows = []
    for g in GEN.split(","):                                   # several runs: "repo:a.jsonl.gz,repo:b.jsonl.gz"
        repo, path = g.strip().split(":", 1)
        f = hf_hub_download(repo, path, repo_type="dataset", token=os.environ.get("HF_TOKEN"))
        rows += [json.loads(l) for l in gzip.open(f, "rt")]
    if tools is not None:
        rows = [r for r in rows if (r.get("source") == "hermes") == tools]
    if MASK:                                                   # heal 4: drop prose "calls" and question menus (prep_tools.keep_gen)
        from prep_tools import keep_gen
        why = {}
        rows = [r for r in rows if keep_gen(r, why)]
        log("on-policy filter dropped", why)
    random.Random(4).shuffle(rows)
    log(f"on-policy conversations{'' if tools is None else (' with tools' if tools else ' without tools')}: {len(rows)}")
    return [chat_item(r["text"]) for r in rows]


def chat_item(text):
    """A chat-format text as a training item: masked segments when MASK, else the plain text."""
    if not MASK:
        return text
    from prep_tools import segments
    return segments(text)


def math_stream():
    """FineMath 4+ (ODC-By): maths and step-by-step reasoning text."""
    from datasets import load_dataset
    while True:
        for r in load_dataset("HuggingFaceTB/finemath", "finemath-4plus", split="train", streaming=True):
            if r["text"].strip():
                yield r["text"]


def code_stream():
    from datasets import load_dataset
    while True:
        for r in load_dataset("codeparrot/codeparrot-clean-valid", split="train", streaming=True):
            if r["content"].strip():
                yield r["content"]


def agent_texts(held=20):
    """Teacher episodes split by EPISODE (calls in one episode share long prompts). Returns (held-out replies,
    training texts). Held-out text is Gemma's replies only, so shared harness prompts can't be memorised."""
    eps = []
    if os.path.exists(AGENT_FILE):
        eps = [json.loads(l) for l in gzip.open(AGENT_FILE, "rt")]
    random.Random(0).shuffle(eps)
    held_replies = [str(c.get("output") or "") for e in eps[:held] for c in e.get("calls") or [] if len(str(c.get("output") or "")) > 80]
    train = []
    for e in eps[held:]:
        for c in e.get("calls") or []:
            t = "\n\n".join(str(m.get("content", "")) for m in c.get("messages") or [] if m.get("content")) + "\n\n" + str(c.get("output") or "")
            if len(t) > 200:
                train.append(t)
    random.Random(1).shuffle(train)
    return held_replies, train


class Packer:
    """Mixes sources by weight into SEQ-long rows of (ids, trained mask, CE weight per target).

    Plain text (web, code, maths) streams through rows split anywhere, documents separated by BOS. Chat records
    ([(text, train)] from prep_tools.segments) are never split across rows: whole conversations are packed into a
    row while they fit (PACK_CONVS=1) or one per row (PACK_CONVS=0), and the rest of the row is padding, masked.
    A split conversation would train its later answers without the turns they answer (heal 4 review)."""
    def __init__(self, encode, bos, sources, pad=0):
        self.encode, self.bos, self.sources, self.pad = encode, bos, sources, pad
        self.buf, self.mbuf, self.cbuf = [], [], []             # plain stream: ids, trained, CE weight
        self.conv = None                                        # conversation row being filled
        self.ready = []
        self.rng = random.Random(1)
        self.rows = {"plain": 0, "conv": 0, "pad_tokens": 0, "conv_cut": 0}

    def _finish(self, ids, m, c):
        n = SEQ + 1 - len(ids)
        self.rows["conv"] += 1; self.rows["pad_tokens"] += n
        self.ready.append((ids + [self.pad] * n, (m + [0] * n)[1:], (c + [0.0] * n)[1:]))

    def add(self, item, ce_w):
        if isinstance(item, str):
            ids = self.encode(item[:20000])
            self.buf += [self.bos] + ids; self.mbuf += [0] + [1] * len(ids); self.cbuf += [0.0] + [ce_w] * len(ids)
            return
        ids, m = [self.bos], [0]
        for text, train in item:
            e = self.encode(text); ids += e; m += [int(train)] * len(e)
        if len(ids) > SEQ + 1:                                  # prep keeps conversations under SEQ; cut the end if not
            ids, m = ids[:SEQ + 1], m[:SEQ + 1]; self.rows["conv_cut"] += 1
        c = [ce_w * x for x in m]
        if PACK_CONVS and self.conv and len(self.conv[0]) + len(ids) <= SEQ + 1:
            for a, b in zip(self.conv, (ids, m, c)):
                a += b
            return
        if self.conv:
            self._finish(*self.conv)
        self.conv = [ids, m, c]
        if not PACK_CONVS:
            self._finish(*self.conv); self.conv = None

    def row(self):
        while True:
            if self.ready:
                return self.ready.pop(0)
            if len(self.buf) >= SEQ + 1:
                r, m, c = self.buf[:SEQ + 1], self.mbuf[:SEQ + 1], self.cbuf[:SEQ + 1]
                self.buf, self.mbuf, self.cbuf = self.buf[SEQ:], self.mbuf[SEQ:], self.cbuf[SEQ:]
                self.rows["plain"] += 1
                return r, m[1:], c[1:]                          # mask[i]: is target r[i+1] trained
            names = list(self.sources)
            name = self.rng.choices(names, weights=[MIX.get(n, 0) for n in names])[0]
            try:
                item = next(self.sources[name])
            except StopIteration:
                self.sources.pop(name); continue
            self.add(item, CE_SRC.get(name, CE_W))

    def batch(self):
        rows = [self.row() for _ in range(BATCH)]
        return (torch.tensor([r for r, _, _ in rows]), torch.tensor([m for _, m, _ in rows], dtype=torch.float32),
                torch.tensor([c for _, _, c in rows], dtype=torch.float32))


def cycle(items):
    while True:
        for x in items:
            yield x


# ── Model pieces ─────────────────────────────────────────────────────────────

def softcap(x, c):
    return torch.tanh(x / c) * c if c else x


@torch.no_grad()
def bpb(model, head_w, encode, bos, docs, cap):
    model.eval()
    nats = byts = 0
    for d in docs:
        ids = [bos] + encode(d)
        x = torch.tensor([ids], device=DEV)
        with torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
            h = model(input_ids=x).last_hidden_state[0, :-1]
        logits = softcap((h.float() @ head_w.float().T), cap)
        nats += F.cross_entropy(logits, x[0, 1:], reduction="sum").item()
        byts += len(d.encode("utf-8"))
    model.train()
    return nats / math.log(2) / max(1, byts)


def bpb_segments(model, head_w, encode, bos, recs, cap):
    """Bits per byte on the trained (model-written) parts of chat records only."""
    model.eval()
    nats = byts = 0
    for rec in recs:
        ids, mask, n_bytes = [bos], [], 0
        for text, train in rec:
            e = encode(text); ids += e; mask += [train] * len(e)
            n_bytes += len(text.encode("utf-8")) if train else 0
        ids = ids[:2048]; mask = mask[:len(ids) - 1]
        x = torch.tensor([ids], device=DEV)
        with torch.no_grad(), torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
            h = model(input_ids=x).last_hidden_state[0, :-1]
        logits = softcap((h.float() @ head_w.float().T), cap)
        ce = F.cross_entropy(logits, x[0, 1:], reduction="none")
        nats += (ce * torch.tensor(mask, device=DEV, dtype=ce.dtype)).sum().item(); byts += n_bytes
    model.train()
    return nats / math.log(2) / max(1, byts)


def save_ckpt(student, tok_json, tag, extra):
    d = os.path.join(OUT, "ckpt")
    tmp = d + ".tmp"
    os.makedirs(tmp, exist_ok=True)
    sd = {k: v.detach().to(torch.bfloat16).cpu() for k, v in student.state_dict().items()}   # bf16 on disk
    student.save_pretrained(tmp, state_dict=sd, safe_serialization=True)
    json.dump(tok_json, open(os.path.join(tmp, "tokenizer.json"), "w"))
    json.dump({"tag": tag, **extra}, open(os.path.join(tmp, "ckpt_info.json"), "w"))
    import shutil
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.rename(tmp, d)
    if CKPT_KEEP and extra.get("step") and not tag.startswith("final"):  # dated copies; heal 3's own folder is never touched
        shutil.copytree(d, os.path.join(OUT, f"ckpt-step{extra['step']}"))
        old = sorted((x for x in os.listdir(OUT) if x.startswith("ckpt-step")), key=lambda x: int(x[9:]))
        for x in old[:-CKPT_KEEP]:
            shutil.rmtree(os.path.join(OUT, x))
    log("checkpoint", tag)


def main():
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from tokenizers import Tokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    kept = load_json("KEPT_IDS", "kept_ids.json")
    tok_json = load_json("TOKENIZER", "tokenizer_pruned.json")
    if kept is None or tok_json is None:
        raise SystemExit("needs kept_ids.json and tokenizer_pruned.json from stage 1")
    ptok = Tokenizer.from_str(json.dumps(tok_json))
    encode = lambda s: ptok.encode(s, add_special_tokens=False).ids           # student ids
    bos = ptok.token_to_id(tok.bos_token)

    m = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16)
    teacher = m.model.language_model.to(DEV).eval()
    t_head = m.get_output_embeddings().weight
    for p in teacher.parameters():
        p.requires_grad_(False)
    cap = getattr(teacher.config, "final_logit_softcapping", None)
    kept_t = torch.tensor(kept, device=DEV)
    new2old = kept_t

    # Which layers to keep: KEEP_LAYERS="0,1,..." or the SKIP least-changing (from stage 1 layer_scores).
    L = teacher.config.num_hidden_layers
    if os.environ.get("KEEP_LAYERS"):
        keep_layers = [int(x) for x in os.environ["KEEP_LAYERS"].split(",")]
    else:
        scores = json.loads(os.environ["LAYER_SCORES"])
        first_shared = L - (teacher.config.num_kv_shared_layers or 0)
        prev = teacher.config.layer_types[:first_shared]
        prot = {0, L - 1} | {len(prev) - 1 - prev[::-1].index(t) for t in set(prev)}
        order = [i for i in sorted(range(L), key=lambda i: scores[i]) if i not in prot]
        skip = set(order[:int(os.environ.get("SKIP", 10))])
        keep_layers = [i for i in range(L) if i not in skip]
    log("keep layers", keep_layers)

    # FFN channel scores on a little calibration text (teacher ids).
    held_agent, train_agent = agent_texts()
    web_eval = []
    ws = web_stream(0)
    for _ in range(80):
        web_eval.append(next(ws)[:3000])
    cal = web_eval[:40] + [a[:3000] for a in train_agent[:20]]
    t_enc = lambda s: [new2old[i].item() for i in encode(s)]
    sums = [None] * L
    hid = torch.zeros(teacher.config.hidden_size, device=DEV)
    hooks = []
    for l in teacher.layers:
        for n in ("input_layernorm", "pre_feedforward_layernorm"):
            def acc(mod, a, o):
                hid.add_(o.float().abs().reshape(-1, o.shape[-1]).mean(0))   # returns None: output unchanged
            hooks.append(getattr(l, n).register_forward_hook(acc))
    for i, l in enumerate(teacher.layers):
        def pre(mod, a, i=i):
            v = a[0].float().abs().reshape(-1, a[0].shape[-1]).sum(0)
            sums[i] = v if sums[i] is None else sums[i] + v
        hooks.append(l.mlp.down_proj.register_forward_pre_hook(pre))
    with torch.no_grad():
        for d in cal:
            teacher(input_ids=torch.tensor([[tok.bos_token_id] + t_enc(d)], device=DEV))
    for h in hooks:
        h.remove()
    ch = [s * l.mlp.down_proj.weight.float().norm(dim=0) for s, l in zip(sums, teacher.layers)]

    hk = hid.topk(HIDDEN).indices.sort().values.tolist() if HIDDEN else None
    if RESUME:
        from huggingface_hub import snapshot_download
        from transformers.models.gemma4.modeling_gemma4 import Gemma4TextModel
        repo, path = RESUME.split(":", 1)
        d = snapshot_download(repo, repo_type="dataset", allow_patterns=[f"{path}/*"], token=os.environ.get("HF_TOKEN"))
        student = Gemma4TextModel.from_pretrained(os.path.join(d, path), dtype=torch.float32).to(DEV)
        info = json.load(open(os.path.join(d, path, "ckpt_info.json")))
        keep_layers = info.get("keep_layers", keep_layers)
        log("resumed from", RESUME, info)
    else:
        student = cut(teacher, keep_layers, FFN, ch, kept, hk).to(DEV).float()
    student.train()
    s_head = student.embed_tokens.weight                                     # tied
    n_params = sum(p.numel() for p in student.parameters())
    n_body = sum(p.numel() for n, p in student.named_parameters() if not n.startswith("embed_tokens"))
    log(f"student {n_params / 1e6:.0f}M params, body {n_body / 1e6:.0f}M ({len(keep_layers)} layers, hidden {student.config.hidden_size}, ffn {FFN}, vocab {len(kept)})")
    try:
        student.gradient_checkpointing_enable()
    except Exception as e:
        log("no gradient checkpointing:", e)
    opt = torch.optim.AdamW(student.parameters(), lr=LR, betas=(0.9, 0.95), weight_decay=0.0, fused=DEV == "cuda")

    evals = {"web": web_eval[40:], "agent_replies": [a[:3000] for a in held_agent[:80]]}
    tool_train, tool_eval = [], []
    if MIX.get("toucan"):                                     # prep_tools: rendered, masked, length-limited
        from prep_tools import toucan_records
        st = {}
        recs = toucan_records(tok, lambda t: len(encode(t)), limit=int(os.environ.get("TOUCAN_ROWS", 0)) or None, stats=st)
        tool_eval, tool_train = [r["segments"] for r in recs[:TOOL_EVAL]], [r["segments"] for r in recs[TOOL_EVAL:]]
        log("toucan", st, "train", len(tool_train), "held out", len(tool_eval))
    stop = {ptok.token_to_id(t) for t in ("<eos>", "<end_of_turn>", "<turn|>") if ptok.token_to_id(t) is not None}
    PROMPTS = ["What is the capital of France? Answer in one sentence.", "Write a Python function that reverses a string.",
               "Explain why the sky is blue in two sentences.", "What is 17 times 23? Think step by step, then answer.",
               "What's the weather like in Phoenix right now?"]
    WEATHER = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city.",
               "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name"}}, "required": ["city"]}}}]
    SEARCH = [{"type": "function", "function": {"name": "web_search", "description": "Search the web. Returns titles, links and snippets.",
              "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "What to search for"}}, "required": ["query"]}}},
              {"type": "function", "function": {"name": "recall", "description": "Look up what is saved in memory about the user or a topic.",
              "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]
    # Multi-turn probes from tiny Gemma 4 in the browser (2026-11-02) and the heal 4 review, each with a pass check
    # on the reply. "Same call, different result" tells reading the result apart from a canned answer.
    def after_search(result, q="what's it like outside in phoenix rn"):
        return [{"role": "user", "content": q},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": {"query": "Phoenix weather now"}}}]},
                {"role": "tool", "tool_call_id": "c1", "name": "web_search", "content": result}]
    calls = lambda name: (lambda r: f"<|tool_call>call:{name}" in r)
    says = lambda *xs: (lambda r: "<|tool_call>" not in r and all(x.lower() in r.lower() for x in xs))
    PROBES = {   # made-up fixtures: the answer must come from the result
        "star trek, detail in turn 2": ([
            {"role": "user", "content": "can you find out the name of the man who was in star trek that recently died?"},
            {"role": "assistant", "content": "Sure. Do you remember anything else about him, like which Star Trek series he was in?"},
            {"role": "user", "content": "literally just search the web for like \"death star trek\" and look for the latest results man"}], calls("web_search")),
        "name given in turn 2": ([
            {"role": "user", "content": "look up an actor for me"},
            {"role": "assistant", "content": "Sure, which actor?"},
            {"role": "user", "content": "just use the web_search tool for \"patrick stewart\""}], lambda r: calls("web_search")(r) and "stewart" in r.lower()),
        "answer from a tool result": (after_search("1. Phoenix, AZ Weather - 61°F, light rain, wind 14 mph, high 66°F - weather.example"), says("61")),
        "same call, different result": (after_search("1. Phoenix, AZ Weather - 97°F, clear and sunny, wind 3 mph, high 101°F - weather.example"), says("97")),
        "tool error": (after_search("Error: search service timed out"), lambda r: "<|tool_call>call:web_search" in r or ("°" not in r and any(w in r.lower() for w in ("couldn", "could not", "error", "timed out", "try again", "wasn't able", "unable")))),
        "what do you remember about me": ([{"role": "user", "content": "What do you remember about me?"}], lambda r: "call:web_search" not in r),
    }
    def chat(p):
        if p in PROBES:
            return tok.apply_chat_template(PROBES[p][0], tools=SEARCH, tokenize=False, add_generation_prompt=True)
        kw = {"tools": WEATHER} if "weather" in p else {}
        return tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True, **kw)
    if MIX.get("toucan"):
        PROMPTS += list(PROBES)

    @torch.no_grad()
    def chat_samples(n=64):
        """Greedy (worst case for loops) and the app's own settings (temperature 0.7, top-k 64, repeat penalty 1.15)."""
        student.eval()
        out = []
        g = torch.Generator(device=DEV).manual_seed(0)
        for mode in ("greedy", "app"):
            for p in PROMPTS:
                ids = ptok.encode(chat(p), add_special_tokens=False).ids; gen = []
                for _ in range(n):
                    with torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
                        h = student(input_ids=torch.tensor([ids + gen], device=DEV)).last_hidden_state[0, -1]
                    lg = (h.float() @ s_head.float().T)
                    if mode == "greedy":
                        j = int(lg.argmax())
                    else:
                        if gen:
                            prev = torch.tensor(sorted(set(gen)), device=DEV)
                            v = lg[prev]
                            lg[prev] = torch.where(v > 0, v / 1.15, v * 1.15)
                        top = lg.topk(64)
                        pr = torch.softmax(top.values / 0.7, -1)
                        j = int(top.indices[torch.multinomial(pr, 1, generator=g)])
                    gen.append(j)
                    if j in stop:
                        break
                reply = ptok.decode(gen, skip_special_tokens=False)
                out.append({"mode": mode, "prompt": p, "reply": reply, **({"pass": bool(PROBES[p][1](reply))} if p in PROBES else {})})
        student.train()
        return out
    t_head_k = t_head[kept_t]

    def evaluate(tag):
        r = {"step": step, "min": round((time.time() - T0) / 60, 1), "tag": tag}
        for k, docs in evals.items():
            r[f"student_{k}"] = round(bpb(student, s_head, encode, bos, docs, cap), 4)
        if tool_eval:
            r["student_tools_replies"] = round(bpb_segments(student, s_head, encode, bos, tool_eval, cap), 4)
        r["samples"] = chat_samples()
        if MIX.get("toucan"):
            for mode in ("greedy", "app"):
                got = [x["pass"] for x in r["samples"] if x["mode"] == mode and "pass" in x]
                r[f"probes_{mode}"] = f"{sum(got)}/{len(got)}"
        open(os.path.join(OUT, "metrics.jsonl"), "a").write(json.dumps(r) + "\n")
        log("eval", {k: v for k, v in r.items() if k != "samples"}, "|", " / ".join(repr(x["reply"][:70]) for x in r["samples"][:2]))
        return r

    step = 0
    base = {}
    with torch.no_grad():
        for k, docs in evals.items():
            # Teacher on the same (pruned-tokenizer) text, softmax over the kept rows: the target to approach.
            nats = byts = 0
            for d in docs:
                ids = [tok.bos_token_id] + t_enc(d)
                x = torch.tensor([ids], device=DEV)
                h = teacher(input_ids=x).last_hidden_state[0, :-1]
                lg = softcap((h.float() @ t_head_k.float().T), cap)
                tgt = torch.tensor([bos] + encode(d), device=DEV)[1:]
                nats += F.cross_entropy(lg, tgt, reduction="sum").item(); byts += len(d.encode("utf-8"))
            base[f"teacher_{k}"] = round(nats / math.log(2) / byts, 4)
    log("teacher", base)
    open(os.path.join(OUT, "metrics.jsonl"), "a").write(json.dumps({"teacher": base}) + "\n")
    first = evaluate("cut, before healing")

    template = lambda q, a: tok.apply_chat_template([{"role": "user", "content": q}, {"role": "assistant", "content": a}], tokenize=False).removeprefix(tok.bos_token)
    sources = {"web": web_stream(200), "code": code_stream(), "agent": cycle(train_agent)}
    if tool_train:
        sources["toucan"] = cycle(tool_train)
    if MIX.get("chat"):
        sources["chat"] = chat_stream(template)
    if MIX.get("gentools") and GEN:                            # tool calls get their own share of the mix
        sources["gentools"] = cycle(gen_texts(True))
    if MIX.get("gen") and GEN:
        sources["gen"] = cycle(gen_texts(False if MIX.get("gentools") else None))
    if MIX.get("math"):
        sources["math"] = math_stream()
    if MIX.get("smoltalk"):
        sources["smoltalk"] = smoltalk_stream(tok)
    if MIX.get("math"):
        sources["math"] = math_stream()
    packer = Packer(encode, bos, sources, pad=ptok.token_to_id("<pad>") or 0)
    deadline = T0 + MINUTES * 60
    last_ckpt = time.time()
    warm = 100
    total_est = None
    tokens = trained = 0
    while time.time() < deadline:
        x, wmask, cew = packer.batch()
        x, wmask, cew = x.to(DEV), wmask.to(DEV), cew.to(DEV)                # ids; which targets are trained; CE weight
        inp, tgt = x[:, :-1], x[:, 1:]
        with torch.no_grad():
            th = teacher(input_ids=new2old[inp]).last_hidden_state
            tl = softcap(th.float() @ t_head_k.float().T, cap)
            tp = F.log_softmax(tl, -1)
        with torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
            sh = student(input_ids=inp).last_hidden_state
        sl = softcap(sh.float() @ s_head.float().T, cap)
        sp = F.log_softmax(sl, -1)
        # Per-token KL averaged over trained targets (all of them for plain text; equals batchmean KL when
        # nothing is masked), plus next-token loss where a source asks for it (CE_SRC / CE_W).
        w = wmask.reshape(-1)
        kl_tok = (tp.exp() * (tp - sp)).sum(-1).reshape(-1)
        kd = (kl_tok * w).sum() / w.sum().clamp(min=1)
        nll = F.nll_loss(sp.reshape(-1, sp.shape[-1]), tgt.reshape(-1), reduction="none")
        ce = (nll * w).sum() / w.sum().clamp(min=1)                          # logged
        loss = kd + (nll * cew.reshape(-1)).sum() / w.sum().clamp(min=1)
        # Warmup then cosine to 10% over the time budget.
        frac = min(1.0, (time.time() - T0) / (MINUTES * 60))
        lr = LR * min(1.0, (step + 1) / warm) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac)))
        for g in opt.param_groups:
            g["lr"] = lr
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        opt.step()
        step += 1
        tokens += inp.numel()
        trained += int(wmask.sum().item())
        if step % 20 == 0:
            log(f"step {step} kd {kd.item():.4f} ce {ce.item():.3f} lr {lr:.2e} tokens {tokens / 1e6:.1f}M trained {trained / 1e6:.1f}M rows {packer.rows}")
        if step % EVAL_EVERY == 0:
            evaluate("training")
        if time.time() - last_ckpt > CKPT_MIN * 60:
            save_ckpt(student, tok_json, f"step {step}", {"step": step, "tokens": tokens, "keep_layers": keep_layers, "ffn": FFN})
            last_ckpt = time.time()
    last = evaluate("end")
    save_ckpt(student, tok_json, f"final step {step}", {"tokens": tokens, "keep_layers": keep_layers, "ffn": FFN})
    summary = {"teacher": base, "before": first, "after": last, "steps": step, "tokens": tokens,
               "student_params": n_params, "keep_layers": keep_layers, "ffn": FFN, "vocab": len(kept)}
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    log("done", summary)


if __name__ == "__main__":
    # Exit hard either way: streaming-dataset threads kept a crashed job alive until its time limit (and billed it).
    code = 0
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
