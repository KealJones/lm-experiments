import json, sys, re, subprocess, tempfile, pathlib, concurrent.futures as cf  # run from kaggle-out/: python ../regrade.py
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run
EXP = {t: e for t, _, e in run.TASKS}
COPY_MARKS = {"python": ["nums = [3, 1, 4]", '"even"'], "zig": ["{ 3, 1, 4 }", "even\\n"], "plink": ["list(3, 1, 4)", '"even"']}

def norm(l):
    l = l.strip()
    l = re.sub(r"^[^:=]*[:=]\s*", "", l) if re.search(r"[:=]\s*\S", l) else l  # drop "label: "
    return l.strip()

def execute(lang, code):
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / {"python": "m.py", "zig": "main.zig", "plink": "m.plk"}[lang]
        f.write_text(code)
        cmd = {"python": [sys.executable, "-I", str(f)], "plink": [sys.executable, "-I", str(run.HERE / "plink.py"), str(f)],
               "zig": [sys.executable, "-m", "ziglang", "run", str(f)]}[lang]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120 if lang == "zig" else 10, cwd=d)
        except subprocess.TimeoutExpired:
            return None
        return (r.stdout + (r.stderr if lang == "zig" else "")) if r.returncode == 0 else None

def lenient(row):
    if row["verdict"] == "pass": return True
    if row["verdict"] == "syntax": return False
    out = execute(row["lang"], run.extract(row["reply"]))
    if out is None: return False
    got = [norm(l) for l in out.strip().splitlines() if l.strip()]
    exp = EXP[row["task"]].split("\n")
    # pass if the expected lines appear contiguously, ending at the last line (answer printed last, extra stuff before is ok)
    return got[-len(exp):] == exp

for m in ["qwen3-0.6b", "qwen3-1.7b"]:
    rows = json.load(open(f"full_{m}.json"))["rows"]
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lenient, rows))
    for r, ok in zip(rows, res): r["lenient"] = ok
    py = {r["task"] for r in rows if r["lang"] == "python" and r["arm"] == "cold" and r["lenient"]}
    print(f"\n## {m}  (lenient: answer must be the last line(s), labels allowed)  python-cold solved {len(py)}/25")
    for lang in run.LANGS:
        for arm in run.ARMS:
            c = [r for r in rows if r["lang"] == lang and r["arm"] == arm]
            solved = {r["task"] for r in c if r["lenient"]}
            cp = sum(any(k in run.extract(r["reply"]) for k in COPY_MARKS[lang]) for r in c) if arm == "snippet" else 0
            print(f"{lang:6} {arm:7} pass {100*sum(r['lenient'] for r in c)/len(c):3.0f}%  syntax {100*sum(r['verdict']=='syntax' for r in c)/len(c):3.0f}%  "
                  f"solved {len(solved):2}/25  of-python-solved {len(solved & py):2}/{len(py)}" + (f"  copied-snippet-example {100*cp/len(c):.0f}%" if arm=='snippet' else ""))
    # what kind of syntax errors in zig cold
    errs = [re.search(r"error: (.{0,70})", r["detail"]) for r in rows if r["lang"] == "zig" and r["verdict"] == "syntax"]
    from collections import Counter
    print("  top zig errors:", Counter(re.sub(r"'[^']*'", "'X'", e.group(1)) for e in errs if e).most_common(5))
