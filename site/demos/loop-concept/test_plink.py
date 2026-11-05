"""Check the browser Plink (plink.js) against the experiment's plink.py on every Plink program the models wrote.

  python3 site/demos/loop-concept/test_plink.py      (needs node)

Both must agree on the kind of result (ran / syntax error / runtime error), the printed output and the
exact syntax error message.
"""
import glob, json, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parents[2] / "experiments" / "loop-concept"
sys.path.insert(0, str(EXP))
import run  # noqa: E402


def programs():
    progs = {run.CARDS["plink"]}
    for f in glob.glob(str(EXP / "kaggle-out" / "full_*.json")):
        progs |= {run.extract(r["reply"]) for r in json.load(open(f))["rows"] if r["lang"] == "plink"}
    for f in glob.glob(str(EXP / "kaggle-out*" / "agent_full_*plink.json")):
        for c in json.load(open(f))["convs"]:
            progs |= {c[k] for k in ("final_code", "last_run_code", "graded_code") if c.get(k)}
            for m in c["msgs"]:
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", tc)
                    args = fn.get("arguments")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            continue
                    if fn.get("name") == "run" and isinstance(args, dict) and args.get("code"):
                        progs.add(args["code"])
    return sorted(progs)


def python_result(src):
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "p.plk"
        f.write_text(src)
        try:
            r = subprocess.run([sys.executable, "-I", str(EXP / "plink.py"), str(f)], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            return {"kind": "runtime", "stdout": "", "error": ""}
    kind = {0: "ok", 2: "syntax"}.get(r.returncode, "runtime")
    return {"kind": kind, "stdout": r.stdout.rstrip("\n"), "error": r.stderr.strip()}


JS = """
import fs from 'fs';
import { runReport } from '%s';
const progs = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify(progs.map(p => runReport(p))));
""" % (HERE / "plink.js").as_posix()

if __name__ == "__main__":
    progs = programs()
    js = json.loads(subprocess.run(["node", "--input-type=module", "-e", JS], input=json.dumps(progs),
                                   capture_output=True, text=True, check=True).stdout)
    bad = 0
    for src, j in zip(progs, js):
        p = python_result(src)
        same = j["kind"] == p["kind"] and (p["kind"] != "ok" or j["stdout"] == p["stdout"]) \
            and (p["kind"] != "syntax" or j["error"] == p["error"])
        if not same:
            bad += 1
            print("MISMATCH\n", src[:300], "\n python:", p, "\n js:", j, "\n")
    print(f"{len(progs) - bad} of {len(progs)} programs agree")
    sys.exit(1 if bad else 0)
