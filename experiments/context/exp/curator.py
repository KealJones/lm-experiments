"""Context-curator test. One function of a working game is emptied; the model must rewrite it.
Arms differ only in which context items go into that one prompt:
  pinned   - goal + step only
  all      - every item, in menu order, until the context budget is used
  overlap  - top 4 items by word overlap with goal+step (like Squiggle's current smart context)
  reranker - top 4 items by Qwen3-Reranker-0.6B score (also records the scores)
  curator  - a hidden Qwen3 0.6B turn (thinking off) picks item numbers from a menu
Success = the repaired game scores 5/5 in the sandbox. Thinking is off for the fill turns.
usage: python3 curator.py <out.json> [trials]
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from core import *
import llama_cpp
from llama_cpp import Llama

OUT = sys.argv[1]; TRIALS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
GOOD = open(f"{S}/t/good.ts").read()
WORK = f"{S}/exp/curator_ws"; os.makedirs(WORK, exist_ok=True)
TARGETS = ["winner", "minimax", "bestMove", "render", "play"]
ITEM_BUDGET = 2200
RERANK = f"{S}/model/qwen3-reranker-0.6b-q8.gguf"

NOTES = """- board is a Cell[] of 9 cells, index = row*3 + col; '' means empty
- the human is 'X', the computer is 'O'
- LINES lists the 8 winning lines as index triples
- winner(b) returns 'X', 'O', 'draw' or null (game not over)
- minimax(b, turn) scores a position: +1 if O wins, -1 if X wins, 0 draw; it tries every empty cell
- bestMove(b) returns the index of the best empty cell for 'O'
- render() rebuilds #app: score line, 9 buttons with class 'cell', and the #restart button
- play(i) places X at i, lets the computer answer, updates score, then calls render()"""
CSS = """#app { display: grid; grid-template-columns: repeat(3, 80px); gap: 6px; }
.cell { width: 80px; height: 80px; font-size: 40px; border-radius: 8px; border: 2px solid #ccc; background: #fff; }
.cell:hover { background: #f4f4f4; }
#score { grid-column: 1 / 4; font: 600 18px system-ui; text-align: center; }
#restart { grid-column: 1 / 4; padding: 8px; border-radius: 6px; background: #3b82f6; color: white; }
@media (prefers-color-scheme: dark) { .cell { background: #222; color: #eee; border-color: #444; } }"""
WEATHER = 'get_weather(city: string) -> { "city": string, "temp_f": number, "conditions": string, "wind_mph": number }. Calls the Brightleaf weather proxy; cached for 10 minutes. Returns an error object if the city is unknown.'
CHAT = "Earlier in this chat the user said: 'can the cells be a bit darker in dark mode? and maybe round the corners more' and the assistant changed .cell border-radius from 4px to 8px."

def fn_spans(src):
    o = outline_src(src)
    return {f["name"]: f for f in o["functions"]}, o

def outline_src(src):
    p = f"{WORK}/tmp.ts"; open(p, "w").write(src); return outline(p)

def build(target):
    fns, o = fn_spans(GOOD)
    f = fns[target]
    broken = GOOD[:f["bodyStart"]] + "{\n  // TODO\n}" + GOOD[f["bodyEnd"]:]
    ws = Workspace(f"{WORK}/{target}"); ws.write(broken)
    tail = "\n".join(broken.split("\n")[-15:])
    head_decls = "\n".join(l for l in broken.split("\n") if re.match(r"(type|let|const)\s", l) and "=>" not in l)
    items = [("Outline of game.ts: types, variables and function signatures", ws.outline_text()),
             ("Brightleaf company style guide", FILLER.split("Office information")[0][-900:]),
             ("Full source of game.ts", broken)]
    for name, g in fns.items():
        if name != target: items.append((f"Code of function {name}", GOOD[g["nodeStart"]:g["end"]]))
    items += [("Brightleaf pricing and office hours", FILLER.split("Office information:")[1].split("Holiday")[0][:700]),
              ("Top-level types and variables of game.ts", head_decls),
              ("Docs for the get_weather tool", WEATHER),
              ("NOTES.md (project notes)", NOTES),
              ("page.css (styles for the page)", CSS),
              ("Last 15 lines of game.ts", tail),
              ("Earlier chat about dark-mode colors", CHAT),
              ("Brightleaf holiday schedule", "Offices are closed on New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving and the day after, and December 24 through January 1.")]
    return ws, f, items

def step_text(f): return f"Write the complete code for the function `{f['sig']}`" + (f" ({f['comment']})" if f.get("comment") else "") + ". It is currently empty in game.ts."

def overlap_pick(query, items, k=4):
    q = set(re.findall(r"[a-z]{3,}", query.lower()))
    sc = [(len(q & set(re.findall(r"[a-z]{3,}", (d + " " + c).lower()))), i) for i, (d, c) in enumerate(items)]
    return [i for s, i in sorted(sc, key=lambda x: (-x[0], x[1]))[:k]]

_rr = {}
def rerank_scores(query, items):
    if "m" not in _rr:
        _rr["m"] = Llama(model_path=RERANK, embedding=True, pooling_type=llama_cpp.LLAMA_POOLING_TYPE_RANK, n_ctx=2048, n_threads=2, verbose=False)
    m = _rr["m"]
    pre = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
    suf = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    out = []
    for d, c in items:
        doc = (d + ":\n" + c)[:2500]
        s = m.embed(pre + f"<Instruct>: Is this piece of information needed to do the task?\n<Query>: {query}\n<Document>: {doc}" + suf)
        out.append(float(s[0] if isinstance(s, list) else s))
    return out

def curator_pick(goal, step, items, seed, log):
    menu = "\n".join(f"{i+1}. {d}" for i, (d, _) in enumerate(items))
    user = (f"Someone is about to do this task.\n{goal}\nStep: {step}\n\nThese pieces of information are available:\n{menu}\n\n"
            "Which pieces does that person need to do this step well? Answer with only the numbers, comma separated.")
    p = f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    r = model().create_completion(p, max_tokens=60, seed=seed, stop=["<|im_end|>"], **SAMPLE_OFF)
    txt = r["choices"][0]["text"]
    picks = []
    for n in re.findall(r"\d+", txt):
        i = int(n) - 1
        if 0 <= i < len(items) and i not in picks: picks.append(i)
    log["curator_reply"] = txt.strip()
    return picks

def fill(ws, f, goal, step, chosen, items, seed):
    parts, used = [], 0
    for i in chosen:
        d, c = items[i]
        t = tok(c)
        if used + t > ITEM_BUDGET: continue
        parts.append(f"## {d}\n{c}"); used += t
    user = goal + "\n\n" + "\n\n".join(parts) + ("\n\n" if parts else "") + "Step: " + step + " Reply with only that whole function in one TypeScript code block."
    p = render(FILLER, user) + "<think>\n\n</think>\n\n"
    r = model().create_completion(p, max_tokens=max(64, N_CTX - tok(p)), seed=seed, stop=["<|im_end|>"], **SAMPLE_OFF)
    out = r["choices"][0]["text"]
    ws.write(re.sub(r"\{\n  // TODO\n\}", "{\n  // TODO\n}", ws.read()))
    base = ws.read()
    code = latest_code(out)
    ok_fn = bool(code and re.search(r"\bfunction\s+" + f["name"] + r"\b|\b" + f["name"] + r"\s*=", code))
    if ok_fn: ws.replace_function(f["name"], code)
    sc = score(ws.game)
    ws.write(base)  # restore the broken file for the next arm
    return {"prompt_tokens": tok(p), "items_used": len(parts), "item_tokens": used, "fn_written": ok_fn,
            "points": sc["points"], "success": sc["points"] == 5, "ts_errors": sc["ts_errors"], "output": out[:3000]}

results = json.load(open(OUT)) if os.path.exists(OUT) else []
done = {(r["target"], r["trial"]) for r in results}
for target in TARGETS:
    ws, f, items = build(target)
    goal, step = GOAL, step_text(f)
    query = goal + " Step: " + step
    rr = rerank_scores(query, items)
    for trial in range(TRIALS):
        if (target, trial) in done: continue
        seed = 1000 + trial
        rec = {"target": target, "trial": trial, "menu": [d for d, _ in items], "rerank_scores": [round(x, 3) for x in rr]}
        cur = curator_pick(goal, step, items, seed, rec)
        picks = {"pinned": [], "all": list(range(len(items))), "overlap": overlap_pick(query, items),
                 "reranker": sorted(range(len(items)), key=lambda i: -rr[i])[:4], "curator": cur}
        rec["picks"] = picks; rec["arms"] = {}
        for arm, ch in picks.items():
            t = time.time()
            rec["arms"][arm] = {**fill(ws, f, goal, step, ch, items, seed), "secs": round(time.time() - t, 1)}
            a = rec["arms"][arm]
            print(f"{target} t{trial} {arm:8} pts={a['points']} ok={a['success']} items={a['items_used']} ({a['item_tokens']} tok) {a['secs']}s", flush=True)
        results.append(rec); json.dump(results, open(OUT, "w"), indent=1)
print("ALL DONE", flush=True)
