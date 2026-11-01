"""Loop concept vs loop syntax: does a small model already know *what loop to write* and only trip on *how to spell it*?

Each task ("print the squares of 1 to 10") is asked in three languages, each two ways:
  cold     just the task
  snippet  the task plus a generic syntax snippet for that language, the kind you'd look up (no hints about the task)
Languages:
  python   the model knows it: shows whether it gets the concept at all
  zig      Zig 0.17, real but newer than the model's training data, and fussy (signed % is an error, etc.)
  plink    a made-up language (plink.py): can't have been memorised, so the snippet is the only way to learn its spelling
Every program is run and its output compared with the right answer. Failures are split into
  syntax   didn't compile / parse
  wrong    ran but printed the wrong thing (or crashed at run time, or timed out)
If the snippet turns syntax failures into passes, the model had the concept and only lacked the spelling.

  python run.py check                        run the reference programs through the graders
  python run.py worker --model Qwen/Qwen3-0.6B --gpu 0 --tag pilot|full
  python run.py report
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

HERE = pathlib.Path(__file__).resolve().parent
LANGS = ["python", "zig", "plink"]
ARMS = ["cold", "snippet"]
SAMPLES = 5  # answers per task per cell: 1 greedy + 4 sampled


# ---------------------------------------------------------------- tasks (expected output computed in Python)

def _primes(n):
    return [p for p in range(2, n) if all(p % d for d in range(2, p))]


def _fib(k):
    a, b, out = 0, 1, []
    for _ in range(k):
        out.append(a)
        a, b = b, a + b
    return out


def _collatz(n):
    s = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        s += 1
    return s


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def _fizz(i):
    return "FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i)


def _running(xs):
    t, out = 0, []
    for x in xs:
        t += x
        out.append(t)
    return out


TASKS = [
    ("sum100", "adds up the whole numbers from 1 to 100 and prints the total", [5050]),
    ("evens", "prints the even numbers from 0 to 20 (including 20)", list(range(0, 21, 2))),
    ("countdown", "counts down from 10 to 1, printing each number", list(range(10, 0, -1))),
    ("fact10", "computes 10 factorial (10 * 9 * ... * 1) with a loop and prints it", [3628800]),
    ("fib15", "prints the first 15 Fibonacci numbers, starting 0, 1, 1, 2", _fib(15)),
    ("squares", "prints the square of each number from 1 to 10", [i * i for i in range(1, 11)]),
    ("times7", "prints the 7 times table: 7, 14, 21, up to 70", [7 * i for i in range(1, 11)]),
    ("arrsum", "stores the numbers 4, 8, 15, 16, 23, 42 in an array/list, adds them up with a loop and prints the total",
     [108]),
    ("arrmax", "stores the numbers 12, 45, 7, 89, 23, 56 in an array/list, finds the largest with a loop and prints it",
     [89]),
    ("oddcount", "stores the numbers 3, 7, 10, 15, 22, 9, 8 in an array/list and prints how many of them are odd", [4]),
    ("primes", "prints every prime number below 50", _primes(50)),
    ("digitsum", "adds up the digits of 98765 using a loop (not string tricks) and prints the sum", [35]),
    ("gcd", "finds the greatest common divisor of 1071 and 462 with a loop (Euclid's method) and prints it", [21]),
    ("collatz", "starts at 27 and repeatedly halves it if even or replaces it with 3*n+1 if odd, until it reaches 1; "
                "prints how many steps that took", [_collatz(27)]),
    ("pow2", "prints the powers of 2 from 1 up to 1024 (1, 2, 4, ..., 1024)", [2 ** i for i in range(11)]),
    ("reverse", "stores 5, 10, 15, 20 in an array/list and prints them in reverse order (20 first)", [20, 15, 10, 5]),
    ("fizzbuzz", "prints FizzBuzz for 1 to 15: Fizz for multiples of 3, Buzz for multiples of 5, FizzBuzz for both, "
                 "otherwise the number", [_fizz(i) for i in range(1, 16)]),
    ("stars", "prints a triangle of stars 5 rows tall: row 1 is *, row 2 is **, up to ***** (no spaces)",
     ["*" * i for i in range(1, 6)]),
    ("mult35", "adds up every number below 100 that is a multiple of 3 or 5 and prints the total",
     [sum(i for i in range(100) if i % 3 == 0 or i % 5 == 0)]),
    ("odds", "prints the odd numbers from 1 to 19 by stepping 2 at a time", list(range(1, 20, 2))),
    ("running", "stores 1, 2, 3, 4, 5 in an array/list and prints the running total after each one (1, 3, 6, ...)",
     _running([1, 2, 3, 4, 5])),
    ("down3", "counts down from 30 to 0 in steps of 3, printing each number (30, 27, ..., 0)", list(range(30, -1, -3))),
    ("pairs", "prints every pair i j for i from 1 to 3 and j from 1 to 2, one pair per line as two numbers separated "
              "by a space (1 1, then 1 2, then 2 1, ...)", [f"{i} {j}" for i in range(1, 4) for j in range(1, 3)]),
    ("indexed", "stores 9, 8, 7 in an array/list and prints each position and value, one per line as two numbers "
                "separated by a space, positions starting at 0 (0 9, then 1 8, then 2 7)",
     [f"{i} {v}" for i, v in enumerate([9, 8, 7])]),
    ("revnum", "reverses the digits of 12345 with a loop (not string tricks) and prints the result", [54321]),
]
TASKS = [(tid, desc, "\n".join(str(x) for x in exp)) for tid, desc, exp in TASKS]
PILOT_TASKS = ["sum100", "arrmax", "fizzbuzz"]


# ---------------------------------------------------------------- syntax snippets (generic: nothing task-specific)

CARDS = {
    "python": '''# variables
total = 0
nums = [3, 1, 4]
# counting loop: i takes 1, 2, ..., 10 (the end of range is excluded); a third argument is the step
for i in range(1, 11):
    total += i
# loop over the items of a list
for x in nums:
    if x % 2 == 0:
        print(x, "even")
    else:
        print(x)
# loop over positions with their values
for k, x in enumerate(nums):
    print(k, x)
# loop while a condition holds; break leaves a loop early
n = 10
while n > 0:
    n = n // 2
    if n == 1:
        break
print("total: " + str(total))''',
    "zig": '''const std = @import("std");

pub fn main() void {
    // variables: var can change, const can't
    var total: i64 = 0;
    const nums = [_]i64{ 3, 1, 4 };
    // counting loop: i takes 1, 2, ..., 10 (the end of 1..11 is excluded); step with the : (i += step) part
    var i: i64 = 1;
    while (i <= 10) : (i += 1) {
        total += i;
    }
    // loop over the items of an array
    for (nums) |x| {
        // signed integers need @mod / @divTrunc, not % and /
        if (@mod(x, 2) == 0) {
            std.debug.print("{d} even\\n", .{x});
        } else {
            std.debug.print("{d}\\n", .{x});
        }
    }
    // loop over positions 0 .. nums.len-1 with their values
    for (nums, 0..) |x, k| {
        std.debug.print("{d} {d}\\n", .{ k, x });
    }
    // loop while a condition holds; break leaves a loop early
    var n: i64 = 10;
    while (n > 0) {
        n = @divTrunc(n, 2);
        if (n == 1) break;
    }
    // print a number, then text
    std.debug.print("total: {d}\\n", .{total});
    std.debug.print("{s}\\n", .{"done"});
}''',
    "plink": '''note variables: let declares a new one, set changes it
let total be 0
let nums be list(3, 1, 4)
note counting loop: i takes 1, 2, ..., 10 (both ends included); "by" sets the step, which may be negative
count i from 1 to 10 by 1
  set total to total + i
end
note loop over the items of a list
for each x in nums
  if x mod 2 = 0
    show x, "even"
  otherwise
    show x
  end
end
note loop over positions 0 .. size(nums) - 1; item(nums, k) is the value at position k
for each index k in nums
  show k, item(nums, k)
end
note loop while a condition holds; stop leaves a loop early
let n be 10
while n > 0
  set n to n div 2
  if n = 1
    stop
  end
end
note operators: + - * div mod, = <> < > <= >=, and or not; & joins text, text(n) turns a number into text
show "total: " & text(total)''',
}
NICE = {"python": "Python", "zig": "Zig 0.17", "plink": "Plink"}
PLINK_INTRO = "Plink is a small programming language. "
FENCE = {"python": "python", "zig": "zig", "plink": "plink"}


def prompt(lang, arm, desc):
    head = PLINK_INTRO if lang == "plink" else ""
    if arm == "snippet":
        head += (f"Here is a reference snippet showing {NICE[lang]} syntax, looked up from the docs:\n\n"
                 f"```{FENCE[lang]}\n{CARDS[lang]}\n```\n\n")
    return (head + f"Write a complete {NICE[lang]} program that {desc}. Print each value on its own line and nothing "
            f"else. Reply with only the code, in one code block.")


# ---------------------------------------------------------------- graders

def extract(reply):
    blocks = re.findall(r"```[^\n`]*\n(.*?)```", reply, re.S)
    if blocks:
        return blocks[0]
    m = re.search(r"```[^\n`]*\n(.*)", reply, re.S)  # unterminated block
    return m.group(1) if m else reply


def zig_cmd():
    return [sys.executable, "-m", "ziglang"]


def grade(lang, code, expected):
    """-> (verdict, detail) where verdict is pass | syntax | wrong."""
    with tempfile.TemporaryDirectory() as d:
        ext = {"python": "py", "zig": "zig", "plink": "plk"}[lang]
        f = pathlib.Path(d) / f"main.{ext}"
        f.write_text(code)
        if lang == "python":
            try:
                compile(code, "main.py", "exec")
            except SyntaxError as e:
                return "syntax", str(e)[:300]
            cmd, limit = [sys.executable, "-I", str(f)], 10
        elif lang == "plink":
            cmd, limit = [sys.executable, "-I", str(HERE / "plink.py"), str(f)], 10
        else:
            cmd, limit = zig_cmd() + ["run", str(f)], 120
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=limit, cwd=d)
        except subprocess.TimeoutExpired:
            return "wrong", "timeout"
    if lang == "zig":
        # Zig's std.debug.print writes to stderr, so the program's output can be on either stream;
        # compile errors look like "main.zig:3:5: error: ..."
        if re.search(r"main\.zig:\d+:\d+: error:", r.stderr):
            return "syntax", r.stderr[-600:]
        out = r.stdout + r.stderr
    elif lang == "plink":
        if r.returncode == 2:
            return "syntax", r.stderr[-300:]
        out = r.stdout
    else:
        out = r.stdout
    got = "\n".join(l.rstrip() for l in out.strip().splitlines())
    if r.returncode == 0 and got == expected:
        return "pass", ""
    return "wrong", (f"exit {r.returncode}; got {got[:200]!r}" + (f"; err {r.stderr[-200:]!r}" if r.stderr else ""))


# ---------------------------------------------------------------- reference programs, to check the graders

GOLD = {
    ("python", "sum100"): "t = 0\nfor i in range(1, 101):\n    t += i\nprint(t)\n",
    ("python", "stars"): "for i in range(1, 6):\n    print('*' * i)\n",
    ("plink", "sum100"): "let t be 0\ncount i from 1 to 100\n set t to t + i\nend\nshow t\n",
    ("plink", "down3"): "count i from 30 to 0 by -3\n show i\nend\n",
    ("plink", "arrmax"): "let xs be list(12, 45, 7, 89, 23, 56)\nlet best be item(xs, 0)\nfor each x in xs\n"
                         " if x > best\n  set best to x\n end\nend\nshow best\n",
    ("plink", "fizzbuzz"): "count i from 1 to 15\n if i mod 15 = 0\n  show \"FizzBuzz\"\n orif i mod 3 = 0\n"
                           "  show \"Fizz\"\n orif i mod 5 = 0\n  show \"Buzz\"\n otherwise\n  show i\n end\nend\n",
    ("plink", "stars"): "for i in range(1, 6):\n    print('*' * i)\n",  # Python spelling: must be a syntax fail
    ("plink", "squares"): "count i from 1 to 10\n show i * i\nend\n",
    ("plink", "pairs"): "count i from 1 to 3\n count j from 1 to 2\n  show i, j\n end\nend\n",
    ("plink", "indexed"): "let xs be list(9, 8, 7)\nfor each index k in xs\n show k, item(xs, k)\nend\n",
    ("plink", "collatz"): "let n be 27\nlet s be 0\nwhile n <> 1\n if n mod 2 = 0\n  set n to n div 2\n otherwise\n"
                          "  set n to 3 * n + 1\n end\n set s to s + 1\nend\nshow s\n",
    ("zig", "sum100"): "const std = @import(\"std\");\npub fn main() void {\n    var t: i64 = 0;\n"
                       "    for (1..101) |i| { t += @intCast(i); }\n    std.debug.print(\"{d}\\n\", .{t});\n}\n",
    ("zig", "evens"): "const std = @import(\"std\");\npub fn main() void {\n    var i: i64 = 0;\n"
                      "    while (i <= 20) : (i += 2) { if (@mod(i, 2) == 0) std.debug.print(\"{d}\\n\", .{i}); }\n}\n",
    ("zig", "countdown"): "const std = @import(\"std\");\npub fn main() void {\n    var i: i64 = 10;\n"
                          "    while (i >= 1) : (i -= 1) { if (i % 2 == 0) {} std.debug.print(\"{d}\\n\", .{i}); }\n}\n",
}
GOLD_EXPECT = {("plink", "stars"): "syntax", ("zig", "countdown"): "syntax"}


def check():
    exp = {t: e for t, _, e in TASKS}
    ok = True
    for (lang, tid), code in GOLD.items():
        v, d = grade(lang, code, exp[tid])
        want = GOLD_EXPECT.get((lang, tid), "pass")
        print(f"{'ok ' if v == want else 'BAD'} {lang:6} {tid:9} {v:6} (want {want}) {d[:120]}")
        ok &= v == want
    for lang in LANGS:  # the cards themselves must run
        v, d = grade(lang, CARDS[lang], "__never__")
        print(f"{'ok ' if v == 'wrong' and 'exit 0' in d else 'BAD'} card {lang}: {v} {d[:100]}")
        ok &= v == "wrong" and "exit 0" in d
    print("ALL OK" if ok else "SOMETHING WRONG")
    return ok


# ---------------------------------------------------------------- generation

def worker(model_name, gpu, tag):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(model_name)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    try:
        model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float16)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
    model = model.cuda().eval()
    tasks = [t for t in TASKS if t[0] in PILOT_TASKS] if tag == "pilot" else TASKS
    samples = 1 if tag == "pilot" else SAMPLES
    jobs = []  # (lang, arm, tid, expected, chat text)
    for lang in LANGS:
        for arm in ARMS:
            for tid, desc, expected in tasks:
                msgs = [{"role": "user", "content": prompt(lang, arm, desc)}]
                try:
                    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                                   enable_thinking=False)
                except TypeError:
                    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                jobs.append((lang, arm, tid, expected, text))

    def generate(texts, sample):
        outs = []
        for i in range(0, len(texts), 16):
            batch = tok(texts[i:i + 16], return_tensors="pt", padding=True).to("cuda")
            kw = dict(do_sample=True, temperature=0.7, top_p=0.95) if sample else dict(do_sample=False)
            with torch.no_grad():
                g = model.generate(**batch, max_new_tokens=700, pad_token_id=tok.pad_token_id, **kw)
            outs += tok.batch_decode(g[:, batch["input_ids"].shape[1]:], skip_special_tokens=True)
            print(f"  generated {len(outs)}/{len(texts)} ({'sampled' if sample else 'greedy'}, {time.time()-t0:.0f}s)",
                  flush=True)
        return outs

    texts = [j[4] for j in jobs]
    replies = [(0, r) for r in generate(texts, False)]
    for s in range(1, samples):
        torch.manual_seed(s)
        replies += [(s, r) for r in generate(texts, True)]
    print(f"generation done in {time.time()-t0:.0f}s; grading", flush=True)

    rows = []
    with cf.ThreadPoolExecutor(4) as ex:
        futs = []
        for k, (s, reply) in enumerate(replies):
            lang, arm, tid, expected, _ = jobs[k % len(jobs)]
            code = extract(reply)
            futs.append((dict(lang=lang, arm=arm, task=tid, sample=s, reply=reply),
                         ex.submit(grade, lang, code, expected)))
        for row, fut in futs:
            row["verdict"], row["detail"] = fut.result()
            rows.append(row)
    slug = model_name.split("/")[-1].lower()
    out = {"model": model_name, "tag": tag, "seconds": round(time.time() - t0), "rows": rows}
    pathlib.Path(f"{tag}_{slug}.json").write_text(json.dumps(out, indent=1))
    for lang in LANGS:
        for arm in ARMS:
            g = [r for r in rows if r["lang"] == lang and r["arm"] == arm and r["sample"] == 0]
            print(f"  {lang:6} {arm:7} greedy pass {sum(r['verdict'] == 'pass' for r in g)}/{len(g)}  "
                  f"syntax-fail {sum(r['verdict'] == 'syntax' for r in g)}", flush=True)
    print(f"== {model_name} {tag} done in {out['seconds']}s", flush=True)


# ---------------------------------------------------------------- report

def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def report():
    lines = ["# Loop concept vs syntax: results", ""]
    for f in sorted(pathlib.Path(".").glob("full_*.json")):
        d = json.load(open(f))
        rows = d["rows"]
        n_tasks = len({r["task"] for r in rows})
        n_samp = len({r["sample"] for r in rows})
        lines += [f"## {d['model']}", "",
                  f"{n_tasks} tasks; each cell is 1 greedy answer + {n_samp - 1} sampled answers per task "
                  f"({n_tasks * n_samp} programs). 'solved' = at least one of the {n_samp} answers passed.", "",
                  "| language | arm | greedy pass | all answers: pass | syntax fail | wrong output | tasks solved |",
                  "|---|---|---|---|---|---|---|"]
        for lang in LANGS:
            for arm in ARMS:
                c = [r for r in rows if r["lang"] == lang and r["arm"] == arm]
                g = [r for r in c if r["sample"] == 0]
                solved = len({r["task"] for r in c if r["verdict"] == "pass"})
                lines.append(f"| {NICE[lang]} | {arm} | {pct(sum(r['verdict'] == 'pass' for r in g), len(g))} | "
                             f"{pct(sum(r['verdict'] == 'pass' for r in c), len(c))} | "
                             f"{pct(sum(r['verdict'] == 'syntax' for r in c), len(c))} | "
                             f"{pct(sum(r['verdict'] == 'wrong' for r in c), len(c))} | {solved}/{n_tasks} |")
        # the key cross-tab: tasks it solves in Python (has the concept) -> solved in the other language?
        py_solved = {r["task"] for r in rows if r["lang"] == "python" and r["arm"] == "cold" and r["verdict"] == "pass"}
        lines += ["", f"Tasks it solves in plain Python (it has the concept): {len(py_solved)}/{n_tasks}. "
                  "Of those, how many it also solves in:", ""]
        for lang in ["zig", "plink"]:
            for arm in ARMS:
                s = {r["task"] for r in rows if r["lang"] == lang and r["arm"] == arm and r["verdict"] == "pass"}
                lines.append(f"- {NICE[lang]} {arm}: {len(s & py_solved)}/{len(py_solved)}")
        lines += ["", "Per task (greedy answer; P pass, S syntax fail, W wrong output):", "",
                  "| task | " + " | ".join(f"{NICE[l]} {a}" for l in LANGS for a in ARMS) + " |",
                  "|---|" + "---|" * (len(LANGS) * len(ARMS))]
        for tid, _, _ in TASKS:
            cells = []
            for lang in LANGS:
                for arm in ARMS:
                    r = [r for r in rows if r["task"] == tid and r["lang"] == lang and r["arm"] == arm
                         and r["sample"] == 0]
                    cells.append({"pass": "P", "syntax": "S", "wrong": "W"}[r[0]["verdict"]] if r else "-")
            lines.append(f"| {tid} | " + " | ".join(cells) + " |")
        lines.append("")
    pathlib.Path("RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "worker", "report"])
    ap.add_argument("--model")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--tag", default="full")
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(0 if check() else 1)
    elif a.cmd == "worker":
        worker(a.model, a.gpu, a.tag)
    else:
        report()
