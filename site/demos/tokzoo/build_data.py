"""Train the tokzoo playground's small vocabularies and write data/vocab.json.

  python3 site/demos/tokzoo/build_data.py

The real tokzoo run will train its BPE vocabularies on FineWeb-Edu. That hasn't happened, so the playground
trains stand-ins here on a corpus that ships with the repo: every experiment README plus the top README. It writes:
  - two byte-level BPE merge lists (GPT-2-style pre-splitting), 768 and 4,096 tokens
  - the same small BPE trained with digits split one by one
  - the most common 3-word phrases, for the 3-word-chunk scheme
tokenizers.js applies these in the browser; test_tokenizers.py checks it against encode() here.
"""
import collections
import json
import pathlib
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SMALL, LARGE = 768, 4096
PHRASES = 300

CONTRACTIONS = ("'s", "'t", "'re", "'ve", "'m", "'ll", "'d")


def is_letter(c):
    return unicodedata.category(c).startswith("L")


def is_number(c):
    return unicodedata.category(c).startswith("N")


def is_space(c):
    return c in "\t\n\v\f\r " or unicodedata.category(c) in ("Zs", "Zl", "Zp")


def pretokenize(text, split_digits=False):
    """GPT-2's pre-split pattern, written out by hand so Python and JS agree exactly:
    's|'t|'re|'ve|'m|'ll|'d| ?L+| ?N+| ?[^\\sLN]+|\\s+(?!\\S)|\\s+   (with split_digits, ' ?N' takes one digit)"""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        hit = next((k for k in CONTRACTIONS if text.startswith(k, i)), None)
        if hit:
            out.append(hit)
            i += len(hit)
            continue
        j = i + 1 if c == " " and i + 1 < n else i
        nxt = text[j] if j < n else ""
        if nxt and (j > i or c != " "):
            if is_letter(nxt):
                k = j
                while k < n and is_letter(text[k]):
                    k += 1
                out.append(text[i:k]); i = k; continue
            if is_number(nxt):
                k = j + 1
                if not split_digits:
                    while k < n and is_number(text[k]):
                        k += 1
                out.append(text[i:k]); i = k; continue
            if not is_space(nxt):
                k = j
                while k < n and not (is_space(text[k]) or is_letter(text[k]) or is_number(text[k])):
                    k += 1
                out.append(text[i:k]); i = k; continue
        # whitespace run: leave its last char to the next word if a non-space follows
        k = i
        while k < n and is_space(text[k]):
            k += 1
        if k < n and k - i > 1:
            k -= 1
        out.append(text[i:k])
        i = k
    return out


def train_bpe(corpus, vocab_size, split_digits=False):
    words = collections.Counter(tuple(p.encode("utf-8")) for p in pretokenize(corpus, split_digits))
    words = {w: c for w, c in words.items()}
    seqs = {w: list(w) for w in words}
    merges = []
    next_id = 256
    while next_id < vocab_size:
        pairs = collections.Counter()
        for w, c in words.items():
            s = seqs[w]
            for a, b in zip(s, s[1:]):
                pairs[(a, b)] += c
        if not pairs:
            break
        best_count = max(pairs.values())
        if best_count < 2:
            break
        best = min(p for p, c in pairs.items() if c == best_count)  # ties: lowest ids, so it's deterministic
        merges.append(best)
        for w in words:
            s = seqs[w]
            if len(s) < 2:
                continue
            out, k = [], 0
            while k < len(s):
                if k + 1 < len(s) and s[k] == best[0] and s[k + 1] == best[1]:
                    out.append(next_id); k += 2
                else:
                    out.append(s[k]); k += 1
            seqs[w] = out
        next_id += 1
    return merges


def bpe_encode_piece(piece, ranks):
    """Merge the lowest-ranked pair first, GPT-2 style. Returns token ids."""
    s = list(piece.encode("utf-8"))
    while len(s) > 1:
        best, best_rank = None, None
        for k in range(len(s) - 1):
            r = ranks.get((s[k], s[k + 1]))
            if r is not None and (best_rank is None or r < best_rank):
                best, best_rank = k, r
        if best is None:
            break
        new_id = 256 + best_rank
        pair = (s[best], s[best + 1])
        out, k = [], 0
        while k < len(s):
            if k + 1 < len(s) and (s[k], s[k + 1]) == pair:
                out.append(new_id); k += 2
            else:
                out.append(s[k]); k += 1
        s = out
    return s


def token_bytes(merges):
    table = [bytes([b]) for b in range(256)]
    for a, b in merges:
        table.append(table[a] + table[b])
    return table


def encode(text, merges, split_digits=False):
    """Text -> list of token strings (bytes decoded with 'replace' only for display)."""
    ranks = {tuple(p): r for r, p in enumerate(merges)}
    table = token_bytes(merges)
    out = []
    for piece in pretokenize(text, split_digits):
        out.extend(table[t] for t in bpe_encode_piece(piece, ranks))
    return out


def find_phrases(corpus, top):
    """The most common runs of three letter-words, each word after the first starting with one space."""
    counts = collections.Counter()
    toks = pretokenize(corpus)
    for a, b, c in zip(toks, toks[1:], toks[2:]):
        if all(is_letter(t.lstrip(" ")[:1] or " ") and t.lstrip(" ").isalpha() for t in (a, b, c)) \
                and b.startswith(" ") and c.startswith(" ") and len(b) > 1 and len(c) > 1:
            counts[(a.lstrip(" ").lower(), b[1:].lower(), c[1:].lower())] += 1
    return [list(p) for p, n in counts.most_common(top) if n >= 3]


def corpus():
    files = [ROOT / "README.md"] + sorted((ROOT / "experiments").glob("*/README.md"))
    return "\n\n".join(f.read_text() for f in files), len(files)


if __name__ == "__main__":
    text, nfiles = corpus()
    data = {
        "corpus": {"files": nfiles, "bytes": len(text.encode("utf-8"))},
        "small": train_bpe(text, SMALL),
        "large": train_bpe(text, LARGE),
        "small_digits": train_bpe(text, SMALL, split_digits=True),
        "phrases": find_phrases(text, PHRASES),
    }
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "vocab.json").write_text(json.dumps(data, separators=(",", ":")))
    print({k: len(v) for k, v in data.items() if isinstance(v, list)}, data["corpus"])
    print([b"".join([t]).decode("utf-8", "replace") for t in encode("ngl i was readin teh docs @ 2am", data["small"])])
