"""Builds agent_gemma.ipynb for Kaggle: llama.cpp (CUDA, T4) serving Gemma 4 E2B on GPU 0 and Keal's tiny Gemma 4 on
GPU 1; the from-scratch-with-tools test (gemma_agent.py) against each. Pilot first, then the full run, then the report."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
FILES = ["run.py", "plink.py", "agent.py", "gemma_agent.py", "docs/zig/langref.txt", "docs/plink/reference.txt"]
B64 = {f: base64.b64encode((here / f).read_bytes()).decode() for f in FILES}
LLAMA_CPP = "785322d"  # commit tested locally

SETUP = f'''import base64, os, subprocess, sys, time
for f, b in {json.dumps(B64)}.items():
    os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
    open(f, "wb").write(base64.b64decode(b))
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ziglang==0.17.0"], check=True)
r = subprocess.run([sys.executable, "run.py", "check"], capture_output=True, text=True)
print(r.stdout[-800:], r.stderr[-800:])
assert r.returncode == 0, "grader check failed"
t0 = time.time()
sh = lambda c: subprocess.run(c, shell=True, check=True, capture_output=True, text=True)
sh("git clone -q https://github.com/ggml-org/llama.cpp && cd llama.cpp && git checkout -q {LLAMA_CPP}")
os.environ["PATH"] = "/usr/local/cuda/bin:" + os.environ["PATH"]
r = subprocess.run("cd llama.cpp && cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 -DLLAMA_CURL=OFF "
                   "-DLLAMA_BUILD_TESTS=OFF && cmake --build build --target llama-server -j 4", shell=True,
                   capture_output=True, text=True)
print(r.stdout[-1500:], r.stderr[-3000:])
assert r.returncode == 0, "llama.cpp build failed"
print(f"llama.cpp built in {{(time.time()-t0)/60:.1f}} min")'''

SERVE = '''import json, urllib.request
from huggingface_hub import hf_hub_download
import gemma_agent as G
servers = {}
for gpu, (name, port) in enumerate([("gemma4-e2b", 8080), ("tiny-gemma4", 8081)]):
    repo, fname, _ = G.MODELS[name]
    path = hf_hub_download(repo, fname)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
    log = open(f"server_{name}.txt", "w")
    servers[name] = (subprocess.Popen(["llama.cpp/build/bin/llama-server", "-m", path, "-ngl", "99", "-c", "98304",
                                       "-np", "6", "--port", str(port), "-fa", "on"],
                                      env=env, stdout=log, stderr=subprocess.STDOUT), f"http://127.0.0.1:{port}")
for name, (p, url) in servers.items():
    for _ in range(300):
        try:
            if json.loads(urllib.request.urlopen(url + "/health", timeout=5).read()).get("status") == "ok":
                break
        except Exception:
            pass
        assert p.poll() is None, open(f"server_{name}.txt").read()[-3000:]
        time.sleep(2)
    print(name, "server up at", url)'''

RUN = '''import glob


def go(tag):
    procs = []
    for name, (_, url) in servers.items():
        log = open(f"agent_{tag}_{name}.txt", "w")
        procs.append((name, subprocess.Popen([sys.executable, "-u", "gemma_agent.py", "worker", "--model", name,
                                              "--server", url, "--tag", tag], stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(30 if tag == "pilot" else 300)
        for name, _ in procs:
            lines = [l for l in open(f"agent_{tag}_{name}.txt").read().splitlines() if l.strip()]
            print(f"[{(time.time()-t0)/60:5.1f} min {name}] " + (lines[-1][:200] if lines else "starting"), flush=True)
    for name, p in procs:
        print(f"--- {name} (exit {p.returncode}) ---\\n" + open(f"agent_{tag}_{name}.txt").read()[-3000:])
    return all(p.returncode == 0 for _, p in procs)


GO = go("pilot") and len(glob.glob("agent_pilot_*_*.json")) == 4
print("Pilot passed; full run starting." if GO else "Pilot FAILED; full run skipped.")
if GO:
    go("full")
for name, (p, _) in servers.items():
    p.terminate()
r = subprocess.run([sys.executable, "agent.py", "report"], capture_output=True, text=True)
print(r.stdout[-10000:], r.stderr[-3000:])'''

head = ("# From scratch with tools: Gemma\n\nGemma 4 E2B and Keal's tiny Gemma 4 (llama.cpp) get only the task "
        "(write a Zig 0.17 / Plink program that ...) and tools to list, grep and read the docs and run code, "
        "up to 15 turns, in Gemma 4's native tool format. Results: `AGENT_RESULTS.md`.")
cells = [{"cell_type": "markdown", "metadata": {}, "source": head}]
for src in (SETUP, SERVE, RUN):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "agent_gemma.ipynb").write_text(json.dumps(nb))
print("agent_gemma.ipynb", round(len(json.dumps(nb)) / 1e6, 2), "MB")
