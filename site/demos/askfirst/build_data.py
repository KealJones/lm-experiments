"""Build the askfirst demo's data from the experiment's saved outputs.

  python3 site/demos/askfirst/build_data.py

Reads experiments/askfirst/hf-out/{results.json,transcripts.json} and rebuilds the exact test scenarios
(askfirst.py draws them from random.Random(123), 30 per family, in TEST_FAMILIES order) so each saved
transcript can be shown next to the gold trajectory for the same scenario, and so the trip briefs the model
never found can be played in the browser. No model runs here.
"""
import difflib
import json
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parents[2] / "experiments" / "askfirst"
sys.path.insert(0, str(EXP))
import scenarios as S  # noqa: E402

N_TEST = 30
TAG = re.compile(r"<(think|ask|reply|fact|search|result|check|notes|answer)((?:\s+\w+=\"[^\"]*\")*)>(.*?)</\1>", re.S)
FAMILIES = {"gift": "Gift", "dinner": "Dinner", "code": "Code help", "given": "Everything given",
            "trip (unseen)": "Weekend trip (never trained)", "keal-mom": "Keal's mom", "keal-coeliac": "Keal's coeliac dinner",
            "keal-boustrophedon": "Keal's boustrophedon"}


def steps(text):
    out, pos = [], 0
    for m in TAG.finditer(text):
        gap = text[pos:m.start()].strip()
        if gap:
            out.append({"tag": "text", "body": gap})
        st = {"tag": m.group(1), "body": m.group(3).strip()}
        key = S.attrs_of(m.group(2)).get("key")
        if key:
            st["key"] = key
        out.append(st)
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        out.append({"tag": "text", "body": tail})
    return out


def test_scenarios():
    r = random.Random(123)
    tests = {k: [f(r) for _ in range(N_TEST)] for k, f in S.TEST_FAMILIES.items()}
    tests |= {k: [f(random.Random(5))] for k, f in S.KEAL.items()}
    return tests


def gold_text(sc):
    pieces, _, _ = S.render_gold(sc)
    return "".join(t for t, _ in pieces)


def main():
    res = json.load(open(EXP / "hf-out" / "results.json"))
    tr = json.load(open(EXP / "hf-out" / "transcripts.json"))
    tests = test_scenarios()

    fams = []
    for fam, label in FAMILIES.items():
        scs = tests[fam][:3]
        eps = {}
        for arm in ("untouched", "patched"):
            eps[arm] = []
            for i, e in enumerate(tr[arm][fam]):
                sc = scs[i]
                assert sc["request"] == e["request"], (fam, arm, i)  # same scenario as the run
                ep = {"request": e["request"], "ok": e["ok"], "parts": e["parts"], "steps": steps(e["text"])}
                if sc["gold"] and arm == "patched":
                    g = gold_text(sc)
                    ep["gold"] = steps(g)
                    ep["same_as_gold"] = round(difflib.SequenceMatcher(None, e["text"], g, autojunk=False).ratio(), 3)
                if fam == "trip (unseen)":
                    ep["brief"] = {k: v["say"] for k, v in sc["brief"]["topics"].items()}
                eps[arm].append(ep)
        fams.append({"id": fam, "label": label, "n": res["untouched"][fam]["n"],
                     "untouched": {k: res["untouched"][fam][k] for k in ("success", "asked", "found_need")},
                     "patched": {k: res["patched"][fam][k] for k in ("success", "asked", "found_need")},
                     "episodes": eps})

    # the three saved trip scenarios, for the "you ask" game: brief, order, what unlocks each topic, the checker's keywords
    trips = []
    for sc in tests["trip (unseen)"][:3]:
        b = sc["brief"]
        who = next(k for k, v in S.TRIP.items() if v[0] == b["topics"]["who"]["say"])
        why = next(k for k, v in S.TRIP_WHY.items() if v[0] == b["topics"]["trip_why"]["say"])
        budget = int(re.search(r"\d+", b["topics"]["budget"]["say"]).group())
        trips.append({"request": sc["request"], "topics": {k: v["say"] for k, v in b["topics"].items()}, "order": b["order"],
                      "who": who, "why": why, "who_words": S.TRIP[who][1], "why_words": S.TRIP_WHY[why][1], "budget": budget})

    data = {
        "families": fams,
        "ppl": {"untouched": res["ppl_before"], "patch_on": res["ppl_patch_on"], "patch_off": res["ppl_patch_off"]},
        "plain_chat": tr["keal_plain_chat"],
        "trips": trips,
        "topic_words": {k: S.TOPIC_WORDS[k] for k in ("who", "from", "budget", "when", "trip_why")},
    }
    json.dump(data, open(HERE / "data" / "askfirst.json", "w"), separators=(",", ":"), ensure_ascii=False)
    print({k: data["ppl"][k] for k in data["ppl"]})
    for f in fams:
        print(f"{f['label']:32} n={f['n']:2}  untouched {f['untouched']['success']:.0%}  patched {f['patched']['success']:.0%}  "
              f"asked {f['untouched']['asked']:.0%}->{f['patched']['asked']:.0%}  "
              f"gold-similarity {[e.get('same_as_gold') for e in f['episodes']['patched']]}")
    print(f"{(HERE / 'data' / 'askfirst.json').stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
