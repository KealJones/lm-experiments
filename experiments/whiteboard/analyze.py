"""What LFM3 did on each update turn, and what reached the notes file (python analyze.py hf-3).
Reads notes-N.json, or partial-notes-N.json for chats a time limit cut off. Writes ANALYSIS.md in that folder."""
import collections, glob, json, os, re, sys
from needles import NEEDLES

D = sys.argv[1]
data = {d["id"]: d for d in json.load(open("data.json"))}
WRITE = re.compile(r"(cat >|>>|sed -i|tee |printf .*>|echo .*>)")
NOTHING = re.compile(r"(nothing new|no new (info|information|details)|leave it as (it )?is|no changes? (needed|required))", re.I)


def kind(u):
    calls = [c for s in u["trace"] for c in s.get("calls", [])]
    if any(c["name"] == "bash" and WRITE.search(str(c["arguments"].get("command", ""))) for c in calls): return "wrote the file"
    if any(not s.get("finished_thinking", True) for s in u["trace"]): return "ran out of output (1,536 tokens) while still thinking"
    if NOTHING.search(" ".join(s["reasoning"] for s in u["trace"])[-800:]): return "decided nothing new"
    if calls: return "called tools, never wrote"
    return "finished thinking, then ended without a call"


total, by10 = collections.Counter(), collections.defaultdict(collections.Counter)
rows = ["| test | turns replayed | finished | wrote | notes words at the end | answer-key facts kept / said so far |", "|---|---|---|---|---|---|"]
for t in range(1, 17):
    f = f"{D}/notes-{t}.json"
    done = os.path.exists(f)
    if not done: f = f"{D}/partial-notes-{t}.json"
    if not os.path.exists(f): continue
    r = json.load(open(f)); ups = r["updates"]
    ks = [kind(u) for u in ups]
    for u, k in zip(ups, ks): total[k] += 1; by10[u["turn"] // 10][k] += 1
    notes = next((x for x in reversed(r["notes_history"]) if x), "") or ""
    upto = ups[-1]["msg_index"] + 2 if ups else 0
    said = "\n".join(m["content"] for m in data[t]["messages"][:upto])
    nd = [n for n in NEEDLES.get(t, []) if t <= 12 and all(re.search(p, said, re.I) for p in n)]
    kept = [n for n in nd if all(re.search(p, notes, re.I) for p in n)]
    n_user = sum(m["role"] == "user" for m in data[t]["messages"])
    rows.append(f"| {t} | {len(ups)}/{n_user} | {'yes' if done else 'no'} | {ks.count('wrote the file')} | {len(notes.split())} | " + (f"{len(kept)}/{len(nd)}" if t <= 12 else "-") + " |")
n = sum(total.values())
out = ["# What LFM3 did when asked to update its notes", "", f"{n} update turns.", "", "| what happened | turns | share |", "|---|---|---|"]
out += [f"| {k} | {v} | {v / n:.0%} |" for k, v in total.most_common()]
out += ["", "By turn number (writes happen early, then the growing file crowds them out):", "", "| turns | wrote | ran out while thinking | ended without a call |", "|---|---|---|---|"]
for b in sorted(by10):
    c = by10[b]
    out.append(f"| {b * 10 + 1}-{b * 10 + 10} | {c['wrote the file']} | {c['ran out of output (1,536 tokens) while still thinking']} | {c['finished thinking, then ended without a call']} |")
out += ["", "## Per chat", ""] + rows
open(f"{D}/ANALYSIS.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
