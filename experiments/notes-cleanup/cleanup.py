"""Notes cleanup: can a pass over the finished notes drop stale and repeated lines without losing facts?

Input: notes-search run 4a's final notes (LFM3's own notes, native layout). Arms, each written to OUT/notes-<arm>.json:
  raw     4a's notes as they are
  tidy    no model: strip junk (leftover "4." / "12:" numbers, JSON brackets, cut-off lines), drop exact and near
          repeats, keeping the newest copy
  words   tidy, then "newest wins" on shared words alone (no model), swept over the share of words
  newest  tidy, then "newest wins": an older line is dropped when a later line is about the same thing (bge-small
          cosine >= T and most of its words shared) but its numbers differ. Swept over T; no model call
  lfm3    tidy, then LFM3 itself, once per group of related lines (embedding clusters, <= 10 lines), in the native
          layout of 4a: the group comes back from a read_notes call, edits go out as update_notes(change, delete)

Scores (free): answer-key facts kept (notes-search/score.py's needles), stale lines left on the three trap tests
(1: party moved Mar 14 -> 22; 2: plumber $2,200 -> $1,800; 6: leaked scores 78.9 / 76.5 -> 70.3 / 68.2), size.

  python cleanup.py OUT [--arms raw,tidy,words,newest,lfm3] [--chats 1,2]
Answers on the cleaned notes reuse notes_search.py with --notes-from OUT/notes-<arm>.json.
"""
import argparse, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "../whiteboard"), os.path.join(HERE, "../notes-search")]
import run as wb                       # LFM3 prompt format, parser, llama-server backend
import notes_search as ns              # toks, junk, norm, apply_native, READ_NOTES / UPDATE_NOTES, live

SRC = os.path.join(HERE, "../notes-search/hf-4a")
SWEEP = (0.75, 0.8, 0.85, 0.9)
WORD_SWEEP = (0.5, 0.6, 0.7, 0.8)
GROUP_SIM, GROUP_MAX, CLEAN_MAX = 0.72, 10, 300

N = {  # copied from notes-search/score.py: the facts each answer needs, any wording
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
# A line is stale when it carries the old value and not the new one (a "moved from Mar 14" line is fine).
STALE = {1: (r"mar(ch)?\.?\s*14|14th", r"22"), 2: (r"2,?200", r"1,?800"), 6: (r"78\.9|76\.5", r"70\.3|68\.2")}
NUM = re.compile(r"\d[\d,.:/-]*")


def clean_line(l):
    l = l.strip().strip('"').strip()
    l = re.sub(r'^\[\s*"', "", l); l = re.sub(r'"\s*\]$', "", l)
    l = re.sub(r"^\d+\s*[.:)]\s+", "", l)          # "4. Vanity" / "12: Starting run-b"; keeps "74.2: ..." and "12.5 baseline"
    return l.strip().strip('"').strip()


def tidy(lines):
    out = []
    for l in map(clean_line, lines):
        if ns.junk(l): continue
        w = set(ns.toks(l))
        # a newer line that repeats this one replaces it (the newest copy is the one kept)
        out = [o for o in out if not (ns.norm(o) == ns.norm(l) or (w and len(set(ns.toks(o)) & w) / max(1, len(set(ns.toks(o)))) >= 0.8 and len(w) >= len(set(ns.toks(o)))))]
        out.append(l)
    return out


def words(l):
    return {w for w in ns.toks(l) if not NUM.fullmatch(w)}


def newest(lines, E, t, w=0.5):
    """Drop line i when a later line j is about the same thing (cosine >= t, and >= w of i's words in j) and i has a
    number j doesn't: the later number is taken to be the current one. E=None: words only (no embedding model)."""
    drop = set()
    for i in range(len(lines)):
        ni, wi = set(NUM.findall(lines[i])), words(lines[i])
        if not ni or not wi: continue
        for j in range(i + 1, len(lines)):
            if (E is None or float(E[i] @ E[j]) >= t) and len(wi & words(lines[j])) / len(wi) >= w and not ni <= set(NUM.findall(lines[j])):
                drop.add(i); break
    return [l for k, l in enumerate(lines) if k not in drop]


def groups(lines, E):
    """Greedy, in written order: a line joins the group whose first line it's most like (cosine >= GROUP_SIM)."""
    gs = []
    for i in range(len(lines)):
        best = max((g for g in gs if len(g) < GROUP_MAX), key=lambda g: float(E[g[0]] @ E[i]), default=None)
        if best is not None and float(E[best[0]] @ E[i]) >= GROUP_SIM: best.append(i)
        else: gs.append([i])
    return gs


CLEAN_SYSTEM = """You tidy the saved notes of a chat. read_notes shows a group of related notes in the order they were written, so a higher number is newer. Call update_notes to fix the group:
- delete: numbers of notes that a newer note repeats, or that a newer note replaces (an old date, amount, score, plan or choice that changed later).
- change: when a note should hold the fact as it is now, its number and the fact.
Keep every fact that still holds, and add nothing new. If the group needs no fixing, don't call update_notes.
Example: read_notes shows "1. Billy's party: Mar 15 at the zoo" and "2. Billy's party moved to Mar 22". You call update_notes with delete: [1] and change: ["2: Billy's party: Mar 22 at the zoo (moved from Mar 15)"]."""


def lfm3_clean(be, lines, E, log):
    """One LFM3 call per group of 2+ related lines; edits only touch that group."""
    out = list(lines)
    for g in groups(lines, E):
        if len(g) < 2: continue
        local = [lines[k] for k in g]
        query = " ".join(ns.toks(local[0])[:8])
        conv = [{"role": "system", "content": CLEAN_SYSTEM},
                {"role": "assistant", "content": "", "tool_calls": [{"name": "read_notes", "arguments": {"query": query}}]},
                {"role": "tool", "content": "\n".join(f"{n + 1}. {l}" for n, l in enumerate(local))}]
        p = wb.lfm3_prompt(conv, ns.NATIVE_TOOLS, thinking=False)
        t = time.time()
        raw = be.one((p, CLEAN_MAX))
        if raw.lstrip().startswith("<think>") and "</think>" not in raw:   # thinks despite thinking-off: close it, as 4a did
            raw += "\n" + wb.THINK_NOTE + "\n</think>\n" + be.one((p + raw + "\n" + wb.THINK_NOTE + "\n</think>\n", CLEAN_MAX))
        _, said, calls = wb.parse_output(raw if "</think>" in raw else "</think>" + raw)
        for c in calls: c["arguments"].pop("add", None)                     # cleanup never adds
        ops = ns.apply_native(local, [], calls)
        for k, l in zip(g, local): out[k] = l
        log.append({"group": local if len(local) else [], "prompt_tokens": len(be.tok.encode(p, add_special_tokens=False)),
                    "out": raw, "ops": ops, "secs": round(time.time() - t, 1), "talked": bool(said.strip()) and not calls})
    return ns.live(out)


def score(notes):
    """Per arm: facts kept (tests 1-12), stale lines (tests 1, 2, 6), lines and words (all 16 chats)."""
    kept = total = full = 0; stale = {}
    for t, facts in N.items():
        text = "\n".join(notes.get(t, []))
        h = sum(all(re.search(p, text, re.I) for p in ps) for ps in facts.values())
        kept += h; total += len(facts); full += h == len(facts)
    for t, (old, new) in STALE.items():
        stale[t] = sum(bool(re.search(old, l, re.I)) and not re.search(new, l, re.I) for l in notes.get(t, []))
    return {"facts": f"{kept}/{total}", "all_facts": f"{full}/12", "stale": stale,
            "lines": sum(map(len, notes.values())), "words": sum(len(l.split()) for v in notes.values() for l in v)}


def selfcheck():
    assert clean_line('["4: Cancel $2,200 plumber quote"') == "Cancel $2,200 plumber quote"
    assert clean_line("74.2: better than a") == "74.2: better than a" and clean_line("12.5 baseline shot") == "12.5 baseline shot"
    assert tidy(["Party at Sky High", "9. Party at Sky High", "Cake: dino"]) == ["Party at Sky High", "Cake: dino"]
    import numpy as np
    E = np.eye(3); E[0] = E[1] = [1, 0, 0]
    assert newest(["Party Saturday March 14 at 2pm", "Party moved to Sunday March 22 at 2pm", "Cake 7 candles"], E, 0.8) == \
        ["Party moved to Sunday March 22 at 2pm", "Cake 7 candles"]
    assert newest(["Run-b score 78.9", "Run-b score 70.3 corrected"], None, 0, 0.6) == ["Run-b score 70.3 corrected"]
    assert score({1: ["Party March 14th", "Party moved to March 22nd (was March 14th)"]})["stale"][1] == 1


def main():
    selfcheck()
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--arms", default="raw,tidy,words,newest,lfm3"); ap.add_argument("--chats", default="")
    ap.add_argument("--src", default=SRC, help="folder with run 4a's chat-N.json")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    raw = {int(f[5:-5]): json.load(open(os.path.join(a.src, f)))["notes"] for f in os.listdir(a.src) if f.startswith("chat-") and f.endswith(".json")}
    if a.chats: raw = {k: v for k, v in raw.items() if str(k) in a.chats.split(",")}
    arms = {"raw": raw, "tidy": {k: tidy(v) for k, v in raw.items()}}
    want = a.arms.split(",")
    if "words" in want:   # newest wins on shared words alone: no model download needed
        for w in WORD_SWEEP:
            arms[f"words-{w}"] = {k: newest(v, None, 0, w) for k, v in arms["tidy"].items()}
    if "newest" in want or "lfm3" in want:
        from sentence_transformers import SentenceTransformer
        emb = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
        E = {k: emb.encode(v, normalize_embeddings=True) for k, v in arms["tidy"].items()}
        if "newest" in want:
            for t in SWEEP:
                arms[f"newest-{t}"] = {k: newest(v, E[k], t) for k, v in arms["tidy"].items()}
    if "lfm3" in want:
        be = wb.Llama(); logs = {}
        def one(k):
            logs[k] = []; return k, lfm3_clean(be, arms["tidy"][k], E[k], logs[k])
        with ThreadPoolExecutor(wb.Llama.SLOTS) as ex:
            arms["lfm3"] = dict(ex.map(one, sorted(arms["tidy"])))
        json.dump(logs, open(os.path.join(a.out, "lfm3-log.json"), "w"), indent=1, ensure_ascii=False)
    rows = ["| arm | facts kept (tests 1-12) | all facts | stale lines t1 / t2 / t6 | lines | words |", "|---|---|---|---|---|---|"]
    for name, notes in arms.items():
        json.dump({str(k): v for k, v in sorted(notes.items())}, open(os.path.join(a.out, f"notes-{name}.json"), "w"), indent=1, ensure_ascii=False)
        s = score(notes)
        rows.append(f"| {name} | {s['facts']} | {s['all_facts']} | {s['stale'][1]} / {s['stale'][2]} / {s['stale'][6]} | {s['lines']} | {s['words']} |")
    open(os.path.join(a.out, "SCORES.md"), "w").write("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
