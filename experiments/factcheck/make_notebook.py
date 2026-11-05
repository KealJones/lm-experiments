"""Builds factcheck.ipynb for Kaggle (2x T4, internet on).
GPU 0: Qwen3 0.6B then Qwen3.5 0.8B; GPU 1: Llama 3.2 1B then Qwen2.5 Coder 1.5B.
Tool smoke test, pilot (2 questions) for Qwen3 + Llama, then the full run, then RESULTS.md."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
FILES = ["factcheck.py", "questions.json"]
B64 = {f: base64.b64encode((here / f).read_bytes()).decode() for f in FILES}

SETUP = f'''import base64, os, subprocess, sys
for f, b in {json.dumps(B64)}.items():
    open(f, "wb").write(base64.b64decode(b))
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "accelerate"], check=False)
import transformers
print("transformers", transformers.__version__)
r = subprocess.run([sys.executable, "factcheck.py", "check"], capture_output=True, text=True)
print(r.stdout[-2500:], r.stderr[-2500:])
assert r.returncode == 0, "tool check failed (internet on?)"'''

RUN = '''import glob, time, torch
NGPU = max(1, torch.cuda.device_count())
print("GPUs:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])


def go(tag, plan):
    procs = []
    for g, keys in plan.items():
        log = open(f"log_{tag}_gpu{g}.txt", "w")
        # ';' not '&&': one model failing (e.g. Qwen3.5 not loading) shouldn't skip the next one
        def one(spec):  # "model:arm" or "model:arm:np" (no planted reviews)
            k, arm, *rest = spec.split(":")
            return (f"{sys.executable} -u factcheck.py worker --model {k} --arm {arm} --gpu {g} --tag {tag}"
                    + (" --no-planted" if rest else ""))
        cmd = " ; ".join(one(k) for k in keys)
        procs.append((g, subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(30 if tag == "pilot" else 120)
        for g, _ in procs:
            lines = [l for l in open(f"log_{tag}_gpu{g}.txt").read().splitlines() if l.strip()]
            print(f"[{(time.time()-t0)/60:5.1f} min gpu{g}] " + (lines[-1][:200] if lines else "starting"), flush=True)
    for g, p in procs:
        print(f"--- gpu{g} ---\\n" + open(f"log_{tag}_gpu{g}.txt").read()[-4000:])


# run 4: Llama (crashed in run 3), Qwen3 / Qwen3.5 with thinking on, and the "read" arm (pipeline looks it up)
GPU0 = ["qwen3:think", "llama:free", "llama:force:np", "coder:read"]
GPU1 = ["qwen35:think", "llama:lookup:np", "qwen3:read", "qwen35:read", "llama:read"]
if NGPU > 1:
    PILOT, FULL = {0: ["llama:read"], 1: ["qwen3:think"]}, {0: GPU0, 1: GPU1}
else:
    PILOT, FULL = {0: ["llama:read", "qwen3:think"]}, {0: GPU0 + GPU1}
go("pilot", PILOT)
GO = len(glob.glob("results_pilot_*.json")) >= 1  # one model failing shouldn't cost the rest
print("Pilot ok; full run starting." if GO else "Pilot FAILED; full run skipped.")'''

FULL = '''if GO:
    go("full", FULL)
r = subprocess.run([sys.executable, "factcheck.py", "report"], capture_output=True, text=True)
print(r.stdout[-10000:], r.stderr[-3000:])'''

head = ("# Draft -> fact-check\n\nSmall models answer 12 easy-to-look-up questions with Wikipedia/Wikidata tools, then "
        "review their own answer (and a planted wrong one) in a fresh chat, plain and strict. Three draft arms: free, lookup (told to always look it up) force (first turn prefilled with a search call), read (the pipeline searches and reads the top page first) and think (Qwen thinking on). Results: `RESULTS.md`; "
        "transcripts in `results_full_*.json`.")
cells = [{"cell_type": "markdown", "metadata": {}, "source": head}]
for src in (SETUP, RUN, FULL):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "factcheck.ipynb").write_text(json.dumps(nb))
print("factcheck.ipynb", round(len(json.dumps(nb)) / 1e6, 3), "MB")
