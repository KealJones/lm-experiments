"""Scores a whiteboard run (python score.py hf-1).
1. Notes recall (tests 1-12): which answer-key facts are in the final notes file (needles.py, same as the
   retrieval check in context-packets), and whether a changed fact's old value is marked as old.
2. Notes behaviour: how often the model edited the file when nudged, file size, tool use, thinking overruns.
3. Blind grading sheet: every arm's final answer per test under shuffled letters (GRADING.md + mapping.json).
"""
import json, os, random, re, sys
from needles import NEEDLES

D = sys.argv[1]
recs = {}
for f in os.listdir(D):
    if f.endswith(".json") and "-" in f and f.split("-")[0] in ("notes", "window", "full"):
        r = json.load(open(os.path.join(D, f)))
        recs[(r["arm"], r["chat"])] = r


def answer_text(r):
    steps = r.get("answer") or []
    last = steps[-1] if steps else {}
    return last.get("text", ""), steps


def hits(text, nds):
    return [all(re.search(p, text or "", re.I) for p in nd) for nd in nds]


lines = ["# Whiteboard run: scores", ""]
lines += ["## Notes recall (final notes file, tests 1-12)", "", "| test | needles in notes | notes words | turns edited / nudged | remember calls |", "|---|---|---|---|---|"]
tot_h = tot_n = full_ok = 0
for t in range(1, 13):
    r = recs.get(("notes", t))
    if not r: continue
    notes = r.get("final_notes") or ""
    h = hits(notes, NEEDLES[t])
    tot_h += sum(h); tot_n += len(h); full_ok += all(h)
    ups = r["updates"]
    lines.append(f"| {t} | {sum(h)}/{len(h)} | {len(notes.split())} | {sum(u['changed'] for u in ups)}/{len(ups)} | {len(r.get('remembered', []))} |")
if tot_n:
    lines += ["", f"All needles in notes: {full_ok}/12. Needle recall: {tot_h}/{tot_n} ({tot_h / tot_n:.0%})."]

# behaviour
calls, overrun, rounds_out, cmds = 0, 0, 0, {}
for (arm, t), r in recs.items():
    steps = [s for u in r.get("updates", []) for s in u["trace"]] + (r.get("answer") or [])
    for s in steps:
        overrun += not s.get("finished_thinking", True)
        rounds_out += s.get("note") == "out of tool rounds"
        for c in s.get("calls", []):
            calls += 1
            k = c["name"] if c["name"] != "bash" else "bash:" + (str(c["arguments"].get("command", "")).split() or ["?"])[0]
            cmds[k] = cmds.get(k, 0) + 1
lines += ["", "## Behaviour", "", f"Generations that ran out of room while still thinking: {overrun}. Tool loops cut off: {rounds_out}.",
          "Tool calls by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(cmds.items(), key=lambda x: -x[1]))]

# needles in the final answers (all arms), as a cheap first look before grading
lines += ["", "## Needles in the final answer (cheap check, not the grade)", "", "| test | notes | window | full |", "|---|---|---|---|"]
for t in range(1, 17):
    row = []
    for arm in ("notes", "window", "full"):
        r = recs.get((arm, t))
        row.append(f"{sum(hits(answer_text(r)[0], NEEDLES[t]))}/{len(NEEDLES[t])}" if r else "-")
    lines.append(f"| {t} | " + " | ".join(row) + " |")
open(os.path.join(D, "SCORES.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))

# blind sheet
rng = random.Random(11)
keys = "../context-packets/data/keys"
sheet, mapping = ["# Blind grading sheet", ""], {}
for t in range(1, 17):
    arms = [a for a in ("notes", "window", "full") if (a, t) in recs]
    rng.shuffle(arms)
    mapping[t] = {chr(65 + i): a for i, a in enumerate(arms)}
    q = json.load(open("data.json"))[t - 1]["question"]
    sheet += [f"## Test {t}", "", f"**Question:** {q}", "", "**Key:** " + open(f"{keys}/key{t}.txt").read().strip(), ""]
    for i, a in enumerate(arms):
        sheet += [f"### Reply {chr(65 + i)}", "", answer_text(recs[(a, t)])[0] or "(no reply text)", ""]
open(os.path.join(D, "GRADING.md"), "w").write("\n".join(sheet))
json.dump(mapping, open(os.path.join(D, "mapping.json"), "w"), indent=1)
