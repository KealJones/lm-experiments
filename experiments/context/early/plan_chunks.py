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
TASK = ("a TypeScript tic tac toe game for the browser: a clickable 3x3 board in the DOM, a computer "
        "opponent that uses minimax so it never loses, a score counter, and a restart button")

src = open(os.path.join(WORK, "relay3.py")).read()
FILLER = re.search(r'FILLER = """(.*?)"""', src, re.S).group(1)

llm = Llama(model_path=MODEL, n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)
def tok(s): return len(llm.tokenize(s.encode(), add_bos=False, special=True))
def strip_think(s): return re.sub(r"<think>.*?(</think>|$)", "", s, flags=re.S).strip()

def chat(user):
    p = f"<|im_start|>system\n{FILLER}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    room = N_CTX - tok(p)
    t = time.time()
    r = llm.create_completion(p, max_tokens=room, temperature=0.6, top_p=0.95, top_k=20,
                              presence_penalty=0.5, stop=["<|im_end|>"])
    out = r["choices"][0]["text"]
    return {"user": user, "prompt_tokens": tok(p), "gen_tokens": r["usage"]["completion_tokens"],
            "finish": r["choices"][0]["finish_reason"], "secs": round(time.time() - t, 1), "output": out}

def code_of(text):
    t = strip_think(text)
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)(?:```|$)", t, re.S)
    return "\n".join(b.rstrip() for b in blocks if b.strip()) if blocks else ""

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

# 2) one fresh chat per step, only that step's text
chunks = []
for n, step in enumerate(steps, 1):
    rec = {"n": n, "step": step, "chats": []}
    log["steps"].append(rec)
    r = chat("Write the code for this step:\n\n" + step)
    rec["chats"].append(r); save()
    print(f"step {n}: gen {r['gen_tokens']} tok, {r['finish']}, {r['secs']}s", flush=True)
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
fp = os.path.join(WORK, "plan_final.ts"); open(fp, "w").write(final)
res = subprocess.run(["node", SBX, fp], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL).stdout
log["sandbox"] = res; save()
print("SANDBOX:\n" + res, flush=True)
print("DONE", flush=True)
