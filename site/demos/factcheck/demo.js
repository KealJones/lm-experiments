const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const ARM_ORDER = ["free", "lookup", "think", "force", "read"];

let IX;                       // data/index.json
const RUNS = new Map();       // "key-arm" -> loaded run file
const state = { key: "qwen3", arm: "read", qid: "australia", sample: "0", style: "strict" };
const tally = { right: 0, total: 0 };
let revealed = false;

const runOf = (key, arm) => IX.runs.find((r) => r.key === key && r.arm === arm);
const pct = ([a, b]) => (b ? `${Math.round((100 * a) / b)}%` : "-");
const frac = (p) => (p ? `${p[0]}/${p[1]}` : "-");
const plainText = (s) => String(s ?? "").replace(/\*\*?([^*]+)\*\*?/g, "$1"); // the models write markdown

async function loadRun(key, arm) {
  const id = `${key}-${arm}`;
  if (!RUNS.has(id)) RUNS.set(id, fetch(`data/runs/${id}.json`).then((r) => r.json()));
  return RUNS.get(id);
}

// ---------------------------------------------------------------- pickers

function options(sel, items, current) {
  sel.innerHTML = items.map(([v, label]) => `<option value="${esc(v)}"${String(v) === String(current) ? " selected" : ""}>${esc(label)}</option>`).join("");
}

function renderPickers() {
  options($("#pick-q"), IX.questions.map((q) => [q.id, q.q]), state.qid);
  options($("#pick-model"), Object.entries(IX.models), state.key);
  const arms = ARM_ORDER.filter((a) => runOf(state.key, a));
  if (!arms.includes(state.arm)) state.arm = arms.includes("read") ? "read" : arms[0];
  options($("#pick-arm"), arms.map((a) => [a, `${a}: ${IX.arms[a]}`]), state.arm);
  options($("#pick-sample"), [["0", "Its draft, sample 1"], ["1", "Its draft, sample 2"], ["2", "Its draft, sample 3"], ["planted", "A planted wrong answer"]], state.sample);
  options($("#pick-style"), [["plain", "Plain: \"is it good and right?\""], ["strict", "Strict: \"assume it's wrong\""]], state.style);
}

// ---------------------------------------------------------------- transcripts

function renderSteps(item, texts, actor) {
  const rows = item.steps.map((s) => {
    if (s.k === "think") return `<div class="step think"><span class="who">${esc(actor)} thinks</span><div class="what"><pre class="code">${esc(s.t)}</pre></div></div>`;
    if (s.k === "say") return `<div class="step say"><span class="who">${esc(actor)}</span><div class="what"><pre class="code">${esc(s.t)}</pre></div></div>`;
    if (s.k === "call") {
      const args = Object.entries(s.args || {}).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");
      const who = s.by === "code" ? "The code" : actor;
      const verb = { search: "searches Wikipedia", read_page: "reads a Wikipedia page", wikidata: "asks Wikidata" }[s.name] || `calls ${s.name}`;
      return `<div class="step callstep"><span class="who">${esc(who)}</span><div class="what"><p class="call">${verb}${args ? ` <code>${esc(args)}</code>` : ""}</p></div></div>`;
    }
    return `<div class="step tool"><span class="who">${esc(s.name || "tool")} result</span><div class="what"><pre class="code">${esc(texts[s.i])}</pre></div></div>`;
  });
  return rows.join("");
}

function mark(ok) {
  return ok ? `<span class="v-pass">right</span>` : `<span class="v-fail">wrong</span>`;
}

async function render() {
  revealed = false;
  const q = IX.questions.find((x) => x.id === state.qid);
  const model = IX.models[state.key];
  const planted = state.sample === "planted";
  $("#q-text").textContent = `"${q.q}"`;
  $("#q-truth").innerHTML = `Correct answer, checked 4 Nov 2026: <strong>${esc(q.answer)}</strong>${q.trap ? `. The trap: ${esc(q.trap)}.` : ""}`;
  $("#prompt-draft").textContent = IX.prompts[`draft:${state.arm}`] + "\n\n" + q.q;
  $("#prompt-review").textContent = IX.prompts[`review:${state.style}`];
  document.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.preset === presetKey())));
  renderReviewTable();

  $("#draft").innerHTML = `<p class="loading">Loading…</p>`;
  $("#review").hidden = true;
  $("#guess").hidden = false;
  const run = await loadRun(state.key, state.arm);
  if (presetKey() !== currentKey) return; // a newer pick came in while loading

  if (planted) {
    $("#draft-note").textContent = "Not the model's own answer: a known-wrong answer planted for this question, to see whether the reviewer catches it.";
    $("#draft").innerHTML = `<div class="final"><span class="label">Answer to check</span><span class="val">${esc(q.planted)}</span>${mark(false)}</div>`;
  } else {
    const d = run.drafts.find((x) => x.qid === state.qid && String(x.sample) === state.sample);
    $("#draft-note").textContent = `${model}, ${state.arm} arm: ${IX.arms[state.arm]}.` +
      (state.arm === "read" ? " The first search and page read were done by the code, not the model." : "") +
      (state.arm === "force" ? " The first search call was started for it." : "");
    $("#draft").innerHTML = renderSteps(d, run.texts, model) +
      `<div class="final"><span class="label">Draft answer</span><span class="val">${esc(plainText(d.final) || "(no answer)")}</span>${mark(d.correct)}</div>`;
  }
  const r = review(run);
  $("#review-note").textContent = r
    ? `${model} again, in a fresh chat, with the ${state.style} prompt and the same tools.`
    : "This review wasn't run.";
  $("#guess").hidden = !r;
  renderTally();
}

function review(run) {
  const planted = state.sample === "planted";
  return run.reviews.find((x) => x.qid === state.qid && x.style === state.style &&
    (planted ? x.source === "planted" : x.source === "own" && String(x.sample) === state.sample));
}

async function reveal(guess) {
  const run = await loadRun(state.key, state.arm);
  const r = review(run);
  if (!r || revealed) return;
  revealed = true;
  const model = IX.models[state.key];
  const said = r.verdict ? r.verdict.toUpperCase() : null;
  const draftRight = r.draft_correct;
  let outcome = "";
  if (guess !== "skip") {
    tally.total++;
    const hit = r.verdict === guess;
    if (hit) tally.right++;
    outcome = hit ? `<p class="called v-pass">You called it.</p>` : `<p class="called v-fail">${said ? `It said ${said}.` : "It never gave a verdict."}</p>`;
  }
  let judged;
  if (!said) judged = `<span class="v-part">No verdict line</span>`;
  else if ((r.verdict === "wrong") === !draftRight) judged = `<span class="v-pass">${said}, correctly</span>`;
  else judged = `<span class="v-fail">${said}, on ${draftRight ? "a right" : "a wrong"} answer</span>`;
  $("#review").innerHTML = outcome + renderSteps(r, run.texts, model) +
    `<div class="final"><span class="label">Verdict</span><span class="verdict-line">${judged}</span></div>
     <div class="final"><span class="label">Answer the user gets</span><span class="val">${esc(plainText(r.final_answer) || "(none)")}</span>${mark(r.final_correct)}</div>`;
  $("#review").hidden = false;
  $("#guess").hidden = true;
  renderTally();
}

function renderTally() {
  $("#tally").textContent = tally.total ? `Your calls so far: ${tally.right} of ${tally.total}` : "";
}

// ---------------------------------------------------------------- tables

function renderDraftsTable() {
  const head = `<thead><tr><th>Model</th>${ARM_ORDER.map((a) => `<th title="${esc(IX.arms[a])}">${a}</th>`).join("")}</tr></thead>`;
  const best = Math.max(...IX.runs.map((r) => r.draft_right));
  const rows = Object.entries(IX.models).map(([key, label]) => `<tr><td>${esc(label)}</td>${ARM_ORDER.map((a) => {
    const r = runOf(key, a);
    if (!r) return `<td class="dim">-</td>`;
    const w = Math.round((r.draft_right / r.drafts) * 3.5 * 10) / 10;
    return `<td${r.draft_right === best ? ' class="v-pass"' : ""}>${r.draft_right}<span class="bar" style="width:${w}rem" aria-hidden="true"></span></td>`;
  }).join("")}</tr>`).join("");
  const haiku = Object.values(IX.haiku.drafts).filter((d) => d.correct).length;
  const h = `<tr><td><em>Claude Haiku, web search</em></td><td colspan="5"><em>${haiku} of 12 questions, one draft each</em></td></tr>`;
  $("#drafts-table").innerHTML = head + `<tbody>${rows}${h}</tbody>`;
}

function renderReviewTable() {
  const head = `<thead><tr><th>Model and arm</th><th>Draft right</th><th>Final right,<br>plain review</th>
    <th>Final right,<br>strict review</th><th>False alarms,<br>strict</th><th>Planted caught,<br>strict</th></tr></thead>`;
  const rows = IX.runs.map((r) => {
    const p = r.styles.plain, s = r.styles.strict;
    const cur = r.key === state.key && r.arm === state.arm;
    const d = r.draft_right / r.drafts;
    const cls = (pair) => {
      const v = pair[0] / pair[1];
      return v > d + 0.04 ? "v-pass" : v < d - 0.04 ? "v-fail" : "";
    };
    return `<tr class="${cur ? "current" : ""}"><td><span class="model">${esc(r.model)}</span> ${r.arm}</td>
      <td>${pct([r.draft_right, r.drafts])}</td>
      <td class="${cls(p.final_right)}">${pct(p.final_right)}</td><td class="${cls(s.final_right)}">${pct(s.final_right)}</td>
      <td>${frac(s.false_alarm)}</td><td>${frac(s.planted_caught)}</td></tr>`;
  }).join("");
  $("#review-table").innerHTML = head + `<tbody>${rows}</tbody>`;
}

function renderEvidenceTable() {
  const head = `<thead><tr><th>Model, read arm</th><th>Answer was in the text</th><th>Answer wasn't</th></tr></thead>`;
  const rows = Object.entries(IX.evidence_split).map(([key, s]) =>
    `<tr><td>${esc(IX.models[key])}</td><td class="${s.in[0] === s.in[1] ? "v-pass" : ""}">${s.in[0]} of ${s.in[1]}</td><td>${s.out[0]} of ${s.out[1]}</td></tr>`).join("");
  $("#ev-table").innerHTML = head + `<tbody>${rows}</tbody>`;
}

// ---------------------------------------------------------------- wiring

let currentKey = "";
const presetKey = () => `${state.key}|${state.arm}|${state.qid}|${state.sample === "planted" ? "0|planted" : state.sample + "|own"}|${state.style}`;

function update() {
  currentKey = presetKey();
  renderPickers();
  render();
}

async function main() {
  IX = await (await fetch("data/index.json")).json();
  renderDraftsTable();
  renderEvidenceTable();
  update();

  for (const [id, k] of [["#pick-q", "qid"], ["#pick-model", "key"], ["#pick-arm", "arm"], ["#pick-sample", "sample"], ["#pick-style", "style"]]) {
    $(id).addEventListener("change", (e) => { state[k] = e.target.value; update(); });
  }
  document.querySelector(".presets").addEventListener("click", (e) => {
    const b = e.target.closest("[data-preset]");
    if (!b) return;
    const [key, arm, qid, sample, source, style] = b.dataset.preset.split("|");
    Object.assign(state, { key, arm, qid, style, sample: source === "planted" ? "planted" : sample });
    update();
  });
  $("#guess").addEventListener("click", (e) => {
    const b = e.target.closest("[data-guess]");
    if (b) reveal(b.dataset.guess);
  });
}

main().catch((err) => {
  $("#draft").innerHTML = `<p class="v-fail">The page's data didn't load (${esc(err.message)}). Reload to try again.</p>`;
});
