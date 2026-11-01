"""From scratch, with tools: plain Qwen3 0.6B gets only the task ("write a Zig 0.17 program that ...") plus tools to
look things up and try things, and as many turns as it wants (up to MAX_TURNS). No snippet, no examples.

Tools (all confined to the language's docs folder):
  list_files()                     what docs exist
  grep(pattern)                    search the docs, returns matching lines with file and line number
  read(file, start_line, num_lines) read part of a doc
  run(code)                        compile/run a program, returns its output and errors
It's done when it replies without calling a tool; the code block in that reply is graded (if there's none, the last
code it ran). Graded leniently: the right answer must be the last line(s) of output, labels allowed.

  python agent.py worker --lang zig --gpu 0 --tag pilot|full
  python agent.py report
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import run as base

HERE = base.HERE
MODEL = "Qwen/Qwen3-0.6B"
MAX_TURNS = 15
MAX_CONTEXT = 14000  # tokens; a conversation that grows past this is ended and graded on what it has
ATTEMPTS = 3
# what Qwen3 0.6B scored before on the same 25 tasks (lenient grading, tasks solved out of 25; see README)
BEFORE = {"zig": {"cold": 0, "snippet": 0}, "plink": {"cold": 0, "snippet": 1}}

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List the documentation files.",
                                      "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "grep", "description": "Search the documentation for a regular expression (case-insensitive). "
                                       "Returns matching lines as file:line: text.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "what to find"}},
                       "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "read", "description": "Read lines from a documentation file.",
        "parameters": {"type": "object", "properties": {
            "file": {"type": "string"}, "start_line": {"type": "integer", "description": "first line, from 1"},
            "num_lines": {"type": "integer", "description": "how many lines (max 100)"}}, "required": ["file"]}}},
    {"type": "function", "function": {
        "name": "run", "description": "Compile and run a complete program. Returns the exit code, output and errors.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "the whole program"}},
                       "required": ["code"]}}},
]


def system(lang):
    what = ("Plink is a small programming language. " if lang == "plink" else "")
    return (f"You are a programmer. {what}You can search and read the {base.NICE[lang]} documentation and run "
            f"{base.NICE[lang]} code with your tools. Use them as much as you need.")


def task_prompt(lang, desc):
    return (f"Write a complete {base.NICE[lang]} program that {desc}. Print only the answer, each value on its own "
            f"line. When you're done, reply with only the final code in one code block.")


# ---------------------------------------------------------------- tools

def docs_dir(lang):
    return HERE / "docs" / lang


def cut(s, n):
    return s if len(s) <= n else s[:n] + f"\n... [{len(s) - n} more characters cut]"


def tool_list_files(lang):
    return "\n".join(f"{p.name} ({len(p.read_text().splitlines())} lines)" for p in sorted(docs_dir(lang).iterdir()))


def tool_grep(lang, pattern="", **_):
    if not str(pattern).strip():
        return "error: empty pattern"
    try:
        rx = re.compile(str(pattern), re.I)
    except re.error:
        rx = re.compile(re.escape(str(pattern)), re.I)
    hits = []
    for p in sorted(docs_dir(lang).iterdir()):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.name}:{i}: {line.strip()[:160]}")
    if not hits:
        return "no matches"
    more = f"\n({len(hits) - 25} more matches not shown)" if len(hits) > 25 else ""
    return cut("\n".join(hits[:25]), 2500) + more


def tool_read(lang, file="", start_line=1, num_lines=60, **_):
    p = docs_dir(lang) / pathlib.Path(str(file)).name
    if not p.exists():
        return f"error: no file {file!r}. Files: " + ", ".join(x.name for x in docs_dir(lang).iterdir())
    lines = p.read_text().splitlines()
    try:
        s, n = max(1, int(start_line)), max(1, min(100, int(num_lines)))
    except (TypeError, ValueError):
        s, n = 1, 60
    chunk = lines[s - 1:s - 1 + n]
    return cut("\n".join(f"{s + k}: {l}" for k, l in enumerate(chunk)), 3500) or "(past the end of the file)"


def execute(lang, code):
    """-> (exit code or None on timeout, stdout, stderr)"""
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / {"python": "main.py", "zig": "main.zig", "plink": "main.plk"}[lang]
        f.write_text(code)
        cmd = {"python": [sys.executable, "-I", str(f)],
               "plink": [sys.executable, "-I", str(HERE / "plink.py"), str(f)],
               "zig": base.zig_cmd() + ["run", str(f)]}[lang]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120 if lang == "zig" else 10, cwd=d)
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return None, "", "timed out"


def tool_run(lang, code="", **_):
    if not str(code).strip():
        return "error: no code"
    rc, out, err = execute(lang, str(code))
    if lang == "zig":  # keep compile errors, drop the long 'referenced by' traces
        err = "\n".join(l for l in err.splitlines() if "/lib/std/" not in l and "reference(s) hidden" not in l)
    return cut(f"exit code: {'timeout' if rc is None else rc}\noutput:\n{out}\nerrors:\n{err}", 1800)


TOOL_FNS = {"list_files": tool_list_files, "grep": tool_grep, "read": tool_read, "run": tool_run}


def call_tool(lang, name, args):
    if name not in TOOL_FNS:
        return f"error: no tool named {name!r}"
    if not isinstance(args, dict):
        return "error: arguments must be an object"
    try:
        return TOOL_FNS[name](lang, **args)
    except TypeError as e:
        return f"error: bad arguments ({e})"


# ---------------------------------------------------------------- grading

def norm(l):
    l = l.strip()
    return re.sub(r"^[^:=]*[:=]\s*", "", l).strip() if re.search(r"[:=]\s*\S", l) else l


def lenient(lang, code, expected):
    v, d = base.grade(lang, code, expected)
    if v != "wrong":
        return v, d
    rc, out, err = execute(lang, code)
    if rc != 0:
        return "wrong", d
    got = [norm(l) for l in (out + (err if lang == "zig" else "")).strip().splitlines() if l.strip()]
    exp = expected.split("\n")
    return ("pass", "lenient") if got[-len(exp):] == exp else ("wrong", d)


# ---------------------------------------------------------------- agent loop

TOOL_CALL = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)


def parse(reply):
    """-> (text without tool calls, [(name, args) or (None, error)])"""
    calls = []
    for raw in TOOL_CALL.findall(reply):
        try:
            j = json.loads(raw)
            args = j.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            calls.append((j.get("name"), args))
        except (json.JSONDecodeError, AttributeError):
            calls.append((None, "error: couldn't read that tool call as JSON"))
    if "<tool_call>" in reply and not reply.count("</tool_call>"):  # cut off mid-call
        calls.append((None, "error: tool call was cut off (too long?)"))
    return TOOL_CALL.sub("", reply).split("<tool_call>")[0].strip(), calls


def worker(lang, gpu, tag):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.time()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    tok.padding_side = "left"
    try:
        model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float16 if dev == "cuda" else torch.float32)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16 if dev == "cuda" else torch.float32)
    model = model.to(dev).eval()

    tasks = [t for t in base.TASKS if t[0] in base.PILOT_TASKS[:2]] if tag == "pilot" else base.TASKS
    attempts = 1 if tag == "pilot" else ATTEMPTS
    max_turns = 6 if tag == "pilot" else MAX_TURNS
    convs = []
    for a in range(attempts):
        for tid, desc, expected in tasks:
            convs.append(dict(lang=lang, task=tid, attempt=a, expected=expected, done=False, end="", turns=0,
                              tools={k: 0 for k in TOOL_FNS}, last_run_code=None, final_code=None,
                              msgs=[{"role": "system", "content": system(lang)},
                                    {"role": "user", "content": task_prompt(lang, desc)}]))

    def render(c):
        return tok.apply_chat_template(c["msgs"], tools=TOOLS, tokenize=False, add_generation_prompt=True,
                                       enable_thinking=False)

    step = 0
    while True:
        active = [c for c in convs if not c["done"]]
        if not active:
            break
        step += 1
        texts = [(c, render(c)) for c in active]
        lens = {id(c): len(tok(t)["input_ids"]) for c, t in texts}
        for c, _ in texts:
            if lens[id(c)] > MAX_CONTEXT:
                c["done"], c["end"] = True, "context full"
        texts = sorted([(c, t) for c, t in texts if not c["done"]], key=lambda x: lens[id(x[0])])
        i = 0
        while i < len(texts):
            bs = max(1, min(8, 40000 // (lens[id(texts[i][0])] + 800)))  # longer contexts -> smaller batches
            chunk = texts[i:i + bs]
            i += bs
            batch = tok([t for _, t in chunk], return_tensors="pt", padding=True).to(dev)
            with torch.no_grad():
                g = model.generate(**batch, max_new_tokens=900, do_sample=True, temperature=0.7, top_p=0.8, top_k=20,
                                   pad_token_id=tok.pad_token_id)
            replies = tok.batch_decode(g[:, batch["input_ids"].shape[1]:], skip_special_tokens=True)
            for (c, _), reply in zip(chunk, replies):
                c["turns"] += 1
                text, calls = parse(reply)
                if not calls:
                    c["msgs"].append({"role": "assistant", "content": reply.strip()})
                    blocks = re.findall(r"```[^\n`]*\n(.*?)```", reply, re.S)
                    c["final_code"] = blocks[-1] if blocks else None
                    c["done"], c["end"] = True, "answered"
                    continue
                good = [(n, a) for n, a in calls if n is not None]
                c["msgs"].append({"role": "assistant", "content": text,
                                  "tool_calls": [{"type": "function", "function": {"name": n, "arguments": a}}
                                                 for n, a in good]})
                c["pending"] = calls
            # run this chunk's tools in parallel (zig compiles are the slow part)
            with cf.ThreadPoolExecutor(4) as ex:
                for c, _ in chunk:
                    if c["done"]:
                        continue
                    futs = []
                    for n, a in c.pop("pending"):
                        if n is None:
                            futs.append((n, a, None))
                        else:
                            c["tools"][n] = c["tools"].get(n, 0) + 1
                            if n == "run" and isinstance(a, dict):
                                c["last_run_code"] = a.get("code")
                            futs.append((n, a, ex.submit(call_tool, lang, n, a)))
                    for n, a, f in futs:
                        c["msgs"].append({"role": "tool", "content": a if f is None else f.result()})
                    if c["turns"] >= max_turns:
                        c["done"], c["end"] = True, "turn limit"
        left = sum(not c["done"] for c in convs)
        print(f"  step {step}: {len(convs) - left}/{len(convs)} finished ({time.time() - t0:.0f}s)", flush=True)

    print("grading", flush=True)
    for c in convs:
        code = c["final_code"] or c["last_run_code"]
        c["graded_code"] = "final answer" if c["final_code"] else ("last run" if code else "none")
        c["verdict"], c["detail"] = lenient(lang, code, c["expected"]) if code else ("wrong", "no code")
    out = {"model": MODEL, "lang": lang, "tag": tag, "seconds": round(time.time() - t0), "convs": convs}
    pathlib.Path(f"agent_{tag}_{lang}.json").write_text(json.dumps(out, indent=1))
    solved = {c["task"] for c in convs if c["verdict"] == "pass"}
    print(f"== {lang} {tag}: pass {sum(c['verdict'] == 'pass' for c in convs)}/{len(convs)}, "
          f"tasks solved {len(solved)}/{len(tasks)} in {out['seconds']}s", flush=True)


# ---------------------------------------------------------------- report

def report():
    lines = ["# From scratch with tools: results", "",
             f"Each model gets just the task, tools to list/grep/read the docs and run code, up to {MAX_TURNS} turns, "
             f"{ATTEMPTS} attempts per task (sampled). Lenient grading: the answer must be the last line(s) of output.", ""]
    for f in sorted(pathlib.Path(".").glob("agent_full_*.json")):
        d = json.load(open(f))
        cs, lang = d["convs"], d["lang"]
        lines += [f"# {d['model']}", ""]
        n = len(cs)
        solved = {c["task"] for c in cs if c["verdict"] == "pass"}
        avg = lambda k: sum(c["tools"].get(k, 0) for c in cs) / n
        ends = {e: sum(c["end"] == e for c in cs) for e in ["answered", "turn limit", "context full"]}
        ends["error"] = sum(c["end"].startswith("error") for c in cs)
        syn = sum(c["verdict"] == "syntax" for c in cs)
        lines += [f"## {base.NICE[lang]}", "",
                  f"- **Tasks solved: {len(solved)}/25**" + (f" (before: cold {BEFORE[lang]['cold']}/25, with a snippet "
                  f"{BEFORE[lang]['snippet']}/25)" if d["model"] == MODEL else ""),
                  f"- Answers passing: {sum(c['verdict'] == 'pass' for c in cs)}/{n}; failing to compile/parse: {syn}/{n}",
                  f"- Average per attempt: {sum(c['turns'] for c in cs) / n:.1f} turns, grep {avg('grep'):.1f}, "
                  f"read {avg('read'):.1f}, list_files {avg('list_files'):.1f}, run {avg('run'):.1f}",
                  f"- Attempts that never looked at the docs: {sum(c['tools']['grep'] + c['tools']['read'] == 0 for c in cs)}/{n}; "
                  f"never ran code: {sum(c['tools']['run'] == 0 for c in cs)}/{n}",
                  f"- How attempts ended: " + ", ".join(f"{k} {v}" for k, v in ends.items()),
                  f"- Solved: {', '.join(sorted(solved)) or 'none'}", ""]
    pathlib.Path("AGENT_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["worker", "report"])
    ap.add_argument("--lang", choices=["zig", "plink"])
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--tag", default="full")
    a = ap.parse_args()
    worker(a.lang, a.gpu, a.tag) if a.cmd == "worker" else report()
