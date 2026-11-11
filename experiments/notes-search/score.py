"""Scores notes-search (python score.py hf-1): facts in the notes and in each packet, phone-time estimate, blind sheet.

Needles here tolerate rewording (notes paraphrase the chat), unlike context-packets' needles.py which matches the
chat's own words. Tests 13-16 depend only on the last exchange, which every packet carries, so they're left to grading.
"""
import json, os, random, re, sys

D = sys.argv[1]
# Phone speeds, LFM3 WebLLM QAD build on Keal's iPhone (lfm3-mlc README, 2026-11-10): 13.7 tok/s decode.
# Prefill isn't measured separately: "first word ~15 s with Squiggle's full prompt" (~1,500 tokens incl. tools)
# puts it near 100 tok/s. Both are rough; the token counts are the real result.
DECODE, PREFILL = 13.7, 100.0

N = {  # the facts each answer needs, any wording
 1: {"date (Sun Mar 22)": [r"(mar(ch)?\.?\s*22|22nd|3/22)"], "venue (Sky High)": [r"sky\s*high"], "kids (12 + 3 cousins)": [r"(15|16|fifteen|sixteen)|(12|twelve).{0,60}(3|three)"]},
 2: {"tile $1,450": [r"1,?450"], "plumber $1,800": [r"1,?800"], "vanity $640": [r"\b640\b"], "electrician $525": [r"\b525\b"]},
 3: {"no tree nuts (Marcus)": [r"nut"], "no cilantro (Dana)": [r"cilantro"], "nothing spicy (Tomas)": [r"spic|heat"], "vegetarian (Priya)": [r"vegetarian|no.?meat|meat"]},
 4: {"CI runs in UTC": [r"utc"], "laptop on Central": [r"central|cst|cdt|chicago"]},
 5: {"Pearl's": [r"pearl"], "burnt end hash": [r"burnt.?end"], "before 8am": [r"(before|by|early).{0,15}8|8\s*(am|a\.m)"]},
 6: {"run-c": [r"run.?c\b"], "LR 1e-4": [r"1e-?4|0\.0001"], "74.2": [r"74\.2"]},
 7: {"Moose = Marcus": [r"moose"], "alternator story ok": [r"alternator"], "trash can vetoed": [r"trash"], "string cheese ok": [r"string cheese|mustard"]},
 8: {"Riverside has carpet": [r"carpet"], "no-carpet dealbreaker": [r"allerg|deal.?breaker|no carpet"]},
 9: {"Spielberg": [r"spielberg"], "born Dec 18, 1946": [r"dec(ember)?\.?\s*18|1946"]},
 10: {"Apr 12-16": [r"apr(il)?\.?\s*1[26]|12.{0,8}16"], "sister in a wheelchair": [r"wheelchair"], "$250/day": [r"250"], "Kiyomizu-dera": [r"kiyomizu"]},
 11: {"revenue 33,320": [r"33,?320"], "shipping 3,025 (or 2,295+730)": [r"3,?025|2,?295"], "tax 8.25% / 2,748.90": [r"8\.25|2,?748"]},
 12: {"UUID ids": [r"uuid"], "newest first": [r"desc|newest|created_at"], "error envelope": [r"envelope|\"error\"|error.{0,20}code"], "async session dep": [r"get_session|depends|asyncsession|async"], "no new deps": [r"dependenc|third.?party|package"]},
}


def has(text, pats):
    return all(re.search(p, text or "", re.I) for p in pats)


recs = {int(f.split("-")[1].split(".")[0]): json.load(open(os.path.join(D, f))) for f in os.listdir(D) if f.startswith("chat-") and f.endswith(".json")}
methods = ["bm25_notags", "bm25", "emb", "hybrid", "lfm3q_bm25", "lfm3q_hybrid", "whole"]
L = ["# notes-search scores", ""]
L += ["## Facts in the packet (tests 1-12; whole = everything in the notes)", "",
      "| test | " + " | ".join(methods) + " |", "|---|" + "---|" * len(methods)]
tot = {m: [0, 0] for m in methods}; full = {m: 0 for m in methods}
for t in range(1, 13):
    r = recs.get(t)
    if not r: continue
    row = []
    for m in methods:
        pk = r["packets"].get(m, "")
        h = sum(has(pk, p) for p in N[t].values()); n = len(N[t])
        tot[m][0] += h; tot[m][1] += n; full[m] += h == n
        row.append(f"{h}/{n}")
    L.append(f"| {t} | " + " | ".join(row) + " |")
L.append("| **all facts** | " + " | ".join(f"**{full[m]}/12**" for m in methods) + " |")
L.append("| **fact recall** | " + " | ".join(f"{tot[m][0]}/{tot[m][1]} ({tot[m][0] / max(1, tot[m][1]):.0%})" for m in methods) + " |")

L += ["", "## Notes", "", "| test | turns | note lines | turns with ADD/CHANGE | NONE | unparsed | notes words |", "|---|---|---|---|---|---|---|"]
for t in sorted(recs):
    r = recs[t]; lg = r["note_log"]
    wrote = sum(bool(x["ops"]) for x in lg); none = sum(x["out"].strip().upper().startswith("NONE") for x in lg)
    L.append(f"| {t} | {len(lg)} | {len(r['notes'])} | {wrote} | {none} | {len(lg) - wrote - none} | {sum(len(l.split()) for l in r['notes'])} |")

L += ["", "## Time per note pass (estimated for the phone)", ""]
pt = [x["prompt_tokens"] for r in recs.values() for x in r["note_log"]]; ot = [x["out_tokens"] for r in recs.values() for x in r["note_log"]]
def pct(v, q): v = sorted(v); return v[min(len(v) - 1, int(q * len(v)))] if v else 0
if pt:
    L += [f"{len(pt)} note passes. Prompt tokens: median {pct(pt, .5)}, 90th pct {pct(pt, .9)}, max {max(pt)}. Output tokens: median {pct(ot, .5)}, 90th pct {pct(ot, .9)}, max {max(ot)}.",
          "", f"At {PREFILL:.0f} tok/s reading and {DECODE} tok/s writing: median pass ~{pct(pt, .5) / PREFILL + pct(ot, .5) / DECODE:.0f} s, 90th pct ~{pct(pt, .9) / PREFILL + pct(ot, .9) / DECODE:.0f} s."]
    qp = [r["query_prompt_tokens"] for r in recs.values()]; qo = [r["query_out_tokens"] for r in recs.values()]
    L += [f"LFM3 query step: prompt median {pct(qp, .5)} tokens, output median {pct(qo, .5)}: ~{pct(qp, .5) / PREFILL + pct(qo, .5) / DECODE:.1f} s before the answer starts. BM25 itself: milliseconds."]
L += ["", "## LFM3's queries", ""] + [f"- {t}: `{recs[t]['lfm3_query']}`" for t in sorted(recs)]
open(os.path.join(D, "SCORES.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))

# blind grading sheet over the answer arms
rng = random.Random(29); keys = "../context-packets/data/keys"; data = {d["id"]: d for d in json.load(open("../whiteboard/data.json"))}
sheet, mapping = [], {}
for t in sorted(recs):
    arms = list(recs[t]["answers"]); rng.shuffle(arms); mapping[t] = {chr(65 + i): a for i, a in enumerate(arms)}
    sheet.append(f"\n######## TEST {t}\nQ: {data[t]['question']}\nKEY: {open(f'{keys}/key{t}.txt').read().strip()[:900]}")
    for i, a in enumerate(arms):
        last = recs[t]["answers"][a][-1]
        sheet.append(f"--- Reply {chr(65 + i)}:\n" + ((last.get("text") or "(no reply text)")[:1200]))
open(os.path.join(D, "GRADING.md"), "w").write("\n".join(sheet))
json.dump(mapping, open(os.path.join(D, "mapping.json"), "w"), indent=1)
