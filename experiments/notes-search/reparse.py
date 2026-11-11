"""Re-reads the saved note-pass outputs leniently (python reparse.py hf-1): drops thinking (anything in <think>..</think>,
an unclosed <think>, or text before a stray </think>), keeps "- bullet" lines and ADD/CHANGE lines as new note lines
(a CHANGE is kept as a later line, so the newest version comes last), skips lines echoing the prompt's placeholders.
Approximate: in the run the model saw the strictly-parsed notes, not these."""
import json, glob, re, sys
from score import N, has

def clean(out):
    if "<think>" in out:
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.S)
        out = out.split("<think>")[0]
    if "</think>" in out: out = out.split("</think>")[-1]
    keep = []
    for ln in out.splitlines():
        s = ln.strip()
        m = re.match(r"^(?:[-*•]\s*)?(?:ADD\s*:|CHANGE\s*(?:line\s*)?\d*\s*:)?\s*(.+)$", s, re.I)
        if not s or s.upper().startswith("NONE") or "<fact>" in s or "3-6 plain words" in s: continue
        if re.match(r"^([-*•]|ADD\s*:|CHANGE)", s, re.I): keep.append(m.group(1).strip())
    return keep

if __name__ == "__main__":
    D = sys.argv[1]; tot = [0, 0]; full = 0; out = {}
    for f in sorted(glob.glob(f"{D}/chat-*.json"), key=lambda p: int(re.findall(r"\d+", p)[-1])):
        r = json.load(open(f)); t = r["chat"]
        lines = [l for x in r["note_log"] for l in clean(x["out"])]
        out[t] = lines
        if t <= 12:
            text = "\n".join(lines); h = [has(text, p) for p in N[t].values()]
            tot[0] += sum(h); tot[1] += len(h); full += all(h)
            print(t, f"{sum(h)}/{len(h)}", len(lines), "lines", sum(len(l.split()) for l in lines), "words", [k for k, p in N[t].items() if not has(text, p)])
    print(f"whole notes, reparsed: all facts {full}/12, recall {tot[0]}/{tot[1]}")
    json.dump(out, open(f"{D}/notes_reparsed.json", "w"), indent=1, ensure_ascii=False)
