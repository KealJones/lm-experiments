"""Draft -> fact-check: can a small model catch (and fix) its own mistakes?

Step 1 (draft): the model gets a plain question plus Wikipedia / Wikidata tools and answers.
Step 2 (review): a NEW conversation with the same model gets the question and its own draft, plus the same tools,
and has to say whether the draft is right and give a final answer. Two review styles:
  plain  - Keal's wording: "review this question and answer and tell me if it is good and right"
  strict - a fact-checker told to assume the draft may be wrong and to check every claim with the tools

  python factcheck.py check                          tool smoke test (needs internet)
  python factcheck.py worker --model qwen3 --gpu 0 --tag pilot|full
  python factcheck.py report                         -> RESULTS.md from results_*.json
"""
import argparse, concurrent.futures as cf, glob, html, json, os, pathlib, re, sys, time, urllib.parse, urllib.request

HERE = pathlib.Path(__file__).parent
QUESTIONS = json.loads((HERE / "questions.json").read_text())
TODAY = "2026-11-04"
MODELS = {
    "qwen3": "Qwen/Qwen3-0.6B",
    "llama": "unsloth/Llama-3.2-1B-Instruct",   # ungated mirror of meta-llama/Llama-3.2-1B-Instruct
    "qwen35": "Qwen/Qwen3.5-0.8B",
    "coder": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
}
SAMPLES = 3            # sampled runs per question (full); pilot = 1
MAX_TURNS = 6          # model replies per conversation
MAX_CONTEXT = 7000     # tokens
MAX_NEW = 700
UA = "lm-experiments-factcheck/0.1 (https://github.com/KealJones/lm-experiments; research script)"

# ---------------------------------------------------------------- tools (Wikipedia + Wikidata)

_cache = {}


def get_json(url, params):
    full = url + "?" + urllib.parse.urlencode({**params, "format": "json"})
    if full in _cache:
        return _cache[full]
    last = None
    for i in range(4):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.loads(r.read().decode())
            _cache[full] = out
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"request failed: {last}")


WP = "https://en.wikipedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def tool_search(query="", **_):
    if not str(query).strip():
        return "error: give a query"
    j = get_json(WP, {"action": "query", "list": "search", "srsearch": query, "srlimit": 5})
    hits = j.get("query", {}).get("search", [])
    if not hits:
        return f"No Wikipedia pages found for '{query}'."
    return "\n".join(f"{i+1}. {h['title']}: {clean(h.get('snippet'))}" for i, h in enumerate(hits))


def tool_read_page(title="", find="", **_):
    if not str(title).strip():
        return "error: give a page title"
    j = get_json(WP, {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
    pages = list(j.get("query", {}).get("pages", {}).values())
    if not pages or "missing" in pages[0] or not pages[0].get("extract"):
        return f"No Wikipedia page called '{title}'. Try search first."
    text = pages[0]["extract"]
    head = f"Wikipedia: {pages[0]['title']}\n"
    if str(find).strip():
        words = [w.lower() for w in re.findall(r"\w+", str(find)) if len(w) > 2] or [str(find).lower()]
        paras = [p for p in re.split(r"\n+", text) if p.strip()]
        hits = [p for p in paras if any(w in p.lower() for w in words)]
        if hits:
            return head + f"Paragraphs mentioning '{find}':\n" + cut("\n\n".join(hits[:6]), 2500)
        head += f"(nothing mentions '{find}'; showing the start)\n"
    return head + cut(text, 2500)


def _wd_labels(ids):
    out = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 50):
        j = get_json(WD, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "labels",
                          "languages": "en"})
        for k, v in j.get("entities", {}).items():
            out[k] = v.get("labels", {}).get("en", {}).get("value", k)
    return out


def _wd_value(dv):
    t, v = dv.get("type"), dv.get("value")
    if t == "wikibase-entityid":
        return ("id", v.get("id"))
    if t == "time":
        s = v["time"].lstrip("+")
        p = v.get("precision", 11)
        return ("str", s[:4] if p <= 9 else s[:7] if p == 10 else s[:10])
    if t == "quantity":
        unit = v.get("unit", "1")
        amt = v["amount"].lstrip("+")
        return ("qty", (amt, unit.rsplit("/", 1)[-1] if unit != "1" else None))
    if t == "monolingualtext":
        return ("str", v.get("text"))
    if t == "string":
        return ("str", v)
    return ("str", str(v))


def tool_wikidata(entity="", property="", **_):
    if not str(entity).strip():
        return "error: give an entity name"
    s = get_json(WD, {"action": "wbsearchentities", "search": entity, "language": "en", "limit": 1})
    if not s.get("search"):
        return f"No Wikidata item found for '{entity}'."
    qid = s["search"][0]["id"]
    e = get_json(WD, {"action": "wbgetentities", "ids": qid, "props": "labels|descriptions|claims",
                      "languages": "en"})["entities"][qid]
    rows, need = [], set()
    for pid, claims in list(e.get("claims", {}).items()):
        if not claims or claims[0]["mainsnak"].get("datatype") in ("external-id", "commonsMedia", "url",
                                                                     "globe-coordinate", "geo-shape", "tabular-data"):
            continue
        vals = []
        for c in claims[:4]:
            dv = c["mainsnak"].get("datavalue")
            if not dv:
                continue
            kind, val = _wd_value(dv)
            vals.append((kind, val))
            if kind == "id":
                need.add(val)
            if kind == "qty" and val[1]:
                need.add(val[1])
        if vals:
            rows.append((pid, vals, len(claims)))
            need.add(pid)
    labels = _wd_labels(sorted(need)) if need else {}

    def show(kind, val):
        if kind == "id":
            return labels.get(val, val)
        if kind == "qty":
            return val[0] + (" " + labels.get(val[1], "") if val[1] else "")
        return str(val)

    lines = []
    for pid, vals, n in rows:
        lab = labels.get(pid, pid)
        if property and str(property).lower() not in lab.lower():
            continue
        more = f" (+{n - len(vals)} more)" if n > len(vals) else ""
        lines.append(f"- {lab}: " + "; ".join(show(k, v) for k, v in vals) + more)
    name = e.get("labels", {}).get("en", {}).get("value", qid)
    desc = e.get("descriptions", {}).get("en", {}).get("value", "")
    if not lines:
        return f"Wikidata: {name} ({desc}). No facts matching '{property}'." if property else f"Wikidata: {name} ({desc}). No facts."
    return cut(f"Wikidata: {name} ({desc})\n" + "\n".join(lines), 2500)


def cut(s, n):
    return s if len(s) <= n else s[:n] + "\n...[cut]"


TOOL_FNS = {"search": tool_search, "read_page": tool_read_page, "wikidata": tool_wikidata}
TOOLS = [
    {"type": "function", "function": {
        "name": "search", "description": "Search Wikipedia. Returns the top 5 page titles with a snippet each.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "what to search for"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_page",
        "description": "Read a Wikipedia page by its exact title. Give `find` to get only the paragraphs that mention those words.",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": "exact page title, e.g. from search"},
            "find": {"type": "string", "description": "optional words to look for in the page"}},
            "required": ["title"]}}},
    {"type": "function", "function": {
        "name": "wikidata",
        "description": "Look up hard facts about one thing (person, place, film, event) on Wikidata: dates, counts, "
                       "heights, who holds an office, winners. Give `property` to filter, e.g. 'height' or 'head of government'.",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string", "description": "name of the thing, e.g. 'Mount Kilimanjaro'"},
            "property": {"type": "string", "description": "optional filter on the fact name"}},
            "required": ["entity"]}}},
]


def call_tool(name, args):
    fn = TOOL_FNS.get(name)
    if fn is None:
        return f"error: no tool called '{name}'. Tools: search, read_page, wikidata"
    if not isinstance(args, dict):
        return "error: arguments must be a JSON object"
    try:
        return fn(**args)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


# ---------------------------------------------------------------- prompts

DRAFT_SYSTEM = (f"You are a helpful assistant. Today's date is {TODAY}. You can look things up with the tools "
                "(Wikipedia search, reading Wikipedia pages, Wikidata facts). Answer the user briefly and directly.")

FORMAT = ("End your reply with exactly these two lines:\n"
          "VERDICT: RIGHT or WRONG\n"
          "FINAL ANSWER: <the answer the user should get>")

REVIEW = {
    "plain": (f"Today's date is {TODAY}. You can look things up with the tools.",
              "Review this question and answer and tell me if it is good and right.\n\n"
              "QUESTION: {q}\n\nANSWER: {a}\n\n" + FORMAT),
    "strict": (f"You are a strict fact-checker. Today's date is {TODAY}. An assistant wrote the answer below and it "
               "may well be wrong or out of date. Your job is to find what is wrong. Do not trust the answer or your "
               "own memory: check every factual claim with the tools before deciding. Anything about 'current' or "
               "'latest' must be checked against today's date. If it is wrong, give the corrected answer.",
               "QUESTION: {q}\n\nANSWER TO CHECK: {a}\n\n" + FORMAT),
}


# ---------------------------------------------------------------- parsing model replies

TAGGED = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
PY_TAG = re.compile(r"<\|python_tag\|>\s*(\{.*\})", re.S)


def _as_call(j):
    if not isinstance(j, dict):
        return None
    name = j.get("name") or (j.get("function") or {}).get("name")
    args = j.get("arguments", j.get("parameters", (j.get("function") or {}).get("arguments", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return (name, args) if name else None


def _bare_json_objects(s):
    """Top-level {...} objects in s (Llama 3.2 writes tool calls as bare JSON)."""
    out, depth, start = [], 0, None
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                out.append(s[start:i + 1])
    return out


def parse(reply):
    """-> (visible text, [(name, args) | (None, error)])"""
    calls = []
    raws = TAGGED.findall(reply) or PY_TAG.findall(reply)
    text = TAGGED.sub("", reply).split("<tool_call>")[0]
    if not raws:
        stripped = reply.strip()
        objs = _bare_json_objects(stripped)
        # only treat bare JSON as a tool call if the reply is (nearly) nothing but tool-call JSON
        if objs and len("".join(objs)) > 0.8 * len(re.sub(r"[\s;,]", "", stripped)):
            cand = []
            for o in objs:
                try:
                    c = _as_call(json.loads(o))
                except json.JSONDecodeError:
                    c = None
                if c and c[0] in TOOL_FNS:
                    cand.append(c)
            if cand:
                return "", cand
    for raw in raws:
        try:
            c = _as_call(json.loads(raw))
            calls.append(c or (None, "error: tool call needs a name"))
        except json.JSONDecodeError:
            calls.append((None, "error: couldn't read that tool call as JSON"))
    if "<tool_call>" in reply and "</tool_call>" not in reply:
        calls.append((None, "error: tool call was cut off"))
    return text.strip(), calls


VERDICT = re.compile(r"VERDICT\s*:?\s*\**\s*(RIGHT|WRONG|CORRECT|INCORRECT)", re.I)
FINAL = re.compile(r"FINAL ANSWER\s*:?\s*\**\s*(.+)", re.I | re.S)


def read_review(text):
    v = VERDICT.findall(text)
    verdict = None
    if v:
        verdict = "right" if v[-1].lower() in ("right", "correct") else "wrong"
    f = FINAL.findall(text)
    final = f[-1].strip() if f else None
    return verdict, final


def is_correct(q, text):
    return bool(text) and any(re.search(p, text, re.I) for p in q["accept"])


# ---------------------------------------------------------------- generation loop

def load(model_key):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    name = MODELS[model_key]
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dt = torch.float16 if dev == "cuda" else torch.float32
    try:
        model = AutoModelForCausalLM.from_pretrained(name, dtype=dt)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=dt)
    return tok, model.to(dev).eval(), dev


def run_convs(convs, tok, model, dev, log):
    import torch

    def render(c):
        return tok.apply_chat_template(c["msgs"], tools=TOOLS, tokenize=False, add_generation_prompt=True,
                                       enable_thinking=False)

    t0, step = time.time(), 0
    while True:
        active = [c for c in convs if not c["done"]]
        if not active:
            break
        step += 1
        texts = [(c, render(c)) for c in active]
        lens = {id(c): len(tok(t, add_special_tokens=False)["input_ids"]) for c, t in texts}
        for c, _ in texts:
            if lens[id(c)] > MAX_CONTEXT:
                c["done"], c["end"] = True, "context full"
        texts = sorted([(c, t) for c, t in texts if not c["done"]], key=lambda x: lens[id(x[0])])
        i = 0
        while i < len(texts):
            bs = max(1, min(12, 36000 // (lens[id(texts[i][0])] + MAX_NEW)))
            chunk = texts[i:i + bs]
            i += bs
            batch = tok([t for _, t in chunk], return_tensors="pt", padding=True, add_special_tokens=False).to(dev)
            with torch.no_grad():
                g = model.generate(**batch, max_new_tokens=MAX_NEW, do_sample=True, temperature=0.7, top_p=0.8,
                                   top_k=20, pad_token_id=tok.pad_token_id)
            replies = tok.batch_decode(g[:, batch["input_ids"].shape[1]:], skip_special_tokens=False)
            for (c, _), reply in zip(chunk, replies):
                for sp in (tok.eos_token, tok.pad_token, "<|im_end|>", "<|eot_id|>", "<|eom_id|>", "<|endoftext|>"):
                    if sp:
                        reply = reply.replace(sp, "")
                reply = re.sub(r"<think>\s*</think>", "", reply).strip()
                c["turns"] += 1
                c["raw"].append(reply)
                text, calls = parse(reply)
                if not calls:
                    c["msgs"].append({"role": "assistant", "content": reply})
                    c["final"], c["done"], c["end"] = reply, True, "answered"
                    continue
                good = [(n, a) for n, a in calls if n is not None]
                c["msgs"].append({"role": "assistant", "content": text,
                                  "tool_calls": [{"type": "function", "function": {"name": n, "arguments": a}}
                                                 for n, a in good]})
                c["pending"] = calls
            with cf.ThreadPoolExecutor(4) as ex:
                for c, _ in chunk:
                    if c["done"]:
                        continue
                    futs = []
                    for n, a in c.pop("pending"):
                        if n is None:
                            futs.append((n, a, None))
                        else:
                            c["tools"].append({"name": n, "args": a})
                            futs.append((n, a, ex.submit(call_tool, n, a)))
                    for n, a, f in futs:
                        c["msgs"].append({"role": "tool", "name": n or "error", "content": a if f is None else f.result()})
                    if c["turns"] >= MAX_TURNS:
                        c["done"], c["end"] = True, "turn limit"
        left = sum(not c["done"] for c in convs)
        log(f"  step {step}: {len(convs) - left}/{len(convs)} done ({time.time() - t0:.0f}s)")
    for c in convs:
        if c["final"] is None:  # turn limit / context full: whatever text it last wrote
            texts = [m["content"] for m in c["msgs"] if m["role"] == "assistant" and m.get("content")]
            c["final"] = texts[-1] if texts else ""


def new_conv(system, user, **meta):
    return dict(meta, msgs=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                done=False, end="", turns=0, raw=[], tools=[], final=None)


def worker(model_key, gpu, tag):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)

    def log(m):
        print(f"[{model_key}] {m}", flush=True)

    t0 = time.time()
    tok, model, dev = load(model_key)
    log(f"loaded {MODELS[model_key]} on {dev} in {time.time() - t0:.0f}s")
    qs = QUESTIONS[:2] if tag == "pilot" else QUESTIONS
    samples = 1 if tag == "pilot" else SAMPLES

    drafts = [new_conv(DRAFT_SYSTEM, q["q"], qid=q["id"], sample=s) for s in range(samples) for q in qs]
    log(f"drafts: {len(drafts)}")
    run_convs(drafts, tok, model, dev, log)
    byid = {q["id"]: q for q in qs}
    for d in drafts:
        d["correct"] = is_correct(byid[d["qid"]], d["final"])

    reviews = []
    for d in drafts:
        for style, (sys_p, user_p) in REVIEW.items():
            reviews.append(new_conv(sys_p, user_p.format(q=byid[d["qid"]]["q"], a=d["final"] or "(no answer)"),
                                    qid=d["qid"], sample=d["sample"], style=style, draft_correct=d["correct"],
                                    source="own"))
    # planted: a known-wrong answer, so every model's catch rate is measured even if its own drafts are all right/wrong
    for s in range(samples):
        for q in qs:
            for style, (sys_p, user_p) in REVIEW.items():
                reviews.append(new_conv(sys_p, user_p.format(q=q["q"], a=q["planted_wrong"]), qid=q["id"], sample=s,
                                        style=style, draft_correct=False, source="planted"))
    log(f"reviews: {len(reviews)}")
    run_convs(reviews, tok, model, dev, log)
    for r in reviews:
        r["verdict"], r["final_answer"] = read_review(r["final"])
        # if it gave no FINAL ANSWER line, the user still gets the draft (if it said right) or nothing usable
        r["final_correct"] = is_correct(byid[r["qid"]], r["final_answer"]) if r["final_answer"] else (
            r["draft_correct"] if r["verdict"] == "right" else False)

    out = {"model": MODELS[model_key], "key": model_key, "tag": tag, "seconds": round(time.time() - t0),
           "drafts": drafts, "reviews": reviews}
    pathlib.Path(f"results_{tag}_{model_key}.json").write_text(json.dumps(out, indent=1, default=str))
    dc = sum(d["correct"] for d in drafts)
    own = [r for r in reviews if r["source"] == "own"]
    log(f"== {tag}: drafts correct {dc}/{len(drafts)}; " + "; ".join(
        f"{s} final correct {sum(r['final_correct'] for r in own if r['style'] == s)}/{len(drafts)}"
        for s in REVIEW) + "; planted caught " + ", ".join(
        f"{s} {sum(r['verdict'] == 'wrong' for r in reviews if r['source'] == 'planted' and r['style'] == s)}"
        f"/{len(qs) * samples}" for s in REVIEW) + f" ({out['seconds']}s)")


# ---------------------------------------------------------------- report

def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def report(pattern="results_full_*.json"):
    files = sorted(glob.glob(pattern)) or sorted(glob.glob("results_*.json"))
    lines = ["# Draft -> fact-check: results", "",
             f"{len(QUESTIONS)} questions, {SAMPLES} sampled drafts each, tools = Wikipedia search, Wikipedia page, "
             f"Wikidata. Each draft is reviewed twice by the same model in a fresh chat: **plain** (Keal's wording) "
             f"and **strict** (fact-checker, assume it's wrong).", "",
             "**Own drafts** = the model reviews its own answers. **Planted** = it reviews a known-wrong answer per "
             "question (e.g. 'The capital of Australia is Sydney').", "",
             "| model | draft right | review | caught wrong own drafts | false alarms on right drafts | final right | fixed (wrong->right) | broke (right->wrong) | planted caught | planted fixed | no verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    per_q = {}
    for f in files:
        r = json.loads(pathlib.Path(f).read_text())
        D = r["drafts"]
        dc = sum(d["correct"] for d in D)
        for style in REVIEW:
            R = [x for x in r["reviews"] if x["style"] == style and x.get("source", "own") == "own"]
            P = [x for x in r["reviews"] if x["style"] == style and x.get("source") == "planted"]
            wrong = [x for x in R if not x["draft_correct"]]
            right = [x for x in R if x["draft_correct"]]
            lines.append("| " + " | ".join([
                r["model"], pct(dc, len(D)), style,
                pct(sum(x["verdict"] == "wrong" for x in wrong), len(wrong)),
                pct(sum(x["verdict"] == "wrong" for x in right), len(right)),
                pct(sum(x["final_correct"] for x in R), len(R)),
                pct(sum(x["final_correct"] for x in wrong), len(wrong)),
                pct(sum(not x["final_correct"] for x in right), len(right)),
                pct(sum(x["verdict"] == "wrong" for x in P), len(P)),
                pct(sum(x["final_correct"] for x in P), len(P)),
                pct(sum(x["verdict"] is None for x in R + P), len(R + P))]) + " |")
        for d in D:
            per_q.setdefault(d["qid"], {}).setdefault(r["key"], []).append("✓" if d["correct"] else "✗")
        tools = [t["name"] for x in D for t in x["tools"]]
        lines.append(f"| | tool calls per draft: {len(tools) / max(1, len(D)):.1f} "
                     f"({', '.join(f'{n} {tools.count(n)}' for n in TOOL_FNS)}) | | | | | | | | | |")
    lines += ["", "## Drafts per question (✓ right / ✗ wrong, one mark per sample)", "",
              "| question | " + " | ".join(sorted({k for v in per_q.values() for k in v})) + " |",
              "|---|" + "---|" * len({k for v in per_q.values() for k in v})]
    keys = sorted({k for v in per_q.values() for k in v})
    for q in QUESTIONS:
        if q["id"] in per_q:
            lines.append(f"| {q['id']} | " + " | ".join("".join(per_q[q['id']].get(k, [])) for k in keys) + " |")
    pathlib.Path("RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def check():
    print(tool_search("Emma Stone filmography")[:400])
    print(tool_read_page("Pluto", find="discovered")[:400])
    print(tool_wikidata("Mount Kilimanjaro", "elevation")[:400])
    # parser checks
    assert parse('<tool_call>\n{"name": "search", "arguments": {"query": "x"}}\n</tool_call>')[1] == [("search", {"query": "x"})]
    assert parse('{"name": "search", "parameters": {"query": "x"}}')[1] == [("search", {"query": "x"})]
    assert parse('The answer is {not json} 1930.')[1] == []
    assert read_review("blah\nVERDICT: WRONG\nFINAL ANSWER: Canberra") == ("wrong", "Canberra")
    print("check ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "worker", "report"])
    ap.add_argument("--model", default="qwen3")
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--tag", default="full")
    a = ap.parse_args()
    {"check": check, "report": report}.get(a.cmd, lambda: worker(a.model, a.gpu, a.tag))()
