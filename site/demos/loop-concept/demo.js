import { runReport } from "./plink.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const LANGS = ["python", "zig", "plink"];
const ARMS = ["cold", "snippet"];
const ARM_TEXT = { cold: "no reference", snippet: "with reference" };
const COPY_MARKS = { python: ["nums = [3, 1, 4]", '"even"'], zig: ["{ 3, 1, 4 }", "even\\n"], plink: ["list(3, 1, 4)", '"even"'] };

const state = { model: "qwen3-1.7b", task: "evens", cell: null };
let R1;

const mark = (r) => (r.lenient ? "pass" : r.strict === "syntax" ? "syntax" : "wrong");
const MARK_TEXT = { pass: "Passed", syntax: "Wouldn't compile or parse", wrong: "Ran, wrong output" };
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const copied = (r) => r.arm === "snippet" && COPY_MARKS[r.lang].some((k) => r.code.includes(k));

// same rule as the experiment's lenient grader: the expected lines must be the last lines printed, labels allowed
function grade(stdout, expected) {
  const norm = (l) => {
    l = l.trim();
    if (/[:=]\s*\S/.test(l)) l = l.replace(/^[^:=]*[:=]\s*/, "");
    return l.trim();
  };
  const got = stdout.trim().split("\n").filter((l) => l.trim()).map(norm);
  const exp = expected.split("\n");
  return got.length >= exp.length && got.slice(-exp.length).join("\n") === exp.join("\n");
}

const rowsFor = (model, f) => R1.models[model].rows.filter(f);
const taskById = (id) => R1.tasks.find((t) => t.id === id);

// ---------------------------------------------------------------- bench

function fillBench(keepEditor = false) {
  const t = taskById(state.task);
  const label = R1.models[state.model].label;
  $("#task-desc").textContent = `Write a program that ${t.desc}.`;
  const py = rowsFor(state.model, (r) => r.task === t.id && r.lang === "python" && r.arm === "cold")[0];
  const pl = rowsFor(state.model, (r) => r.task === t.id && r.lang === "plink" && r.arm === "snippet")[0];
  $("#py-code").textContent = py.code;
  $("#py-note").innerHTML = `${esc(label)}'s greedy answer, no reference: <span class="v-${mark(py)}">${MARK_TEXT[mark(py)].toLowerCase()}</span>`;
  $("#pl-note").innerHTML = `${esc(label)}'s greedy answer with the reference: <span class="v-${mark(pl)}">${MARK_TEXT[mark(pl)].toLowerCase()}</span>` +
    (copied(pl) ? ` <span class="copied">and it copied the reference's example</span>` : "");
  if (!keepEditor) $("#pl-code").value = pl.code;
  $("#result").innerHTML = "";
}

function runEditor() {
  const t = taskById(state.task);
  const rep = runReport($("#pl-code").value);
  let verdict, body = "";
  if (rep.kind === "syntax") {
    verdict = `<p class="verdict v-syntax">Syntax error</p>`;
    body = rep.error;
  } else if (rep.kind === "runtime") {
    verdict = `<p class="verdict v-runtime">It crashed while running</p>`;
    body = (rep.stdout ? rep.stdout + "\n" : "") + rep.error;
  } else if (grade(rep.stdout, t.expected)) {
    verdict = `<p class="verdict v-pass">Passed</p>`;
    body = rep.stdout;
  } else {
    verdict = `<p class="verdict v-wrong">Ran, but the output is wrong</p>`;
    body = `printed:\n${rep.stdout || "(nothing)"}\n\nexpected:\n${t.expected}`;
  }
  $("#result").innerHTML = verdict + `<pre>${esc(body)}</pre>`;
}

// ---------------------------------------------------------------- score

function renderScore() {
  const head = `<thead><tr><th>Model</th><th>Language</th><th>Answers passing,<br>no reference</th>
    <th>Answers passing,<br>with reference</th><th>Wouldn't compile,<br>with reference</th>
    <th>Python-solved tasks<br>it also solves here</th></tr></thead>`;
  let body = "";
  for (const [key, m] of Object.entries(R1.models)) {
    const rows = m.rows;
    const solved = (lang, arm) => new Set(rows.filter((r) => r.lang === lang && r.arm === arm && r.lenient).map((r) => r.task));
    const pySolved = solved("python", "cold");
    LANGS.forEach((lang, i) => {
      const c = (arm) => rows.filter((r) => r.lang === lang && r.arm === arm);
      const passCold = pct(c("cold").filter((r) => r.lenient).length, c("cold").length);
      const passSnip = pct(c("snippet").filter((r) => r.lenient).length, c("snippet").length);
      const syn = pct(c("snippet").filter((r) => r.strict === "syntax").length, c("snippet").length);
      const carried = [...solved(lang, "snippet")].filter((t) => pySolved.has(t)).length;
      body += `<tr>${i === 0 ? `<td rowspan="3" class="lang">${esc(m.label)}</td>` : ""}<td>${R1.langs[lang]}</td>
        <td>${passCold}%</td><td>${passSnip}%</td><td>${syn}%</td>
        <td class="big">${lang === "python" ? `${pySolved.size} of 25 solved` : `${carried} of ${pySolved.size}`}</td></tr>`;
    });
  }
  $("#score").innerHTML = head + `<tbody>${body}</tbody>`;
}

// ---------------------------------------------------------------- every answer

function renderModelSeg() {
  $("#model-seg").innerHTML = Object.entries(R1.models).map(([k, m]) =>
    `<button type="button" data-model="${k}" aria-pressed="${k === state.model}">${esc(m.label)}</button>`).join("");
}

function renderGrid() {
  const rows = R1.models[state.model].rows;
  const head = `<thead><tr><th>Task</th>${LANGS.flatMap((l) => ARMS.map((a) =>
    `<th>${R1.langs[l]}<small>${ARM_TEXT[a]}</small></th>`)).join("")}</tr></thead>`;
  const body = R1.tasks.map((t) => `<tr><td class="task">${t.id}</td>${LANGS.flatMap((l) => ARMS.map((a) => {
    const cell = rows.filter((r) => r.task === t.id && r.lang === l && r.arm === a).sort((x, y) => x.sample - y.sample);
    const key = `${t.id}|${l}|${a}`;
    const label = `${t.id}, ${R1.langs[l]}, ${ARM_TEXT[a]}: ${cell.filter((r) => r.lenient).length} of ${cell.length} passed`;
    return `<td><button type="button" class="cell" data-cell="${key}" aria-pressed="${state.cell === key}" aria-label="${esc(label)}">${
      cell.map((r) => `<i class="mark ${mark(r)}"></i>`).join("")}</button></td>`;
  })).join("")}</tr>`).join("");
  $("#answers").innerHTML = head + `<tbody>${body}</tbody>`;
  if (state.cell) renderDetail();
}

function renderDetail() {
  const [task, lang, arm] = state.cell.split("|");
  const t = taskById(task);
  const cell = rowsFor(state.model, (r) => r.task === task && r.lang === lang && r.arm === arm).sort((x, y) => x.sample - y.sample);
  const cards = cell.map((r) => `
    <article class="answer-card">
      <header><span>${r.sample === 0 ? "Greedy" : `Sample ${r.sample}`}</span>
        <span class="v-${mark(r)}"><i class="mark ${mark(r)}"></i>${MARK_TEXT[mark(r)]}</span></header>
      ${copied(r) ? `<span class="copied">Copied the reference's example</span>` : ""}
      <pre class="code">${esc(r.code)}</pre>
      ${r.detail && !r.lenient ? `<pre class="why">${esc(r.detail)}</pre>` : ""}
      ${lang === "plink" ? `<button type="button" data-try="${r.sample}">Open in the bench</button>` : ""}
    </article>`).join("");
  const d = $("#detail");
  d.hidden = false;
  d.innerHTML = `<h3>${esc(task)} in ${R1.langs[lang]}, ${ARM_TEXT[arm]}</h3>
    <p class="desc">Write a program that ${esc(t.desc)}. Expected output: <span class="expected">${esc(t.expected.replace(/\n/g, " "))}</span></p>
    <div class="answer-list">${cards}</div>`;
}

// ---------------------------------------------------------------- transcripts

// model text with ``` fences shown as code
function prose(text) {
  return text.split(/(```[^\n`]*\n?[\s\S]*?(?:```|$))/).filter((p) => p.trim()).map((p) => {
    const m = p.match(/^```[^\n`]*\n?([\s\S]*?)(?:```)?$/);
    return m ? `<p class="call">Final answer</p><pre class="code">${esc(m[1].trim())}</pre>` : `<p>${esc(p.trim())}</p>`;
  }).join("");
}

let AG = null;
const ag = { model: "Gemma 4 E2B", lang: "zig", task: "evens", attempt: 0 };

function options(sel, values, current, label = (v) => v) {
  sel.innerHTML = values.map((v) => `<option value="${esc(v)}"${String(v) === String(current) ? " selected" : ""}>${esc(label(v))}</option>`).join("");
}

function renderPickers() {
  const uniq = (xs) => [...new Set(xs)];
  options($("#ag-model"), uniq(AG.map((c) => c.model)), ag.model);
  const forModel = AG.filter((c) => c.model === ag.model);
  options($("#ag-lang"), uniq(forModel.map((c) => c.lang)), ag.lang, (v) => R1.langs[v]);
  const forLang = forModel.filter((c) => c.lang === ag.lang);
  options($("#ag-task"), uniq(forLang.map((c) => c.task)), ag.task, (v) => {
    const n = forLang.filter((c) => c.task === v && c.verdict === "pass").length;
    return n ? `${v} (passed ${n} of 3)` : v;
  });
  options($("#ag-attempt"), forLang.filter((c) => c.task === ag.task).map((c) => c.attempt), ag.attempt, (v) => {
    const c = forLang.find((x) => x.task === ag.task && x.attempt === v);
    return `${v + 1}: ${c.verdict === "pass" ? "passed" : "failed"}`;
  });
}

function renderTranscript() {
  const c = AG.find((x) => x.model === ag.model && x.lang === ag.lang && x.task === ag.task && x.attempt === ag.attempt);
  if (!c) { $("#transcript").innerHTML = `<p class="loading">No attempt matches that choice.</p>`; return; }
  const t = taskById(c.task);
  let lastCode = null;
  const turns = c.steps.map((s) => {
    if (s.role === "tool") {
      const err = /exit code: [1-9]|error/i.test(s.text) && !/exit code: 0/.test(s.text);
      return `<div class="turn tool${err ? " err" : ""}"><span class="who">${esc(s.name || "tool")} result</span>
        <div class="what"><pre class="code">${esc(s.text.trim())}</pre></div></div>`;
    }
    const calls = s.calls.map((call) => {
      const code = call.args && call.args.code;
      if (call.name === "run" && code) {
        const same = lastCode !== null && code.trim() === lastCode.trim();
        lastCode = code;
        return { same, html: `<p class="call">Runs this program</p><pre class="code">${esc(code)}</pre>` };
      }
      const args = Object.entries(call.args || {}).filter(([, v]) => v !== "" && v != null).map(([k, v]) => `${k}: ${v}`).join(", ");
      return { same: false, html: `<p class="call">Calls ${esc(call.name)}${args ? ` (${esc(args)})` : ""}</p>` };
    });
    const same = calls.length && calls.every((x) => x.same);
    const text = s.text && s.text.trim() ? prose(s.text.trim()) : "";
    if (!text && !calls.length) return "";
    return `<div class="turn model${same ? " same" : ""}"><span class="who">${esc(c.model)}</span>
      <div class="what">${text}${calls.map((x) => x.html).join("")}</div></div>`;
  }).join("");
  const outcome = c.verdict === "pass" ? `<span class="v-pass">Final answer passed.</span>`
    : `<span class="v-${c.verdict === "syntax" ? "syntax" : "wrong"}">Final answer ${c.verdict === "syntax" ? "didn't compile" : "gave the wrong output"}.</span>`;
  const ended = c.end === "turn limit" ? " It ran out of turns." : "";
  $("#transcript").innerHTML = `<div class="turn"><span class="who">Task</span><div class="what"><p>Write a ${esc(R1.langs[c.lang])} program that ${esc(t.desc)}.</p></div></div>
    ${turns}<p class="outcome">${outcome}${ended}</p>`;
}

async function loadAgents() {
  try {
    AG = await (await fetch("data/agents.json")).json();
  } catch {
    $("#transcript").innerHTML = `<p class="loading">Couldn't load the transcripts. Reload the page to try again.</p>`;
    return;
  }
  renderPickers();
  renderTranscript();
}

// ---------------------------------------------------------------- wiring

async function main() {
  R1 = await (await fetch("data/round1.json")).json();
  const sel = $("#task");
  sel.innerHTML = R1.tasks.map((t) => `<option value="${t.id}"${t.id === state.task ? " selected" : ""}>${t.id}</option>`).join("");
  $("#ref").textContent = R1.snippets.plink;
  fillBench();
  renderScore();
  renderModelSeg();
  renderGrid();

  sel.addEventListener("change", () => { state.task = sel.value; fillBench(); });
  $("#run").addEventListener("click", runEditor);
  $("#reset").addEventListener("click", () => fillBench());
  $("#pl-code").addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); runEditor(); }
  });
  $("#show-ref").addEventListener("click", (e) => {
    const open = $("#ref").hidden;
    $("#ref").hidden = !open;
    e.currentTarget.setAttribute("aria-expanded", String(open));
    e.currentTarget.textContent = open ? "Hide the reference" : "Show the reference it was given";
  });
  $("#model-seg").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-model]");
    if (!b) return;
    state.model = b.dataset.model;
    renderModelSeg();
    renderGrid();
    fillBench();
  });
  $("#answers").addEventListener("click", (e) => {
    const b = e.target.closest(".cell");
    if (!b) return;
    state.cell = state.cell === b.dataset.cell ? null : b.dataset.cell;
    document.querySelectorAll(".cell").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.cell === state.cell)));
    if (state.cell) renderDetail(); else $("#detail").hidden = true;
  });
  $("#detail").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-try]");
    if (!b) return;
    const [task, lang, arm] = state.cell.split("|");
    const r = rowsFor(state.model, (x) => x.task === task && x.lang === lang && x.arm === arm && x.sample === Number(b.dataset.try))[0];
    state.task = task;
    $("#task").value = task;
    fillBench();
    $("#pl-code").value = r.code;
    $(".bench").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    runEditor();
  });

  for (const [id, key] of [["#ag-model", "model"], ["#ag-lang", "lang"], ["#ag-task", "task"], ["#ag-attempt", "attempt"]]) {
    $(id).addEventListener("change", (e) => {
      ag[key] = key === "attempt" ? Number(e.target.value) : e.target.value;
      const pool = AG.filter((c) => c.model === ag.model && c.lang === ag.lang);
      if (!pool.length) ag.lang = AG.find((c) => c.model === ag.model).lang;
      const pool2 = AG.filter((c) => c.model === ag.model && c.lang === ag.lang);
      if (!pool2.some((c) => c.task === ag.task)) ag.task = pool2[0].task;
      if (!pool2.some((c) => c.task === ag.task && c.attempt === ag.attempt)) ag.attempt = pool2.find((c) => c.task === ag.task).attempt;
      renderPickers();
      renderTranscript();
    });
  }
  document.querySelector(".player-picks .seg").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-pick]");
    if (!b || !AG) return;
    const [model, lang, task, attempt] = b.dataset.pick.split("|");
    Object.assign(ag, { model, lang, task, attempt: Number(attempt) });
    document.querySelectorAll("[data-pick]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderPickers();
    renderTranscript();
  });
  document.querySelector('[data-pick^="Gemma"]').setAttribute("aria-pressed", "true");
  document.querySelector('[data-pick^="Qwen"]').setAttribute("aria-pressed", "false");

  // the transcripts are the big file; fetch them once the section is near
  const io = new IntersectionObserver((entries) => {
    if (entries.some((x) => x.isIntersecting)) { io.disconnect(); loadAgents(); }
  }, { rootMargin: "600px" });
  io.observe($(".player"));
}

main().catch((err) => {
  $("#result").innerHTML = `<p class="verdict v-syntax">The page's data didn't load (${esc(err.message)}). Reload to try again.</p>`;
});
