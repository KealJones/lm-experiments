"""Granularity test: how big a piece should each turn write?
Same 5 functions as the curator test (one function of a working game emptied, rewrite it).
Every method gets the same brief: objective, signature, list of what exists (types, variables, function signatures).
  whole - one turn writes the whole function
  lines - each turn writes the next 1-3 lines (sees: brief + locals so far + open blocks + last 3 lines); says DONE to stop
  blocks - top-down stepwise refinement: each turn replaces one HOLE with <=5 lines; any block it opens gets a new
           /*HOLE: purpose*/ body for a later turn (sees: brief + the current function with holes)
Thinking: off, or on capped at THINK tokens per turn. Success = repaired game scores 5/5.
usage: python3 granular.py <out.json> <think on|off> <trials> [methods...]
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from core import *

OUT, THINK, TRIALS = sys.argv[1], sys.argv[2], int(sys.argv[3])
METHODS = sys.argv[4:] or ["whole", "lines", "blocks"]
THINK_TOK = 300
GOOD = open(f"{S}/t/good.ts").read()
WORK = f"{S}/exp/gran_ws"; os.makedirs(WORK, exist_ok=True)
OBJ = {
 "winner": "Return 'X' or 'O' if that mark fills any of the 8 lines in LINES, 'draw' if every cell is filled, otherwise null.",
 "minimax": "Score the position for O by trying every empty cell for `turn` recursively: +1 if O wins, -1 if X wins, 0 for a draw. O maximizes, X minimizes.",
 "bestMove": "Return the index of the empty cell that gives O the highest minimax score.",
 "render": "Rebuild #app: a #score div saying 'You N - Computer N', 9 buttons with class 'cell' showing each board mark that call play(i) when clicked, and a #restart button that clears the board and re-renders.",
 "play": "If cell i is empty and nobody has won: place X, then if the game isn't over place O at bestMove, add a point to the winner's score, then call render().",
}
MAX_TURNS = {"lines": 40, "blocks": 30}
if os.environ.get("ONLY"): OBJ = {k: OBJ[k] for k in os.environ["ONLY"].split(",")}

def gen(user, seed, max_out=400):
    m = model()
    p = render(FILLER, user)
    t0 = time.time()
    if THINK == "off":
        head, kw = "<think>\n\n</think>\n\n", SAMPLE_OFF
    else:
        kw = SAMPLE
        r = m.create_completion(p, max_tokens=THINK_TOK, seed=seed, stop=["</think>", "<|im_end|>"], **kw)
        head = r["choices"][0]["text"] + "\n</think>\n\n"
    p2 = p + head
    r = m.create_completion(p2, max_tokens=min(max_out, N_CTX - tok(p2)), seed=seed, stop=["<|im_end|>"], **kw)
    return strip_think(head + r["choices"][0]["text"]), tok(p2), time.time() - t0

def code_lines(text):
    t = text.strip()
    m = re.search(r"```[a-zA-Z]*\n(.*?)(?:```|$)", t, re.S)
    if m: t = m.group(1)
    return [l.rstrip() for l in t.split("\n") if l.strip() and not l.strip().startswith("```")]

def strip_header(lines, name):
    if lines and re.match(r"\s*(export\s+)?(function\s+" + name + r"\b|(const|let|var)\s+" + name + r"\s*=|" + name + r"\s*\(.*\)\s*(:[^{]*)?\{\s*$)", lines[0]):
        lines = lines[1:]
        # drop the header's closing brace if the model wrote the whole function
        if lines and lines[-1].strip() == "}" and depth_after(lines) < 0: lines = lines[:-1]
    return lines

def setup(target):
    p = f"{WORK}/good.ts"; open(p, "w").write(GOOD)
    o = outline(p); f = next(x for x in o["functions"] if x["name"] == target)
    broken = GOOD[:f["bodyStart"]] + "{\n  // TODO\n}" + GOOD[f["bodyEnd"]:]
    ws = Workspace(f"{WORK}/{target}"); ws.write(broken)
    names = ["Types: " + "; ".join(t["text"] for t in o["types"])] if o["types"] else []
    names += ["Variables: " + "; ".join(v["decl"] for v in o["vars"])]
    names += ["Functions: " + "; ".join(x["sig"] for x in o["functions"] if x["name"] != target)]
    names += ["Element: #app"]
    brief = (GOAL + "\n\nYou are writing ONE function of game.ts.\nFunction: `" + f["sig"] + "`\nObjective: " + OBJ[target] +
             "\n\nWhat exists in game.ts:\n" + "\n".join(names))
    return ws, f, brief, broken

def finish(ws, f, broken, body_lines):
    head = GOOD[f["nodeStart"]:f["bodyStart"]]
    code = head + "{\n" + "\n".join("  " + l if not l.startswith("  ") else l for l in body_lines) + "\n}"
    ws.write(broken); ws.replace_function(f["name"], code)
    sc = score(ws.game); ws.write(broken)
    return code, sc

# ---------------------------------------------------------------- methods
def m_whole(ws, f, brief, broken, seed, log):
    out, ptok, secs = gen(brief + "\n\nWrite the complete function. Reply with only that whole function in one TypeScript code block.", seed, 900)
    log.append({"turn": 1, "prompt_tokens": ptok, "secs": round(secs, 1), "output": out[:1500]})
    code = latest_code(out) or ""
    m = re.search(r"\{(.*)\}\s*$", code, re.S)
    return [l for l in (m.group(1) if m else code).split("\n") if l.strip()], len(log)

def open_blocks(lines):
    stack = []
    for l in lines:
        s = re.sub(r"(['\"`]).*?\1", "", l)
        for ch in s:
            if ch == "{": stack.append(l.strip()[:60])
            elif ch == "}" and stack: stack.pop()
    return stack

def depth_after(lines):
    d = 0
    for l in lines:
        s = re.sub(r"(['\"`]).*?\1", "", l); d += s.count("{") - s.count("}")
    return d

def m_lines(ws, f, brief, broken, seed, log):
    body, rejected, nag = [], 0, ""
    for turn in range(1, MAX_TURNS["lines"] + 1):
        locals_ = re.findall(r"\b(?:const|let|var)\s+(\w+)", "\n".join(body)) + re.findall(r"for\s*\(\s*(?:const|let)\s*\[?([\w,\s]+)\]?\s+of", "\n".join(body))
        opn = open_blocks(body)
        last = "\n".join(body[-3:]) if body else "(nothing yet, this is the first line of the body)"
        user = (brief + "\n\nLocal variables declared so far: " + (", ".join(dict.fromkeys(x.strip() for x in locals_)) or "none") +
                "\nOpen blocks (innermost last): " + (" > ".join([f["sig"]] + opn)) +
                "\nLast lines written:\n" + last +
                "\n\nWrite the NEXT 1 to 3 lines of this function's body (no explanation, do not repeat earlier lines). "
                "Close open blocks with } when they are finished. If the function body is complete, reply with exactly DONE." + nag)
        out, ptok, secs = gen(user, seed + turn, 150)
        new = strip_header(code_lines(out), f["name"])
        ent = {"turn": turn, "prompt_tokens": ptok, "secs": round(secs, 1), "output": out[:400]}
        log.append(ent)
        nag = ""
        if not new or new[0].strip().upper().startswith("DONE"):
            still = open_blocks(body)
            if (still or not body) and rejected < 2:
                rejected += 1; ent["event"] = "DONE rejected"
                nag = ("\n\nNOT DONE: " + ("these blocks are still open: " + " > ".join(still) if still else "the body is still empty") +
                       ". Write the next lines.")
                continue
            ent["event"] = "DONE"; break
        recent = {l.strip() for l in body[-6:] if l.strip() not in ("}", "{", "};")}
        new = [l for l in new if l.strip() not in recent][:3]
        if not new: ent["event"] = "only repeated lines"; continue
        for l in new:
            if depth_after(body + [l]) < 0: ent["event"] = "closed function"; break
            body.append(l)
        if ent.get("event"): break
    d = depth_after(body)
    if d > 0: body += ["}"] * d; log.append({"note": f"auto-closed {d} open blocks"})
    return body, len([e for e in log if "turn" in e])

HOLE = re.compile(r"/\*\s*HOLE\s*:?\s*(.*?)\*/", re.S)
def m_blocks(ws, f, brief, broken, seed, log):
    fn = "/*HOLE: " + OBJ[f["name"]] + "*/"
    for turn in range(1, MAX_TURNS["blocks"] + 1):
        m = HOLE.search(fn)
        if not m: break
        purpose = m.group(1).strip()
        shown = fn[:m.start()] + "/*>>> HOLE TO FILL NOW <<<*/" + fn[m.end():]
        user = (brief + "\n\nThe function so far (HOLE comments are parts not written yet):\n```typescript\n" + GOOD[f["nodeStart"]:f["bodyStart"]] +
                "{\n" + shown + "\n}\n```\n\nWrite the code that replaces the marked hole. Its job: " + purpose +
                "\nRules: at most 5 lines. If you open a block (if/for/while/callback), do not write its inside: put "
                "/*HOLE: what this block should do*/ inside it and close it with }. Reply with only the code.")
        out, ptok, secs = gen(user, seed + turn, 250)
        new = strip_header(code_lines(out), f["name"])
        ent = {"turn": turn, "prompt_tokens": ptok, "secs": round(secs, 1), "purpose": purpose[:120], "output": out[:500]}
        log.append(ent)
        have = {l.strip() for l in fn.split("\n") if l.strip() not in ("}", "{", "};", "];", "]")}
        before = len(new)
        new = [l for l in new if l.strip() not in have]
        if len(new) < before: ent["dropped_repeats"] = before - len(new)
        if not [l for l in new if l.strip() not in ("}", "};", "];")]:
            ent["note"] = "only repeated code; hole closed"; fn = fn[:m.start()] + fn[m.end():]; continue
        root = purpose.split("Job: ", 1)[1].split(" Already written")[0] if purpose.startswith("continue from here") else purpose
        purpose = root
        if len(new) > 5:
            ent["note"] = f"cut {len(new)} lines to 5, rest becomes a continue-hole"
            new = new[:5] + ["/*HOLE: continue from here. Job: " + purpose[:200] + " Already written just above: " + new[4].strip()[:80] + "*/"]
        while new and depth_after(new) < 0 and new[-1].strip() == "}": new = new[:-1]
        rep = "\n".join(new)
        d = depth_after(new)
        if d > 0: rep += "\n" + "}" * d
        fn = fn[:m.start()] + rep + fn[m.end():]
    left = len(HOLE.findall(fn))
    if left: log.append({"note": f"{left} holes left unfilled at the turn limit"}); fn = HOLE.sub("", fn)
    return [l for l in fn.split("\n") if l.strip()], len([e for e in log if "turn" in e])

METHOD_FN = {"whole": m_whole, "lines": m_lines, "blocks": m_blocks}
results = json.load(open(OUT)) if os.path.exists(OUT) else []
done = {(r["method"], r["target"], r["trial"]) for r in results}
for trial in range(TRIALS):
    for target in OBJ:
        for meth in METHODS:
            if (meth, target, trial) in done: continue
            ws, f, brief, broken = setup(target)
            log, t = [], time.time()
            body, turns = METHOD_FN[meth](ws, f, brief, broken, 2000 + trial * 100, log)
            code, sc = finish(ws, f, broken, body)
            rec = {"method": meth, "think": THINK, "target": target, "trial": trial, "turns": turns, "secs": round(time.time() - t),
                   "points": sc["points"], "success": sc["points"] == 5, "ts_errors": sc["ts_errors"], "code": code, "log": log}
            results.append(rec); json.dump(results, open(OUT, "w"), indent=1)
            print(f"{THINK} {meth:6} {target:8} t{trial} pts={sc['points']} turns={turns} {rec['secs']}s", flush=True)
print("ALL DONE", flush=True)
