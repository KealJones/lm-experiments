import { GPT2Tokenizer } from "./tokenizer.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const INITS = { default: "Standard init (std 0.02)", normal1: "Normal, std 1", normal10: "Normal, std 10", uniform: "Uniform, −1 to 1" };
const SHORT = { default: "Standard", normal1: "Std 1", normal10: "Std 10", uniform: "Uniform" };
const PROMPTS = ["The cat sat on the", "Once upon a time", "def add(a, b):"];
const BLIND = Math.log(50257);

const state = { init: "default", seed: 0, busy: false };
let tok, passage, REC, worker;

const fmtPct = (p) => (p >= 0.001 ? (100 * p).toFixed(1) + "%" : p >= 1e-7 ? (100 * p).toPrecision(2) + "%" : "≈ 0%");
// losses near a blind guess need 3 decimals to show the gap; big ones don't
const fmtLoss = (x) => (x >= 1000 ? Math.round(x).toLocaleString("en-US") : x >= 15 ? x.toFixed(1) : x.toFixed(3));
const fmtDiff = (x) => (x >= 1000 ? Math.round(x).toLocaleString("en-US") : x >= 1 ? x.toFixed(1) : x.toFixed(3));
const barToken = (t) => (t.trim() === "" ? t.replace(/ /g, "␣").replace(/\n/g, "↵") || "(empty)" : visible(t));
const visible = (s) => s.replace(/\n/g, "↵").replace(/\t/g, "⇥");

function tokenSpans(pieces) {
  return pieces.map((p) => `<span class="tok">${esc(visible(p))}</span>`).join("");
}

// ---------------------------------------------------------------- live model

function call(msg, onMsg) {
  return new Promise((resolve, reject) => {
    worker.onmessage = ({ data }) => {
      if (data.type === "error") reject(new Error(data.message));
      else if (onMsg(data)) resolve(data);
    };
    worker.postMessage(msg);
  });
}

function setBusy(on, text) {
  state.busy = on;
  for (const b of document.querySelectorAll(".bench button")) b.disabled = on;
  if (text !== undefined) $("#status").textContent = text;
}

async function rebuild() {
  setBusy(true, "Filling 6.9 million weights…");
  $("#score-out").innerHTML = "";
  const r = await call({ type: "build", init: state.init, seed: state.seed }, (d) => d.type === "built");
  return r;
}

async function generate() {
  const prompt = $("#prompt").value || " ";
  const ids = tok.encode(prompt).slice(-200);
  setBusy(true, "Writing…");
  const streams = { true: [], false: [] };
  const show = () => {
    $("#sampled").innerHTML = `<span class="prompt">${esc(prompt)}</span>` + tokenSpans(streams.true.map((i) => tok.decode(i)));
    $("#greedy").innerHTML = `<span class="prompt">${esc(prompt)}</span>` + tokenSpans(streams.false.map((i) => tok.decode(i)));
  };
  show();
  const done = await call({ type: "generate", ids, seed: state.seed }, (d) => {
    if (d.type === "token") { streams[d.sample].push(d.id); show(); }
    return d.type === "generated";
  });
  $("#first").innerHTML = done.firstTop.map(({ id, prob }) => `<li><span class="t">${esc(barToken(tok.decode(id)))}</span>
    <span class="track"><span class="fill" style="width:${Math.max(0, Math.min(100, 100 * prob))}%"></span></span>
    <span class="v">${fmtPct(prob)}</span></li>`).join("");
  setBusy(false, `Seed ${state.seed}, ${INITS[state.init].toLowerCase()}. Try another seed or fill, or score it.`);
}

async function rebuildAndGenerate() {
  try {
    await rebuild();
    await generate();
  } catch (e) {
    setBusy(false, `The model stopped with an error: ${e.message}. Reload the page to try again.`);
  }
}

function gauge(loss) {
  // log scale from 1 to 10,000
  const x = (v) => (Math.log10(Math.max(1, v)) / 4) * 100;
  const ticks = [1, 10, 100, 1000, 10000];
  return `<div class="gauge"><svg viewBox="0 0 100 16" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="100" y1="8" y2="8" stroke="var(--rule)" stroke-width="0.6" vector-effect="non-scaling-stroke"/>
    ${ticks.map((t) => `<line x1="${x(t)}" x2="${x(t)}" y1="5" y2="11" stroke="var(--rule)" vector-effect="non-scaling-stroke"/>`).join("")}
    <line x1="${x(BLIND)}" x2="${x(BLIND)}" y1="1" y2="15" stroke="var(--syntax)" stroke-width="2" vector-effect="non-scaling-stroke"/>
    <line x1="${x(1)}" x2="${x(loss)}" y1="8" y2="8" stroke="var(--ink)" stroke-width="5" vector-effect="non-scaling-stroke"/>
  </svg></div>
  <p class="note">Log scale, 1 to 10,000. The red tick is the blind guess.</p>`;
}

async function score() {
  setBusy(true, "Scoring 255 predictions…");
  try {
    const r = await call({ type: "score", ids: passage.ids }, (d) => {
      if (d.type === "progress") $("#status").textContent = `Scoring… ${d.done} of ${d.of} predictions`;
      return d.type === "scored";
    });
    const diff = r.loss - BLIND;
    const rec = REC.gpt2.inits[state.init].first_row_loss;
    $("#score-out").innerHTML = `<p class="score-line">Loss ${fmtLoss(r.loss)}:
      <span class="v-${diff > 0 ? "syntax" : "pass"}">${diff > 0 ? `${fmtDiff(diff)} worse` : `${fmtDiff(-diff)} better`} than a blind guess</span></p>
      ${gauge(r.loss)}
      <p class="note">It predicted ${r.distinct} different tokens as its top pick across the 255 positions. The
      experiment's own ${INITS[state.init].toLowerCase()} model scored ${fmtLoss(rec)} on this same passage.</p>`;
    setBusy(false, `Seed ${state.seed}, ${INITS[state.init].toLowerCase()}.`);
  } catch (e) {
    setBusy(false, `Scoring stopped with an error: ${e.message}.`);
  }
}

// ---------------------------------------------------------------- recorded chart

function chart() {
  const W = 320, rowH = 30, top = 14, left = 66, right = 18;
  const H = top + rowH * 4 + 26;
  const x = (v) => left + (Math.log10(Math.max(1, v)) / 4) * (W - left - right);
  const ticks = [1, 10, 100, 1000, 10000];
  $("#chart").innerHTML = Object.entries(REC).map(([arch, a]) => {
    const blind = Math.log(a.vocab);
    const rows = Object.keys(INITS).map((init, i) => {
      const loss = a.inits[init].loss;
      const y = top + i * rowH;
      const end = x(loss);
      const label = fmtLoss(loss);
      const inside = end > W - right - 34;
      return `<text class="init" x="${left - 8}" y="${y + 15}" text-anchor="end">${SHORT[init]}</text>
        <rect class="bar" x="${x(1)}" y="${y + 5}" width="${Math.max(1, end - x(1))}" height="14" rx="1"/>
        <text class="val" x="${inside ? end - 4 : end + 4}" y="${y + 16}" text-anchor="${inside ? "end" : "start"}"
          ${inside ? 'style="fill:var(--paper)"' : ""}>${label}</text>`;
    }).join("");
    const axis = ticks.map((t) => `<g class="tick"><line x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${top + rowH * 4}"/>
      <text x="${x(t)}" y="${top + rowH * 4 + 14}" text-anchor="middle">${t.toLocaleString("en-US")}</text></g>`).join("");
    const desc = Object.keys(INITS).map((i) => `${INITS[i]} ${fmtLoss(a.inits[i].loss)}`).join(", ");
    return `<figure>
      <figcaption>${esc(a.label)}<small>${(a.params / 1e6).toFixed(1)}M parameters, ${a.vocab.toLocaleString("en-US")}-token vocabulary</small></figcaption>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`${a.label} loss by fill: ${desc}. Blind guess ${blind.toFixed(3)}.`)}">
        ${axis}${rows}
        <line class="blind" x1="${x(blind)}" x2="${x(blind)}" y1="${top - 6}" y2="${top + rowH * 4}"/>
        <text class="blind-label" x="${x(blind) + 4}" y="${top - 2}">blind guess ${blind.toFixed(2)}</text>
      </svg></figure>`;
  }).join("");
}

// ---------------------------------------------------------------- recorded samples

function renderRecorded() {
  const arch = $("#rec-arch").value, init = $("#rec-init").value;
  const a = REC[arch], r = a.inits[init];
  $("#rec-sub").textContent = `${a.label}'s architecture at 2 layers, width 128: ${(a.params / 1e6).toFixed(1)}M parameters. ` +
    `Loss ${fmtLoss(r.loss)}, which is ${fmtDiff(r.above_blind)} above a blind guess, with ${r.distinct_top1.toLocaleString("en-US")} ` +
    `different top picks across 10,240 positions.`;
  $("#rec-samples").innerHTML = r.samples.map((s) => `<article>
      <p class="kind">Sampled, 20 tokens</p>
      <p class="tokens"><span class="prompt">${esc(s.prompt)}</span>${tokenSpans(s.sampled)}</p>
      <p class="kind">Greedy, 12 tokens</p>
      <p class="tokens"><span class="prompt">${esc(s.prompt)}</span>${tokenSpans(s.greedy)}</p>
    </article>`).join("");
  $("#favs").innerHTML = r.favourites.map(({ token, share }) => `<li><span class="t">${esc(barToken(token))}</span>
    <span class="track"><span class="fill" style="width:${100 * share}%"></span></span><span class="v">${fmtPct(share)}</span></li>`).join("");
}

// ---------------------------------------------------------------- wiring

async function main() {
  const [tk, ps, rec] = await Promise.all(["gpt2-tokenizer", "passage", "recorded"].map((f) => fetch(`data/${f}.json`).then((r) => r.json())));
  tok = new GPT2Tokenizer(tk);
  passage = ps;
  REC = rec;

  $("#fill").innerHTML = Object.entries(INITS).map(([k, v]) => `<button type="button" data-init="${k}" aria-pressed="${k === state.init}">${v}</button>`).join("");
  $("#chips").innerHTML = PROMPTS.map((p) => `<button type="button" data-prompt="${esc(p)}">${esc(p)}</button>`).join("");
  $("#rec-arch").innerHTML = Object.entries(REC).map(([k, a]) => `<option value="${k}">${esc(a.label)}</option>`).join("");
  $("#rec-init").innerHTML = Object.entries(INITS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $("#meta-line").innerHTML = `Runs: local CPU, free, 3 Nov 2026. This page's recorded numbers come from rerunning the
    experiment's own <code>model.py</code> with <code>record.py</code>, which gives the same losses as the write-up.
    <a href="https://github.com/KealJones/lm-experiments/tree/main/experiments/random-weights">The code and full write-up</a>`;
  chart();
  renderRecorded();

  $("#fill").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-init]");
    if (!b || state.busy) return;
    state.init = b.dataset.init;
    document.querySelectorAll("#fill button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    rebuildAndGenerate();
  });
  $("#reroll").addEventListener("click", () => {
    state.seed = Math.floor(Math.random() * 100000);
    $("#seed").value = state.seed;
    rebuildAndGenerate();
  });
  $("#seed").addEventListener("change", () => {
    const v = Math.max(0, Math.min(99999, Math.floor(Number($("#seed").value) || 0)));
    $("#seed").value = v;
    if (v !== state.seed && !state.busy) { state.seed = v; rebuildAndGenerate(); }
  });
  $("#chips").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-prompt]");
    if (!b || state.busy) return;
    $("#prompt").value = b.dataset.prompt;
    generate();
  });
  $("#go").addEventListener("click", () => { if (!state.busy) generate(); });
  $("#prompt").addEventListener("keydown", (e) => { if (e.key === "Enter" && !state.busy) generate(); });
  $("#score").addEventListener("click", () => { if (!state.busy) score(); });
  $("#rec-arch").addEventListener("change", renderRecorded);
  $("#rec-init").addEventListener("change", renderRecorded);

  worker = new Worker("worker.js");
  rebuildAndGenerate();
}

main().catch((e) => {
  $("#status").textContent = `The page's data didn't load (${e.message}). Reload to try again.`;
});
