// The tokzoo schemes, in the browser. Pure functions, no DOM, so test_tokenizers.py can run them in node.
// Each scheme returns { pieces: [string], kind: "tokens" | "rewrite" }:
//   tokens  - the text cut into tokens (lossless: the pieces join back to the input)
//   rewrite - the text changed first; pieces are its words and gaps, for display
// The BPE rows use vocabularies from build_data.py (trained on this repo's READMEs, not the run's FineWeb-Edu).

const CONTRACTIONS = ["'s", "'t", "'re", "'ve", "'m", "'ll", "'d"];
const LETTER = /\p{L}/u;
const NUMBER = /\p{N}/u;
const SPACE_CAT = /[\p{Zs}\p{Zl}\p{Zp}]/u;
const isLetter = (c) => LETTER.test(c);
const isNumber = (c) => NUMBER.test(c);
const isSpace = (c) => "\t\n\v\f\r ".includes(c) || SPACE_CAT.test(c);

// GPT-2's pre-split pattern written out by hand (same as pretokenize() in build_data.py).
export function pretokenize(text, splitDigits = false) {
  const chars = Array.from(text);
  const n = chars.length;
  const out = [];
  let i = 0;
  const startsWith = (k, at) => Array.from(k).every((ch, x) => chars[at + x] === ch);
  while (i < n) {
    const c = chars[i];
    const hit = CONTRACTIONS.find((k) => startsWith(k, i));
    if (hit) { out.push(hit); i += hit.length; continue; }
    const j = c === " " && i + 1 < n ? i + 1 : i;
    const nxt = j < n ? chars[j] : "";
    if (nxt && (j > i || c !== " ")) {
      let k;
      if (isLetter(nxt)) {
        k = j; while (k < n && isLetter(chars[k])) k++;
        out.push(chars.slice(i, k).join("")); i = k; continue;
      }
      if (isNumber(nxt)) {
        k = j + 1;
        if (!splitDigits) while (k < n && isNumber(chars[k])) k++;
        out.push(chars.slice(i, k).join("")); i = k; continue;
      }
      if (!isSpace(nxt)) {
        k = j; while (k < n && !(isSpace(chars[k]) || isLetter(chars[k]) || isNumber(chars[k]))) k++;
        out.push(chars.slice(i, k).join("")); i = k; continue;
      }
    }
    let k = i;
    while (k < n && isSpace(chars[k])) k++;
    if (k < n && k - i > 1) k--;
    out.push(chars.slice(i, k).join(""));
    i = k;
  }
  return out;
}

// ------------------------------------------------------------------ byte-level BPE

const enc = new TextEncoder();
const dec = new TextDecoder("utf-8", { fatal: false });

export function makeBpe(merges) {
  const ranks = new Map(merges.map(([a, b], r) => [a * 65536 + b, r]));
  const table = Array.from({ length: 256 }, (_, b) => [b]);
  for (const [a, b] of merges) table.push(table[a].concat(table[b]));
  function encodePiece(piece) {
    let s = Array.from(enc.encode(piece));
    while (s.length > 1) {
      let best = -1, bestRank = Infinity;
      for (let k = 0; k < s.length - 1; k++) {
        const r = ranks.get(s[k] * 65536 + s[k + 1]);
        if (r !== undefined && r < bestRank) { best = k; bestRank = r; }
      }
      if (best < 0) break;
      const [a, b] = [s[best], s[best + 1]];
      const id = 256 + bestRank;
      const out = [];
      for (let k = 0; k < s.length; k++) {
        if (k + 1 < s.length && s[k] === a && s[k + 1] === b) { out.push(id); k++; } else out.push(s[k]);
      }
      s = out;
    }
    return s;
  }
  return {
    ids: (piece) => encodePiece(piece),
    bytes: (id) => table[id],
  };
}

// Token ids -> display strings. A token that is only part of a character's UTF-8 bytes is shown as hex.
function bytesToPieces(byteLists) {
  return byteLists.map((bs) => {
    const s = dec.decode(new Uint8Array(bs));
    return s.includes("�") ? bs.map((b) => `<${b.toString(16).padStart(2, "0")}>`).join("") : s;
  });
}

export function bpeTokens(text, bpe, splitDigits = false) {
  const lists = [];
  for (const piece of pretokenize(text, splitDigits)) for (const id of bpe.ids(piece)) lists.push(bpe.bytes(id));
  return lists;
}

// ------------------------------------------------------------------ helpers for the rewrite schemes

// Apply f to every run of letters, leave everything else alone. Returns the rewritten text.
const LETTER_RUN = /\p{L}+/gu;
const mapWords = (text, f) => text.replace(LETTER_RUN, (w) => f(Array.from(w)).join(""));
const piecesOf = (text) => pretokenize(text);

const SHIFT = (c) => {
  if (c >= "a" && c <= "z") return String.fromCharCode(((c.charCodeAt(0) - 97 + 1) % 26) + 97);
  if (c >= "A" && c <= "Z") return String.fromCharCode(((c.charCodeAt(0) - 65 + 1) % 26) + 65);
  return c;
};

// keyboard: each key shares a token with its neighbour on the same row (our choice; the plan doesn't fix groups)
export const KEY_GROUPS = ["qw", "er", "ty", "ui", "op", "as", "df", "gh", "jk", "l", "zx", "cv", "bn", "m"];
const KEY_OF = Object.fromEntries(KEY_GROUPS.flatMap((g) => Array.from(g).map((c) => [c, g[0]])));
const keyChar = (c) => {
  const low = c.toLowerCase();
  if (!(low in KEY_OF)) return c;
  const k = KEY_OF[low];
  return c === low ? k : k.toUpperCase();
};

// telegraphic: the function words dropped (articles, common prepositions, conjunctions)
export const FUNCTION_WORDS = ["a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "with", "from", "into",
  "onto", "about", "over", "under", "than", "and", "or", "but", "nor", "so", "yet", "if", "as"];
const FW = new Set(FUNCTION_WORDS);

const VOWELS = new Set(Array.from("aeiouAEIOU"));

// ------------------------------------------------------------------ the zoo

export function buildZoo(vocab) {
  const small = makeBpe(vocab.small);
  const large = makeBpe(vocab.large);
  const smallDigits = makeBpe(vocab.small_digits);
  const phrases = new Set(vocab.phrases.map((p) => p.join(" ")));

  const tokens = (lists) => ({ kind: "tokens", pieces: bytesToPieces(lists) });
  const rewrite = (text) => ({ kind: "rewrite", pieces: piecesOf(text), text });

  return [
    { n: 1, name: "Bytes", from: "baseline", lossy: false, run: (t) => tokens(Array.from(enc.encode(t)).map((b) => [b])) },
    { n: 2, name: "Characters", from: "baseline", lossy: false,
      run: (t) => ({ kind: "tokens", pieces: Array.from(t) }) },
    { n: 3, name: "GPT-2-style BPE, small vocab", from: "baseline", lossy: false, trained: "768 tokens",
      run: (t) => tokens(bpeTokens(t, small)) },
    { n: 4, name: "GPT-2-style BPE, large vocab", from: "baseline", lossy: false, trained: "4,096 tokens",
      run: (t) => tokens(bpeTokens(t, large)) },
    { n: 5, name: "BPE with digits split one by one", from: "baseline", lossy: false, trained: "768 tokens",
      run: (t) => tokens(bpeTokens(t, smallDigits, true)) },
    { n: 6, name: "Seam tokens", from: "Keal", lossy: false,
      note: "Last letter + space + first letter of the next word is one token. The plan doesn't say how the rest of a word is cut, so here each word's middle stays whole.",
      run: (t) => ({ kind: "tokens", pieces: seams(t) }) },
    { n: 7, name: "First, last and length; middle unordered", from: "Keal", lossy: true,
      note: "Every shuffle of a word's middle letters is the same token. Shown with the middle sorted, so anagrams visibly merge.",
      run: (t) => rewrite(mapWords(t, (w) => w.length <= 3 ? w
        : [w[0], ...w.slice(1, -1).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())), w[w.length - 1]])) },
    { n: 8, name: "First and last letter only", from: "Keal", lossy: true,
      run: (t) => rewrite(mapWords(t, (w) => w.length <= 2 ? w : [w[0], w[w.length - 1]])) },
    { n: 9, name: "Every third letter, spaces kept", from: "Keal", lossy: true,
      run: (t) => rewrite(mapWords(t, (w) => w.filter((_, i) => i % 3 === 0))) },
    { n: 10, name: "Every second letter shifted one place", from: "Keal", lossy: false,
      note: "Letters 2, 4, 6… of each word move one step along the alphabet (z wraps to a). It can be undone, so nothing is lost.",
      run: (t) => rewrite(mapWords(t, (w) => w.map((c, i) => (i % 2 ? SHIFT(c) : c)))) },
    { n: 11, name: "Sense-tagged", from: "Keal (Napkin's senses)", lossy: false, needs: "a tagging pass that picks each word's WordNet supersense" },
    { n: 12, name: "Real roots", from: "Keal", lossy: false, needs: "MorphyNet's morpheme splits" },
    { n: 13, name: "3-word chunks", from: "Keal", lossy: false, trained: `${vocab.phrases.length} phrases`,
      note: "The most common 3-word phrases are single tokens; everything else falls back to the small BPE.",
      run: (t) => tokens(chunks(t, phrases, small)) },
    { n: 14, name: "By sound", from: "Claude", lossy: true, needs: "a pronunciation dictionary" },
    { n: 15, name: "Vowels dropped", from: "Claude", lossy: true,
      run: (t) => rewrite(mapWords(t, (w) => w.filter((c) => !VOWELS.has(c)))) },
    { n: 16, name: "Every word backwards", from: "Claude", lossy: false,
      run: (t) => rewrite(mapWords(t, (w) => w.slice().reverse())) },
    { n: 17, name: "Keyboard position", from: "Claude", lossy: true,
      note: `Keys share a token with their row neighbour: ${KEY_GROUPS.join(" ")}. Each letter is written as its pair's first key. The plan doesn't fix the groups yet; this is one choice.`,
      run: (t) => rewrite(mapWords(t, (w) => w.map(keyChar))) },
    { n: 18, name: "Only verbs", from: "Keal", lossy: true, needs: "a part-of-speech tagging pass" },
    { n: 19, name: "Only nouns", from: "Keal", lossy: true, needs: "a part-of-speech tagging pass" },
    { n: 20, name: "Telegraphic", from: "Keal", lossy: true,
      note: `Drops the function words: ${FUNCTION_WORDS.join(", ")}. The plan names "the", "of" and "and"; the rest of the list is this page's choice.`,
      run: (t) => rewrite(telegraphic(t)) },
  ];
}

// row 6: seams. Words are letter runs; where two words are joined by exactly one space,
// "last letter + space + first letter" is one token. A one-letter word between two seams joins both ("x a y").
export function seams(text) {
  const parts = text.split(/(\p{L}+)/u); // [gap, word, gap, word, ..., gap]
  const out = [];
  const gapPieces = (g) => (g ? pretokenize(g) : []);
  out.push(...gapPieces(parts[0]));
  for (let i = 1; i < parts.length; i += 2) {
    const w = Array.from(parts[i]);
    const before = i > 1 && parts[i - 1] === " ";
    const after = i + 2 < parts.length && parts[i + 1] === " ";
    const next = after ? Array.from(parts[i + 2])[0] : "";
    if (before && after && w.length === 1) { out[out.length - 1] += " " + next; continue; }
    const middle = w.slice(before ? 1 : 0, after ? w.length - 1 : w.length);
    if (middle.length) out.push(middle.join(""));
    if (after) out.push(w[w.length - 1] + " " + next);
    else out.push(...gapPieces(parts[i + 1]));
  }
  return out;
}

// row 13: 3-word phrases as single tokens, small BPE for the rest
export function chunks(text, phrases, bpe) {
  const pre = pretokenize(text);
  const word = (t) => /^ ?\p{L}+$/u.test(t);
  const lists = [];
  for (let i = 0; i < pre.length; i++) {
    const [a, b, c] = [pre[i], pre[i + 1], pre[i + 2]];
    if (c !== undefined && word(a) && word(b) && word(c) && b[0] === " " && c[0] === " "
        && phrases.has([a.replace(/^ /, ""), b.slice(1), c.slice(1)].join(" ").toLowerCase())) {
      lists.push(Array.from(enc.encode(a + b + c)));
      i += 2;
      continue;
    }
    for (const id of bpe.ids(a)) lists.push(bpe.bytes(id));
  }
  return lists;
}

// row 20: drop function words with the space before them (or after, at the start)
export function telegraphic(text) {
  return text
    .replace(/(^|[^\p{L}])(\p{L}+)/gu, (m, before, w) => (FW.has(w.toLowerCase()) ? before + "\u0000" : m))
    .replace(/ \u0000|\u0000 ?/g, "");
}
