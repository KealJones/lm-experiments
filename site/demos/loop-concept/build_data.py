"""Build the loop-concept demo's data files from the experiment's raw outputs.

  python3 site/demos/loop-concept/build_data.py

Writes data/round1.json (every answer from the snippet test, with strict and lenient grades) and data/agents.json
(the tool-use transcripts from rounds 2 and 3). Lenient grading follows experiments/loop-concept/regrade.py:
Python and Plink answers are re-run here (model-written code, so it runs isolated with a timeout);
Zig answers keep their strict grade, which is what regrade.py's Zig numbers came to as well.
Run it again whenever loop-concept gets new results; the page reads only these two files.
"""
import concurrent.futures as cf
import glob
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EXP_DIR = HERE.parents[2] / "experiments" / "loop-concept"
sys.path.insert(0, str(EXP_DIR))
import run  # noqa: E402  (the experiment's own task list, snippets and code extractor)

OUT = HERE / "data"
MODELS = {"qwen3-0.6b": "Qwen3 0.6B", "qwen3-1.7b": "Qwen3 1.7B"}
AGENT_FILES = [  # (label, file pattern) for rounds 2 and 3
    ("Qwen3 0.6B", "kaggle-out-agent/agent_full_{lang}.json"),
    ("Gemma 4 E2B", "kaggle-out-gemma/agent_full_gemma4-e2b_{lang}.json"),
    ("Tiny Gemma 4", "kaggle-out-gemma/agent_full_tiny-gemma4_{lang}.json"),
]


def norm(line):
    line = line.strip()
    if re.search(r"[:=]\s*\S", line):
        line = re.sub(r"^[^:=]*[:=]\s*", "", line)  # drop a "label: " prefix
    return line.strip()


def execute(lang, code):
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / ("m.py" if lang == "python" else "m.plk")
        f.write_text(code)
        cmd = [sys.executable, "-I", str(f)] if lang == "python" else [sys.executable, "-I", str(EXP_DIR / "plink.py"), str(f)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=d)
        except subprocess.TimeoutExpired:
            return None
        return r.stdout if r.returncode == 0 else None


def lenient(row, expected):
    if row["verdict"] == "pass":
        return True
    if row["verdict"] == "syntax" or row["lang"] == "zig":
        return False
    out = execute(row["lang"], run.extract(row["reply"]))
    if out is None:
        return False
    got = [norm(x) for x in out.strip().splitlines() if x.strip()]
    exp = expected.split("\n")
    return got[-len(exp):] == exp


def trim(s, n):
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… ({len(s) - n} more characters)"


def round1():
    expected = {t: e for t, _, e in run.TASKS}
    models = {}
    for key, label in MODELS.items():
        rows = json.load(open(EXP_DIR / "kaggle-out" / f"full_{key}.json"))["rows"]
        with cf.ThreadPoolExecutor(8) as ex:
            flags = list(ex.map(lambda r: lenient(r, expected[r["task"]]), rows))
        models[key] = {
            "label": label,
            "rows": [{"lang": r["lang"], "arm": r["arm"], "task": r["task"], "sample": r["sample"],
                      "strict": r["verdict"], "lenient": ok, "code": run.extract(r["reply"]).rstrip(),
                      "detail": trim(r["detail"], 600)} for r, ok in zip(rows, flags)],
        }
    return {
        "tasks": [{"id": t, "desc": d, "expected": e} for t, d, e in run.TASKS],
        "snippets": run.CARDS,
        "langs": {"python": "Python", "zig": "Zig 0.17", "plink": "Plink"},
        "models": models,
    }


def tool_call(tc):
    fn = tc.get("function", tc)
    args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}
    return {"name": fn.get("name"), "args": args or {}}


def agents():
    out = []
    for label, pattern in AGENT_FILES:
        for lang in ("zig", "plink"):
            path = EXP_DIR / pattern.format(lang=lang)
            if not path.exists():
                continue
            for c in json.load(open(path))["convs"]:
                steps = []
                for m in c["msgs"]:
                    if m["role"] == "assistant":
                        steps.append({"role": "model", "text": trim(m.get("content"), 1500),
                                      "calls": [tool_call(t) for t in m.get("tool_calls") or []]})
                    elif m["role"] == "tool":
                        steps.append({"role": "tool", "name": m.get("name", ""), "text": trim(m.get("content"), 900)})
                out.append({"model": label, "lang": lang, "task": c["task"], "attempt": c["attempt"],
                            "verdict": c["verdict"], "end": c["end"], "turns": c["turns"], "tools": c["tools"],
                            "steps": steps})
    return out


def summary(r1):
    """Print the lenient table so it can be checked against the README."""
    for key, m in r1["models"].items():
        rows = m["rows"]
        py = {r["task"] for r in rows if r["lang"] == "python" and r["arm"] == "cold" and r["lenient"]}
        print(f"{m['label']}: Python cold solves {len(py)}")
        for lang in ("python", "zig", "plink"):
            for arm in ("cold", "snippet"):
                c = [r for r in rows if r["lang"] == lang and r["arm"] == arm]
                solved = {r["task"] for r in c if r["lenient"]}
                print(f"  {lang:6} {arm:7} pass {100 * sum(r['lenient'] for r in c) / len(c):3.0f}%  "
                      f"syntax {100 * sum(r['strict'] == 'syntax' for r in c) / len(c):3.0f}%  "
                      f"of python-solved {len(solved & py)}/{len(py)}")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    r1 = round1()
    summary(r1)
    json.dump(r1, open(OUT / "round1.json", "w"), separators=(",", ":"))
    ag = agents()
    json.dump(ag, open(OUT / "agents.json", "w"), separators=(",", ":"))
    for f in OUT.glob("*.json"):
        print(f.name, f"{f.stat().st_size / 1e6:.2f} MB")
