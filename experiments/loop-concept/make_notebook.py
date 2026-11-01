"""Builds loop_concept.ipynb for Kaggle: writes run.py + plink.py, installs Zig 0.17, checks the graders,
runs a pilot (3 tasks, greedy) then the full run (Qwen3 0.6B on GPU 0, Qwen3 1.7B on GPU 1), then the report."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
B64 = {f: base64.b64encode((here / f).read_bytes()).decode() for f in ("run.py", "plink.py")}
MODELS = ["Qwen/Qwen3-0.6B", "Qwen/Qwen3-1.7B"]

SETUP = f'''import base64, os, subprocess, sys
for f, b in {json.dumps(B64)}.items():
    open(f, "wb").write(base64.b64decode(b))
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ziglang==0.17.0"], check=True)
import transformers
print("transformers", transformers.__version__)
if tuple(int(x) for x in transformers.__version__.split(".")[:2]) < (4, 51):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers>=4.51"], check=True)
r = subprocess.run([sys.executable, "run.py", "check"], capture_output=True, text=True)
print(r.stdout[-3000:], r.stderr[-2000:])
assert r.returncode == 0, "grader check failed"'''

RUN = f'''import glob, json, time, torch
MODELS = {json.dumps(MODELS)}
NGPU = max(1, torch.cuda.device_count())
print("GPUs:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
PLAN = {{g: [m for k, m in enumerate(MODELS) if k % NGPU == g] for g in range(NGPU)}}


def run(tag):
    procs = []
    for g, models in PLAN.items():
        log = open(f"{{tag}}_gpu{{g}}.txt", "w")
        cmd = " && ".join(f"{{sys.executable}} -u run.py worker --model {{m}} --gpu {{g}} --tag {{tag}}" for m in models)
        procs.append((g, subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(30 if tag == "pilot" else 300)
        for g, _ in procs:
            lines = [l for l in open(f"{{tag}}_gpu{{g}}.txt").read().splitlines() if l.strip()]
            print(f"[{{(time.time()-t0)/60:5.1f}} min gpu{{g}}] " + (lines[-1][:200] if lines else "starting"), flush=True)
    for g, p in procs:
        print(f"--- gpu{{g}} (exit {{p.returncode}}) ---\\n" + open(f"{{tag}}_gpu{{g}}.txt").read()[-4000:])
    return all(p.returncode == 0 for _, p in procs)


GO = run("pilot") and len(glob.glob("pilot_*.json")) == len(MODELS)
print("Pilot passed; full run starting." if GO else "Pilot FAILED; full run skipped.")'''

FULL = '''if GO:
    run("full")
r = subprocess.run([sys.executable, "run.py", "report"], capture_output=True, text=True)
print(r.stdout[-20000:], r.stderr[-3000:])'''

head = ("# Loop concept vs loop syntax\n\nDoes a small model know *what loop to write* and only trip on *how to spell it*? "
        "25 loop tasks, in Python (known), Zig 0.17 (real, too new for the model) and Plink (made up), each asked cold "
        "and with a generic looked-up syntax snippet. Every program is run and checked. Results: `RESULTS.md`.")
cells = [{"cell_type": "markdown", "metadata": {}, "source": head}]
for src in (SETUP, RUN, FULL):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "loop_concept.ipynb").write_text(json.dumps(nb, indent=1))
print("loop_concept.ipynb")
