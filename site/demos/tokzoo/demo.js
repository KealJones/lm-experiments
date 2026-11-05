import { buildZoo } from "./tokenizers.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const EXAMPLES = [
  ["Messy", "ngl i was readin teh docs @ 2am n it lowkey made sense lol"],
  ["Sound-alikes", "The knight read a book by night, then went to the bank of the river."],
  ["Numbers", "In 2026 we ran 25 tasks for $0.35 each, about 1,000,000 tokens."],
  ["Anagrams", "A casual trail from the barn: salt, not a causal trial form of the bran slat."],
  ["Not English", "naïve café 日本語 👍🏽"],
];

const TOKEN_ROWS = [1, 2, 3, 4, 5, 6, 13];

// show spaces, newlines and tabs so token edges are visible
function chipText(p) {
  return esc(p).replace(/ /g, '<span class="sp">␣</span>').replace(/\n/g, '<span class="sp">↵</span>')
    .replace(/\t/g, '<span class="sp">→</span>');
}

function chips(pieces, kind) {
  return pieces.map((p) => {
    if (p === "") return `<span class="chip empty" title="nothing left of this word">∅</span>`;
    const hex = /^(<[0-9a-f]{2}>)+$/.test(p);
    const gap = kind === "rewrite" && /^\s+$/.test(p);
    return `<span class="chip${hex ? " hex" : ""}${gap ? " gap" : ""}"${hex ? ' title="part of a character\'s bytes"' : ""}>${hex ? esc(p) : chipText(p)}</span>`;
  }).join("");
}

function nameBlock(z) {
  const loss = z.lossy ? `<span class="tag lossy">Lossy</span>` : `<span class="tag lossless">Lossless</span>`;
  const standin = z.trained ? `<span class="tag standin">Stand-in vocabulary, ${esc(z.trained)}</span>` : "";
  return `<div class="row-name"><h3><span class="num">${z.n}</span>${esc(z.name)}</h3>
    <span class="from">Idea: ${esc(z.from)}</span>${loss}${standin}</div>`;
}

let ZOO;

function render() {
  const text = $("#input").value;
  const chars = Array.from(text).length;
  const bytes = new TextEncoder().encode(text).length;
  const letters = (text.match(/\p{L}/gu) || []).length;
  $("#count").textContent = text ? `${chars} characters, ${bytes} bytes, ${letters} letters` : "Type something, or pick an example.";

  const results = new Map(ZOO.filter((z) => z.run).map((z) => [z.n, z.run(text)]));
  const maxTokens = Math.max(1, ...TOKEN_ROWS.map((n) => results.get(n).pieces.length));

  $("#zoo-tokens").innerHTML = TOKEN_ROWS.map((n) => {
    const z = ZOO.find((x) => x.n === n);
    const r = results.get(n);
    const count = r.pieces.length;
    const per = count ? (chars / count).toFixed(1) : "0";
    return `<article class="row">${nameBlock(z)}<div class="row-out">
      <div class="stat"><span>${count} tokens, ${per} characters each</span>
        <span class="bar" aria-hidden="true"><i style="width:${(100 * count) / maxTokens}%"></i></span></div>
      <div class="chips">${chips(r.pieces, "tokens")}</div>
      ${z.note ? `<p class="row-note">${esc(z.note)}</p>` : ""}</div></article>`;
  }).join("");

  $("#zoo-rewrite").innerHTML = ZOO.filter((z) => z.run && !TOKEN_ROWS.includes(z.n)).map((z) => {
    const r = results.get(z.n);
    const kept = (r.text.match(/\p{L}/gu) || []).length;
    const words = (text.match(/\p{L}+/gu) || []).length;
    const keptWords = (r.text.match(/\p{L}+/gu) || []).length;
    const STATS = {
      7: `Keeps all ${letters} letters but not the order of each word's middle`,
      10: `Keeps all ${letters} letters, and the shift can be undone`,
      16: `Keeps all ${letters} letters, and can be read backwards again`,
      17: `Same length, but 26 letters become 14 key pairs`,
      20: `Keeps ${keptWords} of ${words} words`,
    };
    const stat = STATS[z.n] || `Keeps ${kept} of ${letters} letters`;
    return `<article class="row">${nameBlock(z)}<div class="row-out">
      <div class="stat"><span>${stat}</span></div>
      <div class="chips">${chips(r.pieces, "rewrite")}</div>
      ${z.note ? `<p class="row-note">${esc(z.note)}</p>` : ""}</div></article>`;
  }).join("");
}

function renderWaiting() {
  $("#zoo-wait").innerHTML = ZOO.filter((z) => z.needs).map((z) =>
    `<article class="row">${nameBlock(z)}<div class="row-out"><p class="needs">Needs ${esc(z.needs)}. Comes with the run.</p></div></article>`).join("");
}

async function main() {
  const vocab = await (await fetch("data/vocab.json")).json();
  ZOO = buildZoo(vocab);
  $("#corpus-note").textContent = `The real run trains its vocabularies on FineWeb-Edu. Those don't exist yet, so rows 3, 4, 5 and 13 use stand-ins trained on this repo's own READMEs (${vocab.corpus.files} files, ${Math.round(vocab.corpus.bytes / 1000)} KB): byte-level BPE with GPT-2's pre-splitting, at 768 and 4,096 tokens, and the ${vocab.phrases.length} 3-word phrases that appear at least 3 times. The plan doesn't fix the vocabulary sizes; these are this page's. A corpus that small cuts everyday words oddly, so read those rows as what BPE does, not as the run's tokens.`;

  $("#examples").innerHTML = EXAMPLES.map(([label], i) =>
    `<button type="button" data-ex="${i}" aria-pressed="${i === 0}">${esc(label)}</button>`).join("");
  $("#input").value = EXAMPLES[0][1];
  $("#examples").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-ex]");
    if (!b) return;
    $("#input").value = EXAMPLES[Number(b.dataset.ex)][1];
    document.querySelectorAll("#examples button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    render();
  });
  let t;
  $("#input").addEventListener("input", () => {
    document.querySelectorAll("#examples button").forEach((x) => x.setAttribute("aria-pressed", "false"));
    clearTimeout(t);
    t = setTimeout(render, 60);
  });
  renderWaiting();
  render();
}

main().catch((err) => {
  $("#count").textContent = `The vocabularies didn't load (${err.message}). Reload the page to try again.`;
});
