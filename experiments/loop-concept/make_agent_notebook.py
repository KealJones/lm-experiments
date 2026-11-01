"""Builds agent_from_scratch.ipynb for Kaggle: plain Qwen3 0.6B, task only, tools to grep/read docs and run code.
Zig on GPU 0, Plink on GPU 1. Pilot (2 tasks, 6 turns) first, then the full run, then AGENT_RESULTS.md."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
FILES = ["run.py", "plink.py", "agent.py", "docs/zig/langref.txt", "docs/plink/reference.txt"]
B64 = {f: base64.b64encode((here / f).read_bytes()).decode() for f in FILES}

SETUP = f'''import base64, os, subprocess, sys
for f, b in {json.dumps(B64)}.items():
    os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
    open(f, "wb").write(base64.b64decode(b))
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ziglang==0.17.0"], check=True)
import transformers
print("transformers", transformers.__version__)
r = subprocess.run([sys.executable, "run.py", "check"], capture_output=True, text=True)
print(r.stdout[-1500:], r.stderr[-1500:])
assert r.returncode == 0, "grader check failed"'''

RUN = '''import glob, time, torch
NGPU = max(1, torch.cuda.device_count())
print("GPUs:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
PLAN = {0: ["zig"], 1: ["plink"]} if NGPU > 1 else {0: ["zig", "plink"]}


def go(tag):
    procs = []
    for g, langs in PLAN.items():
        log = open(f"agent_{tag}_gpu{g}.txt", "w")
        cmd = " && ".join(f"{sys.executable} -u agent.py worker --lang {l} --gpu {g} --tag {tag}" for l in langs)
        procs.append((g, subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(30 if tag == "pilot" else 300)
        for g, _ in procs:
            lines = [l for l in open(f"agent_{tag}_gpu{g}.txt").read().splitlines() if l.strip()]
            print(f"[{(time.time()-t0)/60:5.1f} min gpu{g}] " + (lines[-1][:200] if lines else "starting"), flush=True)
    for g, p in procs:
        print(f"--- gpu{g} (exit {p.returncode}) ---\\n" + open(f"agent_{tag}_gpu{g}.txt").read()[-3000:])
    return all(p.returncode == 0 for _, p in procs)


GO = go("pilot") and len(glob.glob("agent_pilot_*.json")) == 2
print("Pilot passed; full run starting." if GO else "Pilot FAILED; full run skipped.")'''

FULL = '''if GO:
    go("full")
r = subprocess.run([sys.executable, "agent.py", "report"], capture_output=True, text=True)
print(r.stdout[-10000:], r.stderr[-3000:])'''

head = ("# From scratch with tools\n\nPlain Qwen3 0.6B gets only the task (write a Zig 0.17 / Plink program that ...) "
        "and tools to list, grep and read the docs and to run code, for up to 15 turns. No snippet, no examples. "
        "Results: `AGENT_RESULTS.md`; full transcripts in `agent_full_*.json`.")
cells = [{"cell_type": "markdown", "metadata": {}, "source": head}]
for src in (SETUP, RUN, FULL):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "agent_from_scratch.ipynb").write_text(json.dumps(nb))
print("agent_from_scratch.ipynb", round(len(json.dumps(nb)) / 1e6, 2), "MB")
