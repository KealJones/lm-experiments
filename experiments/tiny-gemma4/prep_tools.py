"""Tool-use data for heal 4: Toucan conversations in Gemma 4's native format, the old E2B answers re-filtered,
and a loss mask so the student only learns what the model itself writes.

Why (heal 3 in the browser, 2026-11-02): tiny Gemma 4 ignored details given in a later turn, wrote
"Tool Call Plan (Simulated): web_search(...)" as text, and stopped after tool results. Its tool data was
single-turn, never had a tool result, and kept E2B's prose "calls" (gen.py only checked the answer finished).

Sources (no Claude-written text anywhere):
  - Agent-Ark/Toucan-1.5M, SFT subset (Apache-2.0): 119K conversations with real MCP tool executions; questions by
    open models, answers by GPT-OSS 120B / Kimi K2 / Qwen3 32B. Subsets: single-turn, multi-turn (follow-up user
    turns), diversified, irrelevant (no tool fits; answer anyway, without a fake call).
  - gen.py's E2B answers (hf-gen2, hf-gen3), filtered by `keep_gen`.
  nvidia/When2Call was looked at and left out: its SFT split has no tool calls at all, and most answers refuse
  ordinary requests ("Apologies, I'm unable to create a Facebook ad copy"), which is the opposite of what we want.

A record is a list of segments [(text, train)], rendered with E2B's own chat template. Segments split only at
special-token boundaries, so encoding them one by one gives the same ids as encoding the whole text (checked
in `check`). train=False: system/tool declarations, user turns, tool results; train=True: everything the model
writes (thinking, text, tool calls, the <|tool_response> stop token, <turn|>).

    python prep_tools.py [N]     local dry run on CPU: counts, length stats, a few rendered samples, mask check
"""
import ast, gzip, json, os, random, re, sys

TEMPLATE_MODEL = os.environ.get("MODEL", "google/gemma-4-E2B-it")
RESP_CHARS = int(os.environ.get("TOOL_RESP_CHARS", 1200))     # tool results are cut like Squiggle cuts them
MAX_TOKENS = int(os.environ.get("TOOL_MAX_TOKENS", 2000))     # whole conversation, so it fits one SEQ=2048 row
IRRELEVANT_SHARE = float(os.environ.get("IRRELEVANT_SHARE", 0.15))
HERE = os.path.dirname(os.path.abspath(__file__))


# ── Masking ──────────────────────────────────────────────────────────────────

MODEL_OPEN = "<|turn>model\n"
TURN_CLOSE = "<turn|>"
RESP_OPEN, RESP_CLOSE = "<|tool_response>", "<tool_response|>"


def segments(text):
    """Split a rendered conversation into (text, train) pieces. Inside a model turn, everything is trained except
    the bodies of tool results; the first <|tool_response> of a run is trained (it is where the model stops)."""
    out, i = [], 0
    while True:
        j = text.find(MODEL_OPEN, i)
        if j < 0:
            out.append((text[i:], False)); break
        j += len(MODEL_OPEN)
        out.append((text[i:j], False))
        k = text.find(TURN_CLOSE, j)
        end = len(text) if k < 0 else k + len(TURN_CLOSE)
        turn, p = text[j:end], 0
        while True:
            a = turn.find(RESP_OPEN, p)
            if a < 0:
                out.append((turn[p:], True)); break
            a += len(RESP_OPEN)
            out.append((turn[p:a], True))
            b = a
            while True:                                              # a run of consecutive results is one masked piece
                c = turn.find(RESP_CLOSE, b)
                b = len(turn) if c < 0 else c + len(RESP_CLOSE)
                if c >= 0 and turn.startswith(RESP_OPEN, b):
                    b += len(RESP_OPEN); continue
                break
            out.append((turn[a:b], False))
            p = b
        i = end
    return [(t, w) for t, w in out if t]


# ── Toucan ───────────────────────────────────────────────────────────────────

def _cut(s, n=RESP_CHARS):
    s = str(s)
    return s if len(s) <= n else s[:n].rstrip() + f"\n…(cut, {len(s) - n} more characters)"


def _args(raw):
    try:
        call = ast.literal_eval(raw) if isinstance(raw, str) else raw
        args = call.get("arguments")
        args = json.loads(args) if isinstance(args, str) else (args or {})
        return call["name"], args if isinstance(args, dict) else None
    except Exception:
        return None, None


def toucan_messages(row):
    """Toucan's roles (user, assistant, tool_call, tool_response) → chat-template messages. Calls follow a
    separate assistant text message, so the template keeps the order text → calls → results → text in one turn."""
    msgs, pending, n = [], [], 0
    for m in json.loads(row["messages"]):
        role, content = m.get("role"), m.get("content")
        if role == "tool_call":
            name, args = _args(content)
            if not name or args is None:
                return None
            n += 1
            call = {"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": args}}
            if msgs and msgs[-1]["role"] == "assistant" and msgs[-1].get("tool_calls"):   # parallel calls: one message
                msgs[-1]["tool_calls"].append(call)
            else:
                msgs.append({"role": "assistant", "content": "", "tool_calls": [call]})
            pending.append(call)
        elif role == "tool_response":
            if not pending:
                return None
            call = pending.pop(0)
            msgs.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": _cut(content)})
        elif role in ("user", "assistant"):
            if pending:
                return None                                          # a call without its result
            if role == "assistant" and not str(content or "").strip():
                continue
            msgs.append({"role": role, "content": str(content or "")})
        else:
            return None
    if pending or not msgs or msgs[-1]["role"] != "assistant" or msgs[-1].get("tool_calls"):
        return None
    return msgs


def _clean_tools(tools):
    out = []
    for t in json.loads(tools):
        f = t.get("function") or {}
        p = f.get("parameters") or {"type": "object", "properties": {}}
        out.append({"type": "function", "function": {"name": f.get("name"), "description": (f.get("description") or "").strip(), "parameters": p}})
    return out


def toucan_rows(seed=5):
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download, list_repo_files
    files = sorted(f for f in list_repo_files("Agent-Ark/Toucan-1.5M", repo_type="dataset") if f.startswith("SFT/"))
    rows = []
    for f in files:
        rows += pq.read_table(hf_hub_download("Agent-Ark/Toucan-1.5M", f, repo_type="dataset")).to_pylist()
    random.Random(seed).shuffle(rows)
    return rows


_W = {}


def _render(r):
    """One Toucan row → ("ok", record) or (reason, None). Runs in forked workers (tokenizer passed via _W)."""
    msgs = toucan_messages(r)
    if not msgs:
        return "bad_shape", None
    try:
        text = _W["tok"].apply_chat_template(msgs, tools=_clean_tools(r["tools"]), tokenize=False).removeprefix(_W["tok"].bos_token)
    except Exception:
        return "template_error", None
    text = _fit(text, _W["count"])
    if text is None:
        return "too_long", None
    return "ok", {"source": "toucan:" + r["subset_name"], "segments": segments(text)}


def toucan_records(tok, count_tokens, limit=None, stats=None, workers=None):
    """Rendered, masked, length-limited Toucan conversations, with the 'irrelevant' subset cut to IRRELEVANT_SHARE.
    limit: rows to look at (all 119K take ~28 CPU-minutes, so the job uses every core)."""
    import multiprocessing as mp
    stats = stats if stats is not None else {}
    rows = toucan_rows()
    rows = rows[:limit] if limit else rows
    _W.update(tok=tok, count=count_tokens)
    workers = workers or max(1, min(32, (os.cpu_count() or 1)))
    if workers > 1:
        with mp.get_context("fork").Pool(workers) as pool:
            done = pool.map(_render, rows, chunksize=64)
    else:
        done = [_render(r) for r in rows]
    keep, irr = [], []
    for why, rec in done:
        if rec is None:
            stats[why] = stats.get(why, 0) + 1
        else:
            (irr if rec["source"] == "toucan:irrelevant" else keep).append(rec)
    n_irr = min(len(irr), int(len(keep) * IRRELEVANT_SHARE / (1 - IRRELEVANT_SHARE)))
    out = keep + irr[:n_irr]
    random.Random(6).shuffle(out)
    stats["kept"] = len(out); stats["irrelevant_kept"] = n_irr; stats["irrelevant_dropped"] = len(irr) - n_irr
    return out


def _fit(text, count_tokens):
    """Whole conversation if it fits; otherwise cut after the last complete model turn that fits (multi-turn
    conversations keep their first exchanges); None if not even the first exchange fits."""
    if count_tokens(text) <= MAX_TOKENS:
        return text
    ends = [m.end() for m in re.finditer(re.escape(TURN_CLOSE) + "\n", text)]
    best = None
    for e in ends:
        part = text[:e]
        if MODEL_OPEN not in part or not part.rstrip().endswith(TURN_CLOSE):
            continue
        if part.rfind("<|turn>user") > part.rfind(MODEL_OPEN):
            continue                                                 # ends on a user turn
        if count_tokens(part) > MAX_TOKENS:
            break
        best = part
    return best


# ── Old E2B answers (gen.py) ─────────────────────────────────────────────────

FAKE_CALL = re.compile(
    r"simulated\)|\(simulated|simulat(ed|ing) (tool|function|call|api|output|response|result)|tool[_ ]call plan|"
    r"```(tool_code|tool_call|tool|function_call|json\s*\{\s*\"(name|function)\")|"
    r"\b(call|use|invoke|run) (the )?`?[a-z_][a-z0-9_]*`? (tool|function)\b.{0,40}\(|"
    r"<\|tool_call>(?!call:)", re.I)
LIST_ASK = re.compile(r"(for example|e\.g\.)[^\n]{0,60}(looking for|interested in|want)[^\n]*:\s*\n\s*(\d+\.|[-*•])", re.I)


def answer_of(text):
    return text.split(MODEL_OPEN, 1)[1] if MODEL_OPEN in text else ""


def keep_gen(row, reasons=None):
    """False for E2B answers that teach the wrong thing: a tool call written as text, or (when tools were offered)
    no native call and a menu of questions instead of acting. Direct answers (no tool fits) and single clarifying
    questions stay."""
    a = answer_of(row["text"])
    visible = re.sub(r"<\|channel>.*?<channel\|>", "", a, flags=re.S)
    def drop(why):
        if reasons is not None:
            reasons[why] = reasons.get(why, 0) + 1
        return False
    if row.get("source") == "hermes":
        if FAKE_CALL.search(a):
            return drop("tool call written as text")
        if "<|tool_call>" not in a:
            if LIST_ASK.search(visible):
                return drop("tools offered: a menu of questions instead of a call")
    return True


def gen_records(paths, reasons=None):
    rows = [json.loads(l) for p in paths for l in gzip.open(p, "rt")]
    out = [{"source": "gen:" + r["source"], "segments": segments(r["text"])} for r in rows if keep_gen(r, reasons)]
    return rows, out


# ── Dry run ──────────────────────────────────────────────────────────────────

def check(ptok, recs):
    """Encoding the segments one by one must give the same ids as encoding the whole text."""
    bad = 0
    for r in recs:
        whole = ptok.encode("".join(t for t, _ in r["segments"]), add_special_tokens=False).ids
        parts = [i for t, _ in r["segments"] for i in ptok.encode(t, add_special_tokens=False).ids]
        bad += whole != parts
    return bad


def main():
    from transformers import AutoTokenizer
    from tokenizers import Tokenizer
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    tok = AutoTokenizer.from_pretrained(TEMPLATE_MODEL)
    ptok = Tokenizer.from_str(open(os.path.join(HERE, "hf-stage1/tokenizer_pruned.json")).read())
    count = lambda s: len(ptok.encode(s, add_special_tokens=False).ids)
    st = {}
    recs = toucan_records(tok, count, limit=n, stats=st)
    print("toucan", st)
    from collections import Counter
    print(Counter(r["source"] for r in recs))
    toks = sorted(count("".join(t for t, _ in r["segments"])) for r in recs)
    trained = sum(count(t) for r in recs for t, w in r["segments"] if w)
    print(f"tokens p50 {toks[len(toks)//2]} p90 {toks[int(len(toks)*.9)]} max {toks[-1]}; total {sum(toks)}, trained {trained} ({100*trained/sum(toks):.0f}%)")
    print("segment/whole mismatches:", check(ptok, recs[:500]))
    reasons = {}
    rows, g = gen_records([os.path.join(HERE, "hf-gen2/gen.jsonl.gz"), os.path.join(HERE, "hf-gen3/gen.jsonl.gz")], reasons)
    print(f"gen: kept {len(g)} of {len(rows)}; dropped {reasons}")
    print(Counter(r["source"] for r in g))
    print("gen segment/whole mismatches:", check(ptok, g[:500]))
    os.makedirs(os.path.join(HERE, "prep"), exist_ok=True)
    with open(os.path.join(HERE, "prep/samples.md"), "w") as f:
        for r in [x for x in recs if "multi" in x["source"]][:2] + [x for x in recs if "irrelevant" in x["source"]][:1] + [x for x in recs if "single" in x["source"]][:2]:
            f.write(f"## {r['source']}\n\n```\n" + "".join((t if w else f"⟦{t}⟧") for t, w in r["segments"]) + "\n```\n\n")
    json.dump({"toucan": st, "toucan_sources": Counter(r["source"] for r in recs), "gen_kept": len(g), "gen_total": len(rows),
               "gen_dropped": reasons, "tokens_p50": toks[len(toks)//2], "tokens_p90": toks[int(len(toks)*.9)],
               "trained_share": round(trained / sum(toks), 3)}, open(os.path.join(HERE, "prep/stats.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
