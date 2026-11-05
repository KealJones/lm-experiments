"""Local port of memdoor's team-solve (GVS5H method) for small Qwen3 models on llama.cpp.
plan -> ideate-a -> ideate-b -> solve -> test(cmd) -> review -> repair -> verify(cmd)
Every agent step: fresh context, plain coding-agent system prompt, tools, thinking on. Files are the only channel.
Also a 'single' baseline: one call, task.md in, solution.py out.
usage: python3 team.py <model> <out.json> <tries> <problem...>     model: 0.6b | 1.7b | 4b
"""
import json, os, re, shutil, subprocess, sys, time
from llama_cpp import Llama

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(os.path.dirname(HERE))
MODELS = {"0.6b": "qwen3-0.6b-q8.gguf", "1.7b": "qwen3-1.7b-q8.gguf", "4b": "qwen3-4b-q4km.gguf"}
MODEL, OUT, TRIES, PROBLEMS = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
N_CTX, MAX_GEN, MAX_CALLS = 16384, 8192, 20
STEP_SECS = {"0.6b": 15 * 60, "1.7b": 25 * 60, "4b": 45 * 60}[MODEL]
llm = Llama(model_path=f"{S}/model/{MODELS[MODEL]}", n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)
def tok(s): return len(llm.tokenize(s.encode(), add_bos=False, special=True))

STEPS = {}
for n in ["plan", "ideate-a", "ideate-b", "solve", "review", "repair"]:
    t = open(f"{S}/ext/memdoor/examples/workflows/team-solve/steps/{n}.yaml").read()
    p = t.split("prompt: |\n", 1)[1].split("\ntimeout:")[0]
    STEPS[n] = "\n".join(l[2:] if l.startswith("  ") else l for l in p.split("\n")).strip()
TEMP = {"plan": 0.3, "ideate-a": 0.4, "ideate-b": 0.4, "solve": 0.2, "review": 0.2, "repair": 0.2}

SYSTEM = ("You are a coding agent working in a project folder. Use the tools to read and write files and to run "
          "commands. When your task is done, reply with a short summary and no tool call.")
TOOLS = [
 ("ls", "List files in the project folder (recursively).", {}),
 ("read_file", "Read a file with line numbers.", {"path": "string"}),
 ("write_file", "Create or overwrite a file.", {"path": "string", "content": "string"}),
 ("edit_file", "Replace an exact piece of text in a file; old must appear exactly once.", {"path": "string", "old": "string", "new": "string"}),
 ("apply_patch", "Insert text into a file immediately before a unique marker line (the marker is kept).", {"path": "string", "marker": "string", "text": "string"}),
 ("bash", "Run a shell command in the project folder (20 second limit). Example: python3 solution.py < tests/1.in", {"command": "string"}),
]
def schema(n, d, p):
    return {"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object",
            "properties": {k: {"type": v} for k, v in p.items()}, "required": list(p)}}}
SYS_FULL = (SYSTEM + "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
            "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n" +
            "\n".join(json.dumps(schema(*t)) for t in TOOLS) +
            "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
            "<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>")

def safe(d, p):
    q = os.path.normpath(os.path.join(d, str(p or "").lstrip("/")))
    if not q.startswith(d): raise ValueError("path outside the project folder")
    return q

def tool(d, name, a):
    a = a if isinstance(a, dict) else {}
    try:
        if name == "ls":
            out = []
            for root, _, files in os.walk(d):
                for f in sorted(files): out.append(os.path.relpath(os.path.join(root, f), d))
            return "\n".join(sorted(out)) or "(empty)"
        if name == "read_file":
            lines = open(safe(d, a.get("path"))).read().split("\n")
            t = "\n".join(f"{i}: {l}" for i, l in enumerate(lines, 1))
            return t[:8000] + ("\n...(truncated)" if len(t) > 8000 else "")
        if name == "write_file":
            p = safe(d, a.get("path")); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(str(a.get("content", ""))); return f"Wrote {a.get('path')}."
        if name == "edit_file":
            p = safe(d, a.get("path")); src = open(p).read(); old = str(a.get("old", "")); n = src.count(old) if old else 0
            if n != 1: return f"edit_file failed: old text found {n} times (must be exactly 1)."
            open(p, "w").write(src.replace(old, str(a.get("new", "")))); return "Edited."
        if name == "apply_patch":
            p = safe(d, a.get("path")); src = open(p).read(); mk = str(a.get("marker", "")); n = src.count(mk) if mk else 0
            if n != 1: return f"apply_patch failed: marker found {n} times (must be exactly 1)."
            i = src.index(mk); open(p, "w").write(src[:i] + str(a.get("text", "")).rstrip("\n") + "\n" + src[i:]); return "Inserted."
        if name == "bash":
            r = subprocess.run(["bash", "-c", str(a.get("command", ""))], cwd=d, capture_output=True, text=True, timeout=20)
            o = (r.stdout + r.stderr)[-3000:]
            return f"exit code {r.returncode}\n{o}" if o.strip() else f"exit code {r.returncode} (no output)"
        return f"Unknown tool {name}."
    except subprocess.TimeoutExpired:
        return "Timed out after 20 seconds."
    except Exception as e:
        return f"Tool error: {e}"

def agent(d, step, run_id, log):
    user = STEPS[step].replace("{{.partition}}", run_id)
    prompt = f"<|im_start|>system\n{SYS_FULL}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    rec = {"step": step, "calls": [], "end": "max tool calls"}; log.append(rec); t0 = time.time()
    for i in range(MAX_CALLS):
        if time.time() - t0 > STEP_SECS: rec["end"] = "step time limit"; break
        room = N_CTX - tok(prompt)
        if room < 256: rec["end"] = "context full"; break
        r = llm.create_completion(prompt, max_tokens=min(MAX_GEN, room), temperature=TEMP[step], top_p=0.95, top_k=20,
                                  seed=hash((run_id, step, i)) % 2**31, stop=["<|im_end|>", "</tool_call>"])
        out, fin = r["choices"][0]["text"], r["choices"][0]["finish_reason"]
        c = {"gen": r["usage"]["completion_tokens"], "think_chars": len("".join(re.findall(r"<think>(.*?)(?:</think>|$)", out, re.S))),
             "out": out[-1500:]}
        rec["calls"].append(c)
        m = re.search(r"<tool_call>\s*(\{.*\})\s*$", out, re.S)
        if not m: rec["end"] = "cut off at reply cap" if fin == "length" else "done"; break
        try:
            j = json.loads(m.group(1), strict=False); name, args = j.get("name"), j.get("arguments") or {}
            res = tool(d, name, args)
        except Exception as e:
            name, res = "?", f"Could not parse the tool call JSON: {e}"
        c["tool"], c["result"] = name, res[:500]
        prompt += out + "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n" + res + "\n</tool_response><|im_end|>\n<|im_start|>assistant\n"
    rec["secs"] = round(time.time() - t0); rec["ctx"] = tok(prompt)
    return rec

def check(d):
    r = subprocess.run(["bash", f"{HERE}/check-samples.sh"], cwd=d, capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout + r.stderr

def hidden(d, problem):
    hd = f"{HERE}/problems/{problem}/hidden"; ok = 0; n = 0
    if not os.path.exists(f"{d}/solution.py"): return 0, len([f for f in os.listdir(hd) if f.endswith(".in")])
    for f in sorted(os.listdir(hd)):
        if not f.endswith(".in"): continue
        n += 1
        try:
            r = subprocess.run(["python3", "solution.py"], cwd=d, stdin=open(f"{hd}/{f}"), capture_output=True, text=True, timeout=10)
            ok += r.stdout.strip() == open(f"{hd}/{f[:-3]}.out").read().strip()
        except subprocess.TimeoutExpired: pass
    return ok, n

def fresh(problem, d):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    shutil.copy(f"{HERE}/problems/{problem}/task.md", d); shutil.copytree(f"{HERE}/problems/{problem}/tests", f"{d}/tests")

def team(problem, trial):
    run_id = f"{MODEL}-{problem}-t{trial}"; d = f"{HERE}/runs/team-{run_id}"; fresh(problem, d); log = []; t0 = time.time()
    for step in ["plan", "ideate-a", "ideate-b", "solve"]: agent(d, step, run_id, log)
    st, out = check(d); open(f"{d}/test-output.log", "w").write(out); open(f"{d}/test-status.txt", "w").write(f"{st}\n")
    log.append({"step": "test", "status": st, "out": out[-800:]})
    for step in ["review", "repair"]: agent(d, step, run_id, log)
    st2, out2 = check(d); open(f"{d}/final-test-output.log", "w").write(out2)
    log.append({"step": "verify", "status": st2, "out": out2[-800:]})
    h = hidden(d, problem)
    return {"mode": "team", "model": MODEL, "problem": problem, "trial": trial, "samples_pass_first": st == 0,
            "samples_pass_final": st2 == 0, "hidden": h, "secs": round(time.time() - t0),
            "files": sorted(os.listdir(d)), "log": log}

def single(problem, trial):
    run_id = f"{MODEL}-{problem}-t{trial}"; d = f"{HERE}/runs/single-{run_id}"; fresh(problem, d); t0 = time.time()
    user = open(f"{d}/task.md").read() + "\n\nReply with the complete solution.py in one Python code block."
    p = f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    r = llm.create_completion(p, max_tokens=min(MAX_GEN * 2, N_CTX - tok(p)), temperature=0.6, top_p=0.95, top_k=20,
                              seed=hash(run_id) % 2**31, stop=["<|im_end|>"])
    out = r["choices"][0]["text"]
    vis = re.sub(r"<think>.*?(</think>|$)", "", out, flags=re.S)
    m = re.findall(r"```(?:python)?\n(.*?)```", vis, re.S)
    if m: open(f"{d}/solution.py", "w").write(m[-1])
    st, o = check(d); h = hidden(d, problem)
    return {"mode": "single", "model": MODEL, "problem": problem, "trial": trial, "samples_pass_final": st == 0,
            "hidden": h, "secs": round(time.time() - t0), "gen": r["usage"]["completion_tokens"],
            "finish": r["choices"][0]["finish_reason"], "out": out[-2000:]}

results = json.load(open(OUT)) if os.path.exists(OUT) else []
done = {(r["mode"], r["problem"], r["trial"]) for r in results}
for trial in range(TRIES):
    for problem in PROBLEMS:
        for mode, fn in [("single", single), ("team", team)]:
            if (mode, problem, trial) in done: continue
            r = fn(problem, trial); results.append(r); json.dump(results, open(OUT, "w"), indent=1)
            steps = "" if mode == "single" else " | " + " ".join(f"{s['step']}:{s.get('end', s.get('status'))}" for s in r["log"])
            print(f"{MODEL} {mode:6} {problem:6} t{trial} samples={'PASS' if r['samples_pass_final'] else 'fail'} "
                  f"hidden={r['hidden'][0]}/{r['hidden'][1]} {r['secs']}s{steps}", flush=True)
print("ALL DONE", flush=True)
