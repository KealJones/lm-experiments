"""Check the browser tokenizers (tokenizers.js) against build_data.py.

  python3 site/demos/tokzoo/test_tokenizers.py      (needs node; run build_data.py first)

Compares pre-splitting and all three BPE vocabularies (as token byte sequences) on every line of the training
corpus plus some messy extra text.
"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_data as bd  # noqa: E402

EXTRA = [
    "ngl i was readin teh docs @ 2am n it lowkey made sense lol",
    "In 2026 we ran 25 tasks for $0.35 each 🙃 naïve café",
    "  leading   spaces\n\n\ttabs and trailing  ",
    "don't won't y'all I'M it's 'quoted' rock'n'roll",
    "日本語のテキスト and émojis 👍🏽 mixed123abc 1,000,000",
]

JS = """
import fs from 'fs';
import { pretokenize, makeBpe, bpeTokens } from '%s';
const { lines, vocab } = JSON.parse(fs.readFileSync(0, 'utf8'));
const bpes = { small: makeBpe(vocab.small), large: makeBpe(vocab.large), small_digits: makeBpe(vocab.small_digits) };
console.log(JSON.stringify(lines.map(t => ({
  pre: pretokenize(t), pre_digits: pretokenize(t, true),
  small: bpeTokens(t, bpes.small), large: bpeTokens(t, bpes.large), small_digits: bpeTokens(t, bpes.small_digits, true),
}))));
""" % (HERE / "tokenizers.js").as_posix()

if __name__ == "__main__":
    vocab = json.loads((HERE / "data" / "vocab.json").read_text())
    text, _ = bd.corpus()
    lines = [l for l in text.splitlines() if l.strip()] + EXTRA
    js = json.loads(subprocess.run(["node", "--input-type=module", "-e", JS], input=json.dumps({"lines": lines, "vocab": vocab}),
                                   capture_output=True, text=True, check=True).stdout)
    bad = 0
    for line, j in zip(lines, js):
        py = {
            "pre": bd.pretokenize(line), "pre_digits": bd.pretokenize(line, True),
            "small": [list(b) for b in bd.encode(line, vocab["small"])],
            "large": [list(b) for b in bd.encode(line, vocab["large"])],
            "small_digits": [list(b) for b in bd.encode(line, vocab["small_digits"], True)],
        }
        for k in py:
            if py[k] != j[k]:
                bad += 1
                print(f"MISMATCH {k}: {line[:80]!r}\n  py {py[k][:12]}\n  js {j[k][:12]}")
                break
    print(f"{len(lines) - bad} of {len(lines)} lines agree on pre-splitting and all three BPE vocabularies")
    sys.exit(1 if bad else 0)
