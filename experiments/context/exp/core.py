"""Shared harness for the context-resume experiments (Qwen3 0.6B, 4,096-token window)."""
import json, os, re, subprocess, time

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QWEN3 = f"{S}/model/qwen3-0.6b-q8.gguf"
CODER = f"{S}/model/qwen25-coder-0.5b-instruct-q8.gguf"
SBX, OUTLINE = f"{S}/sbx/run.mjs", f"{S}/sbx/outline.mjs"
N_CTX, THINK_CAP = 4096, 800
TASK = ("a TypeScript tic tac toe game for the browser: a clickable 3x3 board in the DOM, a computer "
        "opponent that uses minimax so it never loses, a score counter, and a restart button")
GOAL = "Goal: " + TASK[0].upper() + TASK[1:] + "."
FILLER = re.search(r'FILLER = """(.*?)"""', open(f"{S}/relay3.py").read(), re.S).group(1)

_models = {}
def model(path=QWEN3):
    from llama_cpp import Llama
    if path not in _models:
        _models.clear()
        _models[path] = Llama(model_path=path, n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)
    return _models[path]

def tok(s, path=QWEN3): return len(model(path).tokenize(s.encode(), add_bos=False, special=True))
def strip_think(s): return re.sub(r"<think>.*?(</think>|$)", "", s, flags=re.S).strip()
SAMPLE = dict(temperature=0.6, top_p=0.95, top_k=20, presence_penalty=0.5)
SAMPLE_OFF = dict(temperature=0.7, top_p=0.8, top_k=20, presence_penalty=0.5)  # Qwen's non-thinking settings

# ---------------------------------------------------------------- tools
JUNK = {
 "get_weather": ("Get the current weather for a city.", {"city": "string"}),
 "search_company_wiki": ("Search the Brightleaf internal wiki.", {"query": "string"}),
 "send_slack_message": ("Send a message to a Brightleaf Slack channel.", {"channel": "string", "text": "string"}),
}
TOOL_DEFS = {
 "run_typescript": ("Type-check and run TypeScript in a sandbox (fake browser DOM; it clicks 5 board cells). Returns type errors, runtime errors and what happened. Pass code, or omit it to run game.ts.", {"code": "string"}),
 "write_file": ("Overwrite game.ts with this content.", {"content": "string"}),
 "append_file": ("Append text to the end of game.ts (write the game in pieces of at most ~60 lines).", {"text": "string"}),
 "view_file": ("Show lines start..end of game.ts with line numbers.", {"start": "integer", "end": "integer"}),
 "edit_file": ("Replace one exact, unique piece of text in game.ts.", {"old": "string", "new": "string"}),
 "replace_function": ("Replace a whole top-level function in game.ts (by name) with new code for that function.", {"name": "string", "code": "string"}),
 "write_notes": ("Overwrite NOTES.md: what's done, what's next, key names and their types.", {"text": "string"}),
 "finish": ("Call when the game is complete and works.", {"summary": "string"}),
}
OPTIONAL = {"run_typescript": {"code"}, "view_file": {"start", "end"}, "finish": {"summary"}}

def tool_schema(name):
    desc, props = TOOL_DEFS.get(name) or JUNK[name]
    req = [p for p in props if p not in OPTIONAL.get(name, set())]
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {k: {"type": v} for k, v in props.items()}, "required": req}}}

def system_prompt(tools):
    s = FILLER
    if tools:
        names = list(tools) + list(JUNK)
        s += ("\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
              "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
              + "\n".join(json.dumps(tool_schema(n)) for n in names) +
              "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
              "<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>")
    return s

def sandbox(path, timeout=20):
    try:
        r = subprocess.run(["node", SBX, path], capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, env={**os.environ, "SCORE": "1"})
        return (r.stdout or r.stderr or "(no output)").strip()
    except subprocess.TimeoutExpired:
        return "Sandbox timeout: ran for more than 20 seconds (infinite loop?)."

def outline(path):
    if not os.path.exists(path) or not open(path).read().strip(): return None
    r = subprocess.run(["node", OUTLINE, path], capture_output=True, text=True, timeout=20)
    try: return json.loads(r.stdout)
    except Exception: return None

class Workspace:
    def __init__(self, d):
        self.d = d; os.makedirs(d, exist_ok=True)
        self.game, self.notes = f"{d}/game.ts", f"{d}/NOTES.md"
        for p in (self.game, self.notes):
            if not os.path.exists(p): open(p, "w").close()
        self.finished, self.n = False, 0
    def read(self): return open(self.game).read()
    def write(self, s): open(self.game, "w").write(s)

    def outline_text(self):
        o = outline(self.game)
        if not o: return "game.ts is empty."
        L = [f"game.ts: {o['lines']} lines"]
        if o["types"]: L += ["Types:"] + [f"- {t['text']}" for t in o["types"]]
        if o["vars"]: L += ["Variables:"] + [f"- {v['decl']}" + (f"  // {v['comment']}" if v['comment'] else "") for v in o["vars"]]
        if o["functions"]: L += ["Functions:"] + [f"- {f['sig']}" + ("  [TODO]" if f.get("todo") else "") + (f"  // {f['comment']}" if f['comment'] else "") for f in o["functions"]]
        if o["ids"]: L.append("Element ids: " + ", ".join("#" + i for i in o["ids"]))
        return "\n".join(L)
    def tail(self, n=25):
        lines = self.read().split("\n")
        start = max(0, len(lines) - n)
        return "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[start:], start))

    def replace_function(self, name, code):
        o = outline(self.game)
        f = next((f for f in (o or {}).get("functions", []) if f["name"] == name), None)
        src = self.read()
        if not f:
            self.write(src.rstrip() + "\n\n" + code.strip() + "\n"); return f"No function {name} found; appended it at the end."
        self.write(src[:f["nodeStart"]] + code.strip() + src[f["end"]:])
        return f"Replaced function {name}."

    def call(self, name, args):
        self.n += 1
        a = args if isinstance(args, dict) else {}
        try:
            if name == "run_typescript":
                if a.get("code"):
                    p = f"{self.d}/check_{self.n}.ts"; open(p, "w").write(str(a["code"]))
                else: p = self.game
                return sandbox(p)[:1000]
            if name == "write_file": self.write(str(a.get("content", ""))); return f"game.ts written ({self.read().count(chr(10))+1} lines)."
            if name == "append_file":
                open(self.game, "a").write(("" if self.read().endswith("\n") or not self.read() else "\n") + str(a.get("text", "")))
                return f"Appended. game.ts now has {self.read().count(chr(10))+1} lines."
            if name == "view_file":
                lines = self.read().split("\n"); s = max(1, int(a.get("start", 1))); e = min(len(lines), int(a.get("end", s + 40)))
                return "\n".join(f"{i}: {lines[i-1]}" for i in range(s, e + 1))[:1500] or "(empty)"
            if name == "edit_file":
                src, old = self.read(), str(a.get("old", ""))
                if not old or src.count(old) != 1: return f"edit_file failed: the old text appears {src.count(old) if old else 0} times (must be exactly 1)."
                self.write(src.replace(old, str(a.get("new", "")))); return "Edited."
            if name == "replace_function": return self.replace_function(str(a.get("name", "")), str(a.get("code", "")))
            if name == "write_notes": open(self.notes, "w").write(str(a.get("text", ""))); return "NOTES.md saved."
            if name == "finish": self.finished = True; return "OK."
        except Exception as e:
            return f"Tool error: {e}"
        return "This tool is unavailable in this environment."

# ---------------------------------------------------------------- generation
class Out(Exception): pass

def segment(prompt, think, stops=("<|im_end|>",), path=QWEN3, deadline=None, limit=N_CTX):
    """Generate one assistant segment. think: 'on' (capped at THINK_CAP, forced close) or 'off'.
    Returns (text, finish) where finish is 'stop' or 'length' (window full)."""
    if deadline and time.time() > deadline: raise Out("deadline")
    m = model(path)
    if think == "off":
        head = "<think>\n\n</think>\n\n"; kw = SAMPLE_OFF
    else:
        kw = SAMPLE
        room = int(limit) - tok(prompt)
        if room < 32: return "", "length"
        r = m.create_completion(prompt, max_tokens=min(THINK_CAP, room), stop=["</think>", "<|im_end|>"], **kw)
        th, fin = r["choices"][0]["text"], r["choices"][0]["finish_reason"]
        if fin == "stop" and "<think>" not in th:
            return th, "stop"  # it answered without thinking and ended the reply
        head = th + "\n</think>\n\n"
    p2 = prompt + head
    room = int(limit) - tok(p2)
    if room < 16: return head, "length"
    r = m.create_completion(p2, max_tokens=room, stop=list(stops), **kw)
    return head + r["choices"][0]["text"], r["choices"][0]["finish_reason"]

def render(system, user):
    return f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"

def plain_chat(user, think, log, tag, deadline=None, system=None):
    """One fresh chat, no tools. Returns (output, finish)."""
    p = render(system if system is not None else FILLER, user)
    t = time.time()
    out, fin = segment(p, think, deadline=deadline)
    log.append({"tag": tag, "user": user, "prompt_tokens": tok(p), "output": out, "finish": fin, "secs": round(time.time() - t, 1)})
    return out, fin

def tool_chat(user, tools, think, ws, log, tag, deadline=None, max_steps=12):
    """One fresh chat with tools. Returns 'finished' | 'ended' | 'full'."""
    prompt = render(system_prompt(tools), user)
    rec = {"tag": tag, "user": user, "prompt_tokens": tok(prompt), "steps": []}
    log.append(rec)
    for _ in range(max_steps):
        t = time.time()
        out, fin = segment(prompt, think, stops=("<|im_end|>", "</tool_call>"), deadline=deadline)
        step = {"output": out, "finish": fin, "secs": round(time.time() - t, 1), "ctx": tok(prompt + out)}
        rec["steps"].append(step)
        if fin == "length": rec["end"] = "full"; return "full"
        m = re.search(r"<tool_call>\s*(\{.*\})\s*$", out, re.S)
        if not m: rec["end"] = "ended"; return "ended"
        try:
            call = json.loads(m.group(1), strict=False); name, args = call.get("name"), call.get("arguments") or {}
            res = ws.call(name, args)
        except Exception as e:
            name, res = "?", f"Could not parse the tool call JSON: {e}"
        step["tool"], step["result"] = name, res
        prompt += out + "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n" + res + "\n</tool_response><|im_end|>\n<|im_start|>assistant\n"
        if ws.finished: rec["end"] = "finished"; return "finished"
        if N_CTX - tok(prompt) < 64: rec["end"] = "full"; return "full"
    rec["end"] = "max_steps"; return "ended"

def unescape_partial(s):
    s = re.sub(r"\\$", "", s)
    try: return json.loads('"' + s + '"')
    except Exception: return s.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t").replace("\\\\", "\\")

def latest_code(text):
    t = strip_think(text)
    c = [(m.start(), m.group(1)) for m in re.finditer(r"```[a-zA-Z]*\n(.*?)(?:```|$)", t, re.S)]
    c += [(m.start(), unescape_partial(m.group(1))) for m in re.finditer(r'"(?:code|content|text)"\s*:\s*"((?:[^"\\]|\\.)*)("|$)', t, re.S)]
    c = [x for x in c if x[1].strip()]
    return max(c)[1] if c else None

def all_code(text):
    t = strip_think(text)
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)(?:```|$)", t, re.S)
    return "\n".join(b.rstrip() for b in blocks if b.strip()) if blocks else t

# ---------------------------------------------------------------- scoring
def score(path):
    rep = sandbox(path)
    m = re.search(r"TypeScript errors \((\d+)\)", rep)
    ts_err = int(m.group(1)) if m else 0
    runtime = "Runtime error" in rep or "Sandbox timeout" in rep
    m = re.search(r"Clicked \d+ of (\d+) clickable", rep); clickable = int(m.group(1)) if m else 0
    changed = "Page text changed" in rep
    handler_err = "Errors in event handlers" in rep or "Click handler error" in rep
    m = re.search(r"SCORE_MARKS X:(-?\d+) O:(-?\d+)", rep)
    o_marks = int(m.group(2)) if m else 0
    code = open(path).read() if os.path.exists(path) else ""
    pts = {"compiles": ts_err == 0 and bool(code.strip()), "runs": not runtime and bool(code.strip()),
           "board": clickable >= 9, "clicks_work": changed and not handler_err, "computer_moves": o_marks > 0}
    return {"points": sum(pts.values()), **pts, "ts_errors": ts_err, "lines": code.count("\n") + 1 if code.strip() else 0,
            "has_minimax": bool(re.search(r"minimax", code, re.I)) and code.count("minimax") >= 2, "report": rep[:1500]}
