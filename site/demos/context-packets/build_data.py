"""Build the context-packets demo's data from the experiment's saved outputs.

  python3 site/demos/context-packets/build_data.py

Reads experiments/context-packets/data/ (conversations, packets, answers, blind grades and the mapping that
unshuffles them) and writes data/packets.json. No model runs here.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
D = HERE.parents[2] / "experiments" / "context-packets" / "data"

TESTS = {
    1: ("Kid's birthday party", "messy", "The date moved in a throwaway line. A classmate's party is a week earlier."),
    2: ("Bathroom money", "messy", "A total built from four mentions. One quote was replaced, and two items were dropped."),
    3: ("Dinner party", "messy", "Six guests' food rules, dropped one at a time. Non-guests' rules mixed in."),
    4: ("Flaky test, again", "messy", "A CI timezone setting mentioned once, early, explains the new error."),
    5: ("The gas station tip", "messy", "A diner named once in a story. The brother recommended a different one."),
    6: ("Which run won", "messy", "A data leak was found midway, and two scores were corrected. Espresso numbers everywhere."),
    7: ("Best-man stories", "messy", "The groom is Moose, and so is a houseplant. The bride vetoed one story."),
    8: ("Sign the lease?", "messy", "The favourite apartment has carpet. The user said no carpet, early on."),
    9: ("Shark movie director", "clean", "Trivia session. \"That shark movie\" comes back 60 turns later."),
    10: ("Japan trip", "clean", "Dates, sister, wheelchair, budget and a temple, all stated plainly early on."),
    11: ("Business arithmetic", "clean", "Chain two earlier results and a tax amount."),
    12: ("Orders endpoint", "clean", "A FastAPI stack and team rules stated early. A table described midway."),
    13: ("\"now divide that by 3\"", "last", "The run chat, then \"whats 2+2\" / \"4.\" Only the last turn matters."),
    14: ("\"how old was he\"", "last", "The road trip chat, then a question about The Starry Night."),
    15: ("\"make it shorter\"", "last", "The apartment chat, then a drafted text to the landlord."),
    16: ("\"how many live there\"", "last", "The arithmetic chat, then \"capital of Australia?\" / \"Canberra.\""),
}

# Facts a correct answer needs, as regexes, to show which ones each packet carried.
FACTS = {
    1: [("Sunday March 22", r"march 22|22nd"), ("2pm", r"2\s?pm|2:00"), ("Sky High", r"sky high"), ("16 jumpers", r"\b16\b")],
    2: [("$4,415", r"4,?415"), ("tile $1,450", r"1,?450"), ("plumber $1,800", r"1,?800"), ("vanity $640", r"\b640\b"), ("electrician $525", r"\b525\b")],
    3: [("tree nuts", r"\bnut"), ("no cilantro", r"cilantro"), ("vegetarian", r"vegetarian|no.meat"), ("no spice", r"spic"), ("ignore non-guests", r"not (attending|coming)|ignore|non-attendee")],
    4: [("CI sets TZ=UTC", r"tz\s*=\s*utc|tz=utc|utc"), ("laptop is Central", r"central|cdt|cst")],
    5: [("Pearl's Canyon Diner", r"pearl"), ("before 8am", r"before 8|8\s?am|8:00"), ("burnt end hash", r"burnt end")],
    6: [("run-c", r"run-c"), ("lr 1e-4", r"1e-4"), ("74.2", r"74\.2"), ("leaked scores flagged", r"leak")],
    7: [("Moose = groom", r"groom|marcus"), ("alternator story", r"alternator"), ("trash can vetoed", r"trash can"), ("Gary text not cleared", r"gary")],
    8: [("Riverside = big kitchen", r"riverside"), ("bedroom carpet", r"carpet"), ("allergies", r"allerg")],
    9: [("Spielberg", r"spielberg"), ("born Dec 18, 1946", r"(december|dec\.?) 18,? 1946|1946")],
    10: [("Apr 12-16", r"april 12|apr 12"), ("sister Maya", r"maya"), ("wheelchair", r"wheelchair"), ("$250/day", r"250"), ("Kiyomizu-dera", r"kiyomizu")],
    11: [("revenue $33,320", r"33,?320"), ("shipping $3,025", r"3,?025"), ("tax $2,748.90", r"2,?748")],
    12: [("orders columns", r"total_cents"), ("error envelope", r"envelope|\"error\""), ("page size 25 / 100", r"\b25\b.*\b100\b|\b100\b.*\b25\b"), ("no new deps", r"dependenc|third-party|new (package|librar)")],
    13: [("the 4 from 2+2", r"2\s?\+\s?2")],
    14: [("van Gogh", r"van gogh"), ("painted 1889", r"1889")],
    15: [("the landlord text", r"mark|landlord"), ("Monday not Friday", r"monday")],
    16: [("Canberra", r"canberra")],
}

ANSWERERS = {
    "full": ("opus", "full"), "opuspkt": ("opus", "opus"), "sonnetpkt": ("opus", "sonnet"), "haikupkt": ("opus", "haiku"),
    "haikufull": ("haiku", "full"), "haikuXopuspkt": ("haiku", "opus"),
}

NOISY_JUNK = {  # which packet lines are the right source, which are junk, which are wrong
    "N1": {"good": ["Emily Jean"], "wrong": []},
    "N2": {"good": ["March 2022"], "wrong": ["2015"]},
    "N3": {"good": [], "wrong": ["1991"]},
    "N4": {"good": [], "wrong": []},
    "N5": {"good": ["Previous turn"], "wrong": []},
    "N6": {"good": ["Milo's party"], "wrong": []},
}


def turns(text):
    out = []
    for block in re.split(r"\n\s*\n(?=(?:User|Assistant):)", text.strip()):
        m = re.match(r"(User|Assistant):\s*(.*)", block, re.S)
        if m:
            out.append([m.group(1)[0], m.group(2).strip()])
    return out


def words(s):
    return len(s.split())


def main():
    mapping = json.loads((D / "keys" / "mapping.json").read_text())
    tests = []
    for n, (title, kind, trap) in TESTS.items():
        conv = (D / "convs" / f"conv{n}.md").read_text()
        packets = {}
        for b in ("opus", "sonnet", "haiku"):
            p = D / f"packets_{b}" / f"conv{n}.md"
            if p.exists():
                t = p.read_text().strip()
                packets[b] = {"text": t, "words": words(t),
                              "facts": [bool(re.search(rx, t, re.I | re.S)) for _, rx in FACTS[n]]}
        scores = json.loads((D / "grading" / f"scores{n}.json").read_text())
        runs = []
        for letter, cond in mapping[str(n)].items():
            who, ctx = ANSWERERS[cond]
            g = scores[letter]
            runs.append({"answerer": who, "context": ctx,
                         "answer": (D / "answers" / f"{cond}_conv{n}.md").read_text().strip(),
                         "score": g["score"], "pass": g["pass"], "note": g.get("note", ""),
                         "missed": g.get("missed", []), "traps": g.get("traps_hit", [])})
        key = (D / "keys" / f"key{n}.txt").read_text().strip()
        tests.append({"n": n, "title": title, "kind": kind, "trap": trap,
                      "question": (D / "questions" / f"q{n}.txt").read_text().strip(),
                      "turns": turns(conv), "conv_words": words(conv),
                      "facts": [f for f, _ in FACTS[n]], "packets": packets, "runs": runs, "key": key})

    # noisy cases
    cases_md = (D / "noisy" / "cases.md").read_text()
    cases = []
    for m in re.finditer(r"## Case (N\d)\nCONTEXT PACKET:\n(.*?)\nNEW MESSAGE: (.*?)\n", cases_md, re.S):
        cid, packet, msg = m.groups()
        lines = [l[2:] for l in packet.strip().splitlines() if l.startswith("- ")]
        tag = NOISY_JUNK[cid]
        cases.append({"id": cid, "message": msg.strip(),
                      "lines": [{"text": l, "kind": "wrong" if any(w in l for w in tag["wrong"])
                                 else "good" if any(g in l for g in tag["good"]) else "junk"} for l in lines]})
    nscores = json.loads((D / "grading" / "scores_noisy.json").read_text())
    nkeys = {}
    for line in (D / "keys" / "key_noisy.txt").read_text().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            nkeys[k.strip()] = v.strip()
    for letter, model in mapping["noisy"].items():
        ans = (D / "noisy" / f"answers_{model}.md").read_text()
        parts = dict(re.findall(r"## (N\d)\s*\n(.*?)(?=\n## N\d|\Z)", ans, re.S))
        for c in cases:
            c.setdefault("replies", {})[model] = {"text": parts.get(c["id"], "").strip(), **nscores[letter][c["id"]]}
    for c in cases:
        c["key"] = nkeys.get(c["id"], "")

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    (out / "packets.json").write_text(json.dumps({"tests": tests, "noisy": cases}, ensure_ascii=False))
    print(f"wrote {out / 'packets.json'}: {len(tests)} tests, {len(cases)} noisy cases")


if __name__ == "__main__":
    main()
