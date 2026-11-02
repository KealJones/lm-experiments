"""Normal coding-agent test: Qwen3 0.6B, 32K window, plain system prompt, real tools, full conversation history.
Tasks:
  build  - write the tic-tac-toe game into game.ts from scratch
  fix:<fn> - one function of the working game is emptied to // TODO; fix it (it can grep/read the rest)
usage: python3 agent.py <out.json> <think on|off> <tries> <task> [task...]
"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from core import S, sandbox, score, outline, strip_think
from llama_cpp import Llama

OUT, THINK, TRIES, TASKS = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
N_CTX, MAX_STEPS, MAX_SECS, MAX_GEN = 32768, 40, 20 * 60, 4096
GOOD = open(f"{S}/t/good.ts").read()
ROOT = f"{S}/exp/agent_ws"

llm = Llama(model_path=f"{S}/model/qwen3-0.6b-q8.gguf", n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)
def tok(s): return len(llm.tokenize(s.encode(), add_bos=False, special=True))

SYSTEM = ("You are a coding assistant working in a project folder. Use the tools to look at files, make changes, "
          "and check your work with run_game. When the task is complete and run_game shows it working, call finish.")
TOOLS = [
 ("ls", "List files in the project folder.", {}),
 ("grep", "Search files for a regular expression. Returns matching lines as path:line: text.", {"pattern": "string", "path": "string (optional file or folder, default whole project)"}),
 ("read_file", "Read a file with line numbers. Optional start and end lines.", {"path": "string", "start": "integer (optional)", "end": "integer (optional)"}),
 ("write_file", "Create or overwrite a file.", {"path": "string", "content": "string"}),
 ("edit_file", "Replace an exact piece of text in a file. old must appear exactly once.", {"path": "string", "old": "string", "new": "string"}),
 ("run_game", "Type-check game.ts and run it in a fake browser page (it clicks 5 board cells). Returns errors and what happened on the page.", {}),
 ("finish", "Call when the task is complete.", {"summary": "string"}),
]
def schema(n, d, p):
    req = [k for k, v in p.items() if "optional" not in v]
    return {"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object",
            "properties": {k: {"type": v.split(" ")[0]} for k, v in p.items()}, "required": req}}}
SYS_FULL = (SYSTEM + "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
            "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n" +
            "\n".join(json.dumps(schema(*t)) for t in TOOLS) +
            "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
            "<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>")

README = """# Tic tac toe

Browser tic tac toe in TypeScript. index.html loads game.ts, which draws everything inside <div id="app">.
Run `run_game` to type-check and try it.
"""
INDEX = '<!doctype html>\n<html>\n<head><link rel="stylesheet" href="styles.css"></head>\n<body>\n  <div id="app"></div>\n  <script src="game.js"></script>\n</body>\n</html>\n'
CSS = "#app { display: grid; grid-template-columns: repeat(3, 80px); gap: 6px; }\n.cell { width: 80px; height: 80px; font-size: 40px; }\n#score, #restart { grid-column: 1 / 4; }\n"
PKG = '{\n  "name": "tic-tac-toe",\n  "version": "1.0.0",\n  "scripts": { "build": "tsc game.ts" },\n  "devDependencies": { "typescript": "^5.6.0" }\n}\n'

def setup(task, d):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for n, c in [("README.md", README), ("index.html", INDEX), ("styles.css", CSS), ("package.json", PKG)]:
        open(f"{d}/{n}", "w").write(c)
    if task == "build":
        open(f"{d}/game.ts", "w").write("")
        user = ("Write me a TypeScript tic tac toe game for the browser: a clickable 3x3 board in the DOM, a computer opponent "
                "that uses minimax so it never loses, a score counter, and a restart button. Put it in game.ts.")
    else:
        fn = task.split(":")[1]
        p = f"{d}/game.ts"; open(p, "w").write(GOOD)
        f = next(x for x in outline(p)["functions"] if x["name"] == fn)
        open(p, "w").write(GOOD[:f["bodyStart"]] + "{\n  // TODO\n}" + GOOD[f["bodyEnd"]:])
        user = f"The game in game.ts is broken: the function `{fn}` is empty (it just says // TODO). Fix it so the game works."
    return user

def safe(d, path):
    p = os.path.normpath(os.path.join(d, str(path or "").lstrip("/")))
    if not p.startswith(d): raise ValueError("path outside the project")
    return p

def call(d, name, a, state):
    a = a if isinstance(a, dict) else {}
    try:
        if name == "ls":
            return "\n".join(f"{n} ({os.path.getsize(os.path.join(d, n))} bytes)" for n in sorted(os.listdir(d)) if not n.startswith("."))
        if name == "grep":
            rx = re.compile(str(a.get("pattern", "")))
            base = safe(d, a.get("path") or "."); files = [base] if os.path.isfile(base) else [os.path.join(base, n) for n in sorted(os.listdir(base))]
            hits = []
            for f in files:
                if not os.path.isfile(f): continue
                for i, l in enumerate(open(f, errors="ignore").read().split("\n"), 1):
                    if rx.search(l): hits.append(f"{os.path.relpath(f, d)}:{i}: {l.strip()[:160]}")
            return "\n".join(hits[:40]) + (f"\n... {len(hits) - 40} more" if len(hits) > 40 else "") if hits else "No matches."
        if name == "read_file":
            lines = open(safe(d, a.get("path"))).read().split("\n")
            s = max(1, int(a.get("start") or 1)); e = min(len(lines), int(a.get("end") or len(lines)))
            out = "\n".join(f"{i}: {lines[i-1]}" for i in range(s, e + 1))
            return out[:6000] + ("\n... (truncated, use start/end)" if len(out) > 6000 else "")
        if name == "write_file":
            open(safe(d, a.get("path")), "w").write(str(a.get("content", ""))); return f"Wrote {a.get('path')}."
        if name == "edit_file":
            p = safe(d, a.get("path")); src = open(p).read(); old = str(a.get("old", ""))
            n = src.count(old) if old else 0
            if n != 1: return f"edit_file failed: old text found {n} times (must be exactly 1)."
            open(p, "w").write(src.replace(old, str(a.get("new", "")))); return "Edited."
        if name == "run_game":
            state["runs"] += 1
            rep = sandbox(f"{d}/game.ts")
            return "\n".join(l for l in rep.split("\n") if not l.startswith("SCORE_MARKS"))[:2500]
        if name == "finish":
            state["finished"] = True; return "OK."
        return f"Unknown tool {name}."
    except Exception as e:
        return f"Tool error: {e}"

def run(task, trial):
    d = f"{ROOT}/{THINK}-{task.replace(':', '_')}-t{trial}"
    user = setup(task, d)
    prompt = f"<|im_start|>system\n{SYS_FULL}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    state = {"finished": False, "runs": 0}; steps = []; t0 = time.time(); end = "max steps"
    kw = (dict(temperature=0.6, top_p=0.95, top_k=20, presence_penalty=0.5) if THINK == "on" else
          dict(temperature=0.7, top_p=0.8, top_k=20, presence_penalty=0.5))
    for step in range(MAX_STEPS):
        if time.time() - t0 > MAX_SECS: end = "time limit"; break
        if THINK == "off" and not prompt.endswith("<think>\n\n</think>\n\n"): prompt += "<think>\n\n</think>\n\n"
        room = N_CTX - tok(prompt)
        if room < 256: end = "context full"; break
        r = llm.create_completion(prompt, max_tokens=min(MAX_GEN, room), seed=1000 * trial + step, stop=["<|im_end|>", "</tool_call>"], **kw)
        out, fin = r["choices"][0]["text"], r["choices"][0]["finish_reason"]
        rec = {"out": out[-2500:], "gen": r["usage"]["completion_tokens"], "ctx": tok(prompt) + r["usage"]["completion_tokens"]}
        steps.append(rec)
        m = re.search(r"<tool_call>\s*(\{.*\})\s*$", out, re.S)
        if not m:
            end = "ran out of tokens mid-reply" if fin == "length" else "replied without a tool call"; break
        try:
            c = json.loads(m.group(1), strict=False); name, args = c.get("name"), c.get("arguments") or {}
            res = call(d, name, args, state)
        except Exception as e:
            name, res = "?", f"Could not parse the tool call JSON: {e}"
        rec["tool"], rec["result"] = name, res[:600]
        prompt += out + "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n" + res + "\n</tool_response><|im_end|>\n<|im_start|>assistant\n"
        if state["finished"]: end = "called finish"; break
    sc = score(f"{d}/game.ts")
    tools = [s.get("tool") for s in steps if s.get("tool")]
    return {"task": task, "think": THINK, "trial": trial, "end": end, "steps": len(steps), "secs": round(time.time() - t0),
            "max_ctx": max((s["ctx"] for s in steps), default=0), "tools": tools, "run_game_calls": state["runs"],
            "points": sc["points"], "success": sc["points"] == 5, "ts_errors": sc["ts_errors"],
            "parts": {k: sc[k] for k in ["compiles", "runs", "board", "clicks_work", "computer_moves"]},
            "final_reply": strip_think(steps[-1]["out"])[:600] if steps else "", "log": steps}

results = json.load(open(OUT)) if os.path.exists(OUT) else []
done = {(r["task"], r["trial"]) for r in results}
for trial in range(TRIES):
    for task in TASKS:
        if (task, trial) in done: continue
        r = run(task, trial); results.append(r); json.dump(results, open(OUT, "w"), indent=1)
        print(f"{THINK} {task:13} t{trial} pts={r['points']} end={r['end']} steps={r['steps']} ctx={r['max_ctx']} "
              f"run_game={r['run_game_calls']} {r['secs']}s tools={r['tools'][:12]}", flush=True)
print("ALL DONE", flush=True)
