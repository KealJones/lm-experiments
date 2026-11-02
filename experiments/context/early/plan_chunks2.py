"""Plan-then-chunks test: Qwen3 0.6B, 4,096 window, thinking on, junk system prompt.
1) Fresh chat: make a numbered plan only (no code). Stop.
2) For each plan step: fresh chat containing ONLY that step's text. It writes that chunk. Stop.
   If a chunk runs out of context: fresh chat "can you complete this games code\n\n<partial chunk>".
3) Concatenate chunks in order -> final.ts, run in the sandbox.
"""
import json, re, subprocess, sys, time, os
from llama_cpp import Llama

MODEL, OUT, SBX = sys.argv[1], sys.argv[2], sys.argv[3]
WORK = os.path.dirname(OUT)
N_CTX = 4096
THINK_CAP = 800
TASK = ("a TypeScript tic tac toe game for the browser: a clickable 3x3 board in the DOM, a computer "
        "opponent that uses minimax so it never loses, a score counter, and a restart button")

src = open(os.path.join(WORK, "relay3.py")).read()
FILLER = re.search(r'FILLER = """(.*?)"""', src, re.S).group(1)

llm = Llama(model_path=MODEL, n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)
def tok(s): return len(llm.tokenize(s.encode(), add_bos=False, special=True))
def strip_think(s): return re.sub(r"<think>.*?(</think>|$)", "", s, flags=re.S).strip()

def chat(user):
    p = f"<|im_start|>system\n{FILLER}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    t = time.time()
    kw = dict(temperature=0.6, top_p=0.95, top_k=20, presence_penalty=0.5)
    # thinking phase, capped at THINK_CAP tokens; force </think> if it hasn't closed
    r1 = llm.create_completion(p, max_tokens=THINK_CAP, stop=["</think>", "<|im_end|>"], **kw)
    th = r1["choices"][0]["text"]
    capped = r1["choices"][0]["finish_reason"] == "length"
    head = th + ("\n</think>\n\n" if "<|im_end|>" not in th else "")
    p2 = p + head
    room = N_CTX - tok(p2)
    r2 = llm.create_completion(p2, max_tokens=max(room, 1), stop=["<|im_end|>"], **kw)
    out = head + r2["choices"][0]["text"]
    return {"user": user, "prompt_tokens": tok(p), "gen_tokens": r1["usage"]["completion_tokens"] + r2["usage"]["completion_tokens"],
            "think_capped": capped, "finish": r2["choices"][0]["finish_reason"], "secs": round(time.time() - t, 1), "output": out}

def code_of(text):
    t = strip_think(text)
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)(?:```|$)", t, re.S)
    return "\n".join(b.rstrip() for b in blocks if b.strip()) if blocks else t

log = {"task": TASK, "plan": None, "steps": []}
def save(): json.dump(log, open(OUT, "w"), indent=1)

# 1) plan
plan_req = ("Make a plan for writing " + TASK + ". Split the work into small numbered steps, each one a small "
            "chunk of code. For each step, say exactly what code it writes and the names of the functions, "
            "variables and HTML element ids it creates or uses from earlier steps, so someone could write that "
            "step without seeing the other steps. Only write the plan. Do not write any code yet.")
pl = chat(plan_req); log["plan"] = pl; save()
print(f"plan: gen {pl['gen_tokens']} tok, {pl['finish']}, {pl['secs']}s", flush=True)
plan_text = strip_think(pl["output"])
parts = re.split(r"(?m)^\s*(?:#+\s*)?(?:\*\*)?(?:Step\s*)?(\d+)[.):]", plan_text)
steps = []
for i in range(1, len(parts) - 1, 2):
    body = parts[i + 1].strip().strip("*").strip()
    if body: steps.append(f"{parts[i]}. {body}")
log["parsed_steps"] = steps; save()
print(f"parsed {len(steps)} steps", flush=True)

def names_in(code):
    fns = re.findall(r"function\s+(\w+)\s*(\([^)]*\))", code)
    fns += re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(\([^)]*\))\s*(?::[^=]*)?=>", code)
    fset = {f for f, _ in fns}
    vars_ = [v for v in re.findall(r"(?:const|let|var)\s+(\w+)", code) if v not in fset]
    ids = re.findall(r"id=[\"'`]([\w-]+)", code) + re.findall(r"getElementById\(\s*[\"'`]([\w-]+)", code) + re.findall(r"\.id\s*=\s*[\"'`]([\w-]+)", code)
    return [f"{f}{a}" for f, a in fns], vars_, ids

def uniq(xs):
    seen = []; [seen.append(x) for x in xs if x not in seen]; return seen

GOAL = "Goal: " + TASK[0].upper() + TASK[1:] + "."

# 2) one fresh chat per step, only that step's text
chunks = []
for n, step in enumerate(steps, 1):
    rec = {"n": n, "step": step, "chats": []}
    log["steps"].append(rec)
    F, V, I = [], [], []
    for c in chunks:
        f, v, i = names_in(c); F += f; V += v; I += i
    known = ("Already defined by earlier steps (use these, don't redefine them):\n"
             f"- functions: {', '.join(uniq(F)) or 'none'}\n- variables: {', '.join(uniq(V)) or 'none'}\n"
             f"- element ids: {', '.join('#' + x for x in uniq(I)) or 'none'}") if n > 1 else "This is the first step; nothing is defined yet."
    req = (GOAL + "\n\nWrite only the code for this step, as one TypeScript code block:\n" + step + "\n\n" + known)
    rec["request"] = req
    r = chat(req)
    rec["chats"].append(r); save()
    print(f"step {n}: gen {r['gen_tokens']} tok, think capped={r['think_capped']}, {r['finish']}, {r['secs']}s", flush=True)
    code = code_of(r["output"])
    relays = 0
    while r["finish"] == "length" and relays < 4:
        relays += 1
        if not code.strip(): break
        r = chat("can you complete this games code\n\n" + code)
        rec["chats"].append(r); save()
        print(f"step {n} relay {relays}: gen {r['gen_tokens']} tok, {r['finish']}, {r['secs']}s", flush=True)
        code = code_of(r["output"]) or code
    rec["code"] = code; chunks.append(code); save()

# 3) assemble + sandbox
final = "\n\n".join(f"// ---- step {i} ----\n{c}" for i, c in enumerate(chunks, 1))
fp = os.path.join(WORK, "plan2_final.ts"); open(fp, "w").write(final)
res = subprocess.run(["node", SBX, fp], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL).stdout
log["sandbox"] = res; save()
print("SANDBOX:\n" + res, flush=True)
print("DONE", flush=True)
