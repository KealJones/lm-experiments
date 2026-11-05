"""Build the registers demo's data from experiments/registers-v2.

  python3 site/demos/registers/build_data.py

No model checkpoints are in the repo, so nothing here runs a model. What it does use:
  - the world and checker from rv2.py (pure Python; the torch parts are skipped), to rebuild the exact
    100 test problems the models were scored on (random.Random(12345), 50 short + 50 long) with their gold
    plans and the true state after every sentence, i.e. what the taught slots were trained to hold;
  - kaggle-out/full_results_gpu*.jsonl for every score, failure count and slot readout, per seed;
  - the recorded seed-0 sample plans.
It also writes data/checker_cases.json: random plans run through the Python checker, which test_checker.mjs
replays through the JavaScript port to show they agree.
"""
import json
import pathlib
import random
import re
import statistics as st

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parents[2] / "experiments" / "registers-v2"
OUT = HERE / "data"


def load_world():
    """Run rv2.py's skins, world and checker sections (no torch needed)."""
    src = (EXP / "rv2.py").read_text().splitlines()
    start = next(i for i, l in enumerate(src) if l.startswith("# ## Skins"))
    stop = next(i for i, l in enumerate(src) if l.startswith("# ## Vocabulary"))
    tests = next(i for i, l in enumerate(src) if l.startswith("def test_sets"))
    code = "\n".join(src[start:stop - 1] + src[tests:tests + 4])
    ns = {"re": re, "random": random, "st": st}
    exec(code, ns)
    return ns


W = load_world()
PLACE_N, ITEM_N, HAS_DOOR = W["PLACE_N"], W["ITEM_N"], W["HAS_DOOR"]


def labelled_plan(ep):
    """Gold plan sentences with the true state after each, as in rv2.encode_labeled."""
    known = {f[1]: f[2] for f in ep["facts"] if f[0] == "door"}
    loc, held = ep["start"], set()

    def state():
        door = "none" if not HAS_DOOR[loc] else known.get(loc, "unknown")
        return {"where": loc, "key": "key" in held, "target": ep["target"] in held, "door": door, "goal": ep["target"]}

    out = [{"text": W["fact_text"](ep["goal"]), "kind": "goal", "trained": True, "state": state()}]
    for s in ep["plan"]:
        if s[0] == "go":
            loc = s[2]
        elif s[0] in ("open", "unlock"):
            known[s[2]] = "open"
        elif s[0] == "take":
            held.add(s[2])
        for text, train in W["step_text"](s):
            out.append({"text": text, "kind": s[0], "trained": train, "state": state()})
    return out


def problem(ep, split, idx):
    return {
        "id": f"{split}-{idx}", "split": split, "obs": sorted(ep["obs"]),
        "agent": ep["agent"], "start": ep["start"], "loc": ep["loc"], "doors": ep["doors"],
        "target": ep["target"], "prop": ep["prop"],
        "facts": [W["fact_text"](f) for f in ep["facts"]],
        "plan": labelled_plan(ep),
    }


def results():
    rows = []
    for f in sorted((EXP / "kaggle-out").glob("full_results_gpu*.jsonl")):
        rows += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    models = {}
    for cond in ("base", "taught-ends", "taught-every", "self-every"):
        rs = sorted([r for r in rows if r["cond"] == cond], key=lambda r: r["seed"])
        fails = {}
        for r in rs:
            for split in ("short", "long"):
                for k, v in r["seen"][split]["fails"].items():
                    fails[k] = fails.get(k, 0) + v
        m = {
            "seeds": [{
                "seed": r["seed"],
                "short": r["seen"]["short"]["success"], "long": r["seen"]["long"]["success"],
                "messy_short": r["messy"]["short"]["success"], "messy_long": r["messy"]["long"]["success"],
            } for r in rs],
            "fails": fails,
        }
        if "slots_seen" in rs[0]:
            m["slots_seen"] = [st.mean(r["slots_seen"][j] for r in rs) for j in range(4)]
            m["slots_unseen"] = [st.mean(r["slots_unseen"][j] for r in rs) for j in range(4)]
        models[cond] = m
    samples = {r["cond"]: r["sample"] for r in rows if r.get("sample")}
    return models, samples


def checker_cases(eps):
    """Random plans (a mix of gold steps and plausible wrong ones) run through the Python checker."""
    r = random.Random(7)
    cases = []
    for ep in eps:
        gold = [t for s in ep["plan"] for t, train in W["step_text"](s) if train]
        for _ in range(4):
            sents = list(gold)
            for _ in range(r.randint(0, 3)):  # break it: swap in a wrong sentence somewhere
                a, p, i = ep["agent"], r.choice(PLACE_N), r.choice(ITEM_N + ["key"])
                bad = r.choice([
                    f"the {a} is not at the {p} , so the {a} goes to the {p} .",
                    f"the {a} takes the {i} .",
                    f"the door of the {p} is closed , so the {a} opens the door of the {p} .",
                    f"the door of the {p} is locked , so the {a} opens the door of the {p} with the key .",
                    f"the door of the {p} is locked , so the {a} needs the key .",
                    f"the {a} has the {i} , so the goal is done .",
                    f"search : where is the {i} ?",
                    f"the {a} wants the {i} because the {i} is {r.choice(W['PROP_N'])} .",
                    "the the goes .",
                ])
                sents.insert(r.randint(0, len(sents)), bad)
            skin = r.choice(W["ALL_SKINS"])
            if r.random() < 0.1:  # a word from another skin
                other = r.choice([s for s in W["ALL_SKINS"] if s != skin])
                sents = [W["to_skin"](sents[0], other)] + [W["to_skin"](s, skin) for s in sents[1:]]
            else:
                sents = [W["to_skin"](s, skin) for s in sents]
            sim = W["Sim"](ep, skin)
            trace = []
            for s in sents:
                inject = sim.step(s.split())
                trace.append({"status": sim.status, "why": sim.why, "inject": inject})
                if sim.status:
                    break
            cases.append({"ep": problem(ep, "case", 0) | {"skin": skin}, "sents": sents, "trace": trace})
    return cases


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    tests = W["test_sets"](50)
    probs = [problem(ep, split, i) for split, eps in tests.items() for i, ep in enumerate(eps)]
    models, samples = results()
    sample_problem = next(p for p in probs if " ".join(p["facts"]) + " " + p["plan"][0]["text"] + " plan :"
                          == next(iter(samples.values()))["problem"])
    data = {
        "skins": {s: W["SKINS"][s] for s in W["ALL_SKINS"]},
        "plan_skins": W["PLAN_SKINS"], "unseen": W["UNSEEN"],
        "places": PLACE_N, "door_places": W["DOOR_PLACES"], "items": ITEM_N, "props": W["PROP_N"],
        "agents": W["AGENTS"],
        "problems": probs,
        "models": models,
        "sample": {"problem_id": sample_problem["id"], "plans": samples},
    }
    json.dump(data, open(OUT / "registers.json", "w"), separators=(",", ":"))
    json.dump(checker_cases(tests["short"][:20] + tests["long"][:20]), open(OUT / "checker_cases.json", "w"),
              separators=(",", ":"))

    # print what the README table says, from the raw per-seed results
    for cond, m in models.items():
        mean = lambda k: round(100 * st.mean(s[k] for s in m["seeds"]))
        book = sum(v for k, v in m["fails"].items() if k in W["BOOKKEEPING"]) if "BOOKKEEPING" in W else None
        print(f"{cond:13} short {mean('short')}% long {mean('long')}% messy {mean('messy_short')}% / {mean('messy_long')}%"
              f"  fails {m['fails']}")
        if "slots_seen" in m:
            print("   slots seen", [round(100 * x) for x in m["slots_seen"]], "unseen", [round(100 * x) for x in m["slots_unseen"]])
    print("sample problem:", sample_problem["id"])
    for f in OUT.glob("*.json"):
        print(f.name, f"{f.stat().st_size / 1e3:.0f} KB")
