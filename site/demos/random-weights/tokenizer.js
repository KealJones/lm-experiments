// GPT-2's byte-level BPE tokenizer, enough to encode a prompt and decode tokens.
// Uses GPT-2's real vocab and merges (data/gpt2-tokenizer.json, written by record.py from the Hugging Face files);
// record.py checks this encoder against the real tokenizer on test strings.

const PRETOKEN = /'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+/gu;

function bytesToUnicode() {
  const bs = [];
  for (let i = 33; i <= 126; i++) bs.push(i);
  for (let i = 161; i <= 172; i++) bs.push(i);
  for (let i = 174; i <= 255; i++) bs.push(i);
  const cs = bs.slice();
  let n = 0;
  for (let b = 0; b < 256; b++) {
    if (!bs.includes(b)) { bs.push(b); cs.push(256 + n); n++; }
  }
  const enc = new Map(), dec = new Map();
  bs.forEach((b, i) => { enc.set(b, String.fromCharCode(cs[i])); dec.set(String.fromCharCode(cs[i]), b); });
  return { enc, dec };
}

export class GPT2Tokenizer {
  constructor({ vocab, merges }) {
    this.vocab = vocab; // id -> token string (byte-level form)
    this.ids = new Map(vocab.map((t, i) => [t, i]));
    this.ranks = new Map(merges.map((m, i) => [m, i]));
    const { enc, dec } = bytesToUnicode();
    this.byteEnc = enc;
    this.byteDec = dec;
    this.cache = new Map();
    this.utf8 = new TextEncoder();
    this.decoder = new TextDecoder("utf-8");
  }

  bpe(word) {
    if (this.cache.has(word)) return this.cache.get(word);
    let parts = [...word];
    while (parts.length > 1) {
      let best = -1, bestRank = Infinity;
      for (let i = 0; i < parts.length - 1; i++) {
        const r = this.ranks.get(parts[i] + " " + parts[i + 1]);
        if (r !== undefined && r < bestRank) { bestRank = r; best = i; }
      }
      if (best < 0) break;
      const a = parts[best], b = parts[best + 1];
      const next = [];
      for (let i = 0; i < parts.length; i++) {
        if (i < parts.length - 1 && parts[i] === a && parts[i + 1] === b) { next.push(a + b); i++; }
        else next.push(parts[i]);
      }
      parts = next;
    }
    this.cache.set(word, parts);
    return parts;
  }

  encode(text) {
    const out = [];
    for (const m of text.matchAll(PRETOKEN)) {
      const word = [...this.utf8.encode(m[0])].map((b) => this.byteEnc.get(b)).join("");
      for (const piece of this.bpe(word)) out.push(this.ids.get(piece));
    }
    return out;
  }

  // Decode one token, or a list. Partial UTF-8 shows as the replacement character, as it does in Python.
  decode(ids) {
    if (typeof ids === "number") ids = [ids];
    const bytes = [];
    for (const id of ids) for (const ch of this.vocab[id]) bytes.push(this.byteDec.get(ch));
    return this.decoder.decode(new Uint8Array(bytes));
  }
}
