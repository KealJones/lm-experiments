"""Build the factcheck demo's data from experiments/factcheck's raw outputs.

  python3 site/demos/factcheck/build_data.py

Writes data/index.json (questions, prompts, per-run scores, Haiku baseline, picked examples) and one
data/runs/<model>-<arm>.json per model and draft arm with trimmed transcripts, loaded when the visitor picks it.
The scores are recomputed from the transcripts and checked against the RESULTS.md tables they came from;
the script stops if any number disagrees.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parents[2] / "experiments" / "factcheck"
OUT = HERE / "data"

MODELS = {  # key in the results files -> name as its makers write it
    "qwen3": "Qwen3 0.6B",
    "qwen35": "Qwen3.5 0.8B",
    "llama": "Llama 3.2 1B",
    "coder": "Qwen2.5 Coder 1.5B",
}
RESULTS_NAME = {"qwen3": "Qwen3-0.6B", "qwen35": "Qwen3.5-0.8B", "llama": "Llama-3.2-1B-Instruct",
                "coder": "Qwen2.5-Coder-1.5B-Instruct"}
ARMS = ["free", "lookup", "think", "force", "read"]
ARM_TEXT = {
    "free": "tools offered, answer briefly",
    "lookup": "told to always look it up",
    "think": "tools offered, thinking on",
    "force": "made to search once first",
    "read": "handed the top Wikipedia paragraphs first",
}
RUNS = ["kaggle-out-3", "kaggle-out-4"]  # the README's numbers come from these two runs; 1-2 had harness bugs


def trim(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + " …"


def steps(item):
    """A transcript as a short list of steps; drops the system prompt and the user turn (shown separately)."""
    injected = sum(1 for t in item.get("tools") or [] if t.get("injected"))
    thinking = [t for t in (item.get("thinking") or []) if t is not None]
    out, calls_seen, gen = [], 0, 0
    for m in item["msgs"]:
        role = m["role"]
        if role in ("system", "user"):
            continue
        if role == "assistant":
            calls = m.get("tool_calls") or []
            is_injected = bool(calls) and calls_seen < injected and not (m.get("content") or "").strip()
            if not is_injected:
                if gen < len(thinking) and thinking[gen].strip():
                    out.append({"k": "think", "t": trim(thinking[gen], 450)})
                gen += 1
                if (m.get("content") or "").strip():
                    out.append({"k": "say", "t": trim(m["content"], 700)})
            for c in calls:
                fn = c.get("function", c)
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {"raw": args}
                out.append({"k": "call", "name": fn.get("name"), "args": args or {}, "by": "code" if is_injected else "model"})
                calls_seen += 1
        elif role == "tool":
            out.append({"k": "tool", "name": m.get("name", ""), "t": trim(m.get("content"), 300)})
    return out


def dedupe(data):
    """Move tool-result text into one shared list; steps keep an index ("i") into it."""
    texts, where = [], {}
    for x in data["drafts"] + data["reviews"]:
        for st in x["steps"]:
            if st["k"] == "tool":
                t = st.pop("t")
                if t not in where:
                    where[t] = len(texts)
                    texts.append(t)
                st["i"] = where[t]
    return texts


def score(drafts, reviews):
    """Same measures as RESULTS.md, per review style."""
    s = {"drafts": len(drafts), "draft_right": sum(d["correct"] for d in drafts), "styles": {}}
    calls = [t["name"] for d in drafts for t in d.get("tools") or [] if not t.get("injected")]
    s["calls_per_draft"] = round(len(calls) / len(drafts), 1)
    for style in ("plain", "strict"):
        own = [r for r in reviews if r["source"] == "own" and r["style"] == style]
        pl = [r for r in reviews if r["source"] == "planted" and r["style"] == style]
        wrong = [r for r in own if not r["draft_correct"]]
        right = [r for r in own if r["draft_correct"]]
        s["styles"][style] = {
            "caught": [sum(r["verdict"] == "wrong" for r in wrong), len(wrong)],
            "false_alarm": [sum(r["verdict"] == "wrong" for r in right), len(right)],
            "final_right": [sum(bool(r["final_correct"]) for r in own), len(own)],
            "fixed": [sum(bool(r["final_correct"]) for r in wrong), len(wrong)],
            "broke": [sum(not r["final_correct"] for r in right), len(right)],
            "planted_caught": [sum(r["verdict"] == "wrong" for r in pl), len(pl)] if pl else None,
            "planted_fixed": [sum(bool(r["final_correct"]) for r in pl), len(pl)] if pl else None,
        }
    return s


def check_against_results(key, arm, s, results_md):
    """Compare with the row in RESULTS.md, e.g. '| Qwen3-0.6B (read) | 24/36 (67%) | plain | 1/12 (8%) | ...'."""
    label = f"{RESULTS_NAME[key]} ({arm})"
    rows = [r for r in results_md.splitlines() if r.startswith(f"| {label} |")]
    if len(rows) != 2:
        sys.exit(f"no RESULTS.md rows for {label}")
    fr = lambda pair: f"{pair[0]}/{pair[1]}"
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        style = cells[2]
        st = s["styles"][style]
        mine = [f"{s['draft_right']}/{s['drafts']}", fr(st["caught"]), fr(st["false_alarm"]), fr(st["final_right"]),
                fr(st["fixed"]), fr(st["broke"]),
                fr(st["planted_caught"]) if st["planted_caught"] else "-",
                fr(st["planted_fixed"]) if st["planted_fixed"] else "-"]
        theirs = [cells[1], cells[3], cells[4], cells[5], cells[6], cells[7], cells[8], cells[9]]
        theirs = [t.split(" ")[0] for t in theirs]
        if mine != theirs:
            sys.exit(f"MISMATCH {label} {style}: mine {mine} vs RESULTS.md {theirs}")
    return True


def evidence_has_answer(item, q):
    """Read arm: does the text the code put in front of the model contain the answer?"""
    texts = []
    injected = sum(1 for t in item.get("tools") or [] if t.get("injected"))
    for m in item["msgs"]:
        if m["role"] == "tool" and injected > 0:
            texts.append(m.get("content") or "")
            injected -= 1
    return any(re.search(p, " ".join(texts), re.I) for p in q["accept"])


def main():
    questions = json.load(open(EXP / "questions.json"))
    qby = {q["id"]: q for q in questions}
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    runs, prompts, evidence_split, picks = [], {}, {}, {}
    for run in RUNS:
        results_md = (EXP / run / "RESULTS.md").read_text()
        for f in sorted((EXP / run).glob("results_full_*.json")):
            d = json.load(open(f))
            key, arm = d["key"], d["arm"]
            drafts, reviews = d["drafts"], d["reviews"]
            s = score(drafts, reviews)
            check_against_results(key, arm, s, results_md)
            # prompt text, once per arm and review style
            prompts.setdefault(f"draft:{arm}", next(m["content"] for m in drafts[0]["msgs"] if m["role"] == "system"))
            for style in ("plain", "strict"):
                r = next(r for r in reviews if r["style"] == style)
                system = next(m["content"] for m in r["msgs"] if m["role"] == "system")
                user = next(m["content"] for m in r["msgs"] if m["role"] == "user")
                user = re.sub(r"(QUESTION:) .*?\n\n(ANSWER[^:\n]*:) .*?\n\n", r"\1 …\n\n\2 …\n\n", user, flags=re.S)
                prompts.setdefault(f"review:{style}", system + "\n\n" + user)
            if arm == "read":
                split = {"in": [0, 0], "out": [0, 0]}
                for dr in drafts:
                    k = "in" if evidence_has_answer(dr, qby[dr["qid"]]) else "out"
                    split[k][0] += bool(dr["correct"])
                    split[k][1] += 1
                evidence_split[key] = split
            item = lambda x: {"steps": steps(x), "final": trim(x.get("final"), 700), "end": x.get("end")}
            data = {
                "drafts": [{"qid": x["qid"], "sample": x["sample"], "correct": bool(x["correct"]), **item(x)} for x in drafts],
                "reviews": [{"qid": x["qid"], "sample": x["sample"], "style": x["style"], "source": x["source"],
                             "draft_correct": bool(x["draft_correct"]), "verdict": x.get("verdict"),
                             "final_answer": trim(x.get("final_answer"), 400), "final_correct": bool(x.get("final_correct")),
                             **item(x)}
                            for x in reviews if x["source"] == "own" or x["sample"] == 0],  # planted: one sample each
            }
            data["texts"] = dedupe(data)  # tool results repeat a lot (the read arm's evidence is in every chat)
            json.dump(data, open(OUT / "runs" / f"{key}-{arm}.json", "w"), separators=(",", ":"))
            runs.append({"key": key, "arm": arm, "model": MODELS[key], "run": run, **s})
            # examples worth showing first
            for r in reviews:
                tag = None
                if r["source"] == "own" and r["style"] == "strict" and r["draft_correct"] and not r["final_correct"]:
                    tag = "broke"
                elif r["source"] == "own" and r["style"] == "plain" and not r["draft_correct"] and r["verdict"] == "right":
                    tag = "waved"
                elif r["source"] == "planted" and r["sample"] == 0 and r["verdict"] == "wrong" and r["final_correct"]:
                    tag = "caught"
                if tag:
                    picks.setdefault(tag, []).append({"key": key, "arm": arm, "qid": r["qid"], "sample": r["sample"],
                                                      "style": r["style"], "source": r["source"]})

    # README's evidence table, checked
    readme = (EXP / "README.md").read_text()
    for key, split in evidence_split.items():
        row = next(r for r in readme.splitlines() if r.startswith(f"| {MODELS[key]} |") and "/" in r and r.count("|") == 4)
        cells = [re.sub(r"\*", "", c).strip() for c in row.strip("|").split("|")]
        mine = [f"{split['in'][0]}/{split['in'][1]}", f"{split['out'][0]}/{split['out'][1]}"]
        if mine != cells[1:3]:
            sys.exit(f"MISMATCH evidence split {key}: mine {mine} vs README {cells[1:3]}")

    # Haiku baseline (web search, run as subagents; final answers and verdicts only, no transcripts)
    hd = json.load(open(EXP / "haiku" / "drafts.json"))
    hr = json.load(open(EXP / "haiku" / "reviews.json"))
    haiku = {
        "tools": hd["tools"],
        "drafts": {x["id"]: {"answer": x["answer"], "searches": x.get("searches"),
                             "correct": any(re.search(p, x["answer"], re.I) for p in qby[x["id"]]["accept"])}
                   for x in hd["drafts"]},
        "reviews": [{"qid": r["qid"], "source": "planted" if r["kind"] == "planted" else "own", "style": r["style"],
                     "answer": r["answer"], "verdict": r["verdict"], "final_answer": r["final_answer"],
                     "final_correct": r["final_correct"]} for r in hr],
    }
    assert sum(v["correct"] for v in haiku["drafts"].values()) == 12, "README: Haiku drafts 12/12"
    for style in ("plain", "strict"):
        pl = [r for r in haiku["reviews"] if r["source"] == "planted" and r["style"] == style]
        own = [r for r in haiku["reviews"] if r["source"] == "own" and r["style"] == style]
        assert sum(r["verdict"] == "wrong" for r in pl) == 12 == sum(r["final_correct"] for r in pl), style
        assert sum(r["verdict"] == "wrong" for r in own) == 0, style

    order = {k: i for i, k in enumerate(MODELS)}
    runs.sort(key=lambda r: (order[r["key"]], ARMS.index(r["arm"])))
    index = {
        "questions": [{"id": q["id"], "q": q["q"], "answer": q["answer"], "trap": q.get("trap"),
                       "planted": q["planted_wrong"], "accept": q["accept"]} for q in questions],
        "models": MODELS, "arms": ARM_TEXT, "prompts": prompts, "runs": runs,
        "evidence_split": {k: evidence_split[k] for k in MODELS if k in evidence_split}, "haiku": haiku,
    }
    json.dump(index, open(OUT / "index.json", "w"), separators=(",", ":"))
    total = sum(p.stat().st_size for p in OUT.rglob("*.json"))
    print(f"{len(runs)} runs, every score matches RESULTS.md; evidence split matches README; Haiku checks pass")
    print(f"data: {total / 1e6:.2f} MB total, index.json {(OUT / 'index.json').stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
