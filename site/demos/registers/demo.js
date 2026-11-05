import { makeSkins, Sim, WHY } from "./world.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const MODELS = {
  base: { name: "No slots", note: "plain GPT" },
  "taught-ends": { name: "Sentence-end slots", note: "taught by the simulator" },
  "taught-every": { name: "Every-word slots", note: "taught by the simulator" },
  "self-every": { name: "Every-word slots", note: "no teacher" },
};
const OBS = { H: "hidden item", C: "closed door", L: "locked door", KH: "hidden key", KC: "key behind a closed door", S: "choose by property" };
const TESTS = [["short", "Short"], ["long", "Long"], ["messy_short", "Messy short"], ["messy_long", "Messy long"]];
const BOOKKEEPING = new Set(["bad go", "bad take", "bad open", "bad unlock", "false claim"]);
const SLOT_NAMES = ["Where it is", "Holding", "Door here", "Goal item"];
const CHANCE = [0.2, 0.25, 0.25, 0.2];

let D, S;
const st = { pid: "long-0", skin: "home", messy: false, hide: false, plan: [] }; // plan: home-word sentences the visitor added

const problem = () => D.problems.find((p) => p.id === st.pid);
const sk = (text) => S.toSkin(text, st.skin);
const places = () => ({ places: D.places, doorPlaces: D.door_places });

// ---------------------------------------------------------------- running a plan

// Replays the visitor's sentences through the checker. Returns the rows to show and the state table.
function replay(ep, sentences, skin) {
  const sim = new Sim(ep, skin, S, places());
  const known = {};
  for (const f of ep.facts) {
    const m = f.match(/^the door of the (\w+) is (\w+) \.$/);
    if (m) known[m[1]] = m[2];
  }
  const rows = [];
  for (const text of sentences) {
    const inject = sim.step(sk(text).split(" "));
    rows.push({ text, fail: sim.status === "fail" ? sim.why : null });
    if (sim.status === "fail") break;
    const m = text.match(/opens the door of the (\w+)/);
    if (m) known[m[1]] = "open";
    if (inject) rows.push({ text: S.toHome(inject.split(" "), skin), result: true });
    if (sim.status === "ok") break;
  }
  const door = !D.door_places.includes(sim.here) ? "none" : known[sim.here] ?? "unknown";
  return { sim, rows, state: { where: sim.here, key: sim.held.has("key"), target: sim.held.has(ep.target), door, goal: ep.target } };
}

// ---------------------------------------------------------------- bench

function problemLabel(p) {
  const n = Number(p.id.split("-")[1]) + 1;
  return `${p.split === "short" ? "Short" : "Long"} ${n}: ${p.obs.map((o) => OBS[o]).join(", ") || "no obstacles"}`;
}

function renderSkins() {
  $("#skins").innerHTML = Object.keys(D.skins).map((s) => {
    const unseen = D.unseen.includes(s);
    return `<button type="button" data-skin="${s}" aria-pressed="${s === st.skin}">${s}${unseen ? " <small>unseen</small>" : ""}</button>`;
  }).join("");
  const note = $("#skin-note");
  if (D.unseen.includes(st.skin)) {
    note.className = "skin-note unseen";
    note.textContent = `The models never saw a plan in ${st.skin} words, only loose sentences. Same problem, same plan, new nouns.`;
  } else {
    note.className = "skin-note";
    note.textContent = `${st.skin[0].toUpperCase() + st.skin.slice(1)} is one of the 4 skins the models planned in during training. Every skin has its own word for each agent, place, item and verb.`;
  }
}

function renderProblem() {
  const p = problem();
  const words = (t) => (st.messy ? sk(t).replace(/ \./g, "") : sk(t));
  const facts = p.facts.map((f) => esc(words(f))).join(" ");
  $("#problem-text").innerHTML = `${facts} <span class="goal">${esc(words(p.plan[0].text))}</span> plan :`;
}

function goldSentences(p) {
  return p.plan.slice(1).filter((s) => s.trained).map((s) => s.text);
}

function renderPlan() {
  const p = problem();
  const { sim, rows, state } = replay(p, st.plan, st.skin);
  const list = rows.map((r) => {
    if (r.result) return `<li class="result">${esc(sk(r.text))}</li>`;
    if (r.fail) return `<li class="fail">${esc(sk(r.text))}<span class="why">${esc(r.fail)}: ${esc(WHY[r.fail] || "")}</span></li>`;
    return `<li>${esc(sk(r.text))}</li>`;
  });
  if (!rows.length) list.push(`<li class="empty">Nothing yet. Pick a sentence below, or show the gold plan one step at a time.</li>`);
  if (sim.status === "ok") list.push(`<li class="won">The goal is reached. The world accepts this plan.</li>`);
  $("#plan").innerHTML = list.join("");

  const over = sim.status !== null;
  for (const el of ["#action", "#arg1", "#arg2", "#add"]) $(el).disabled = over;
  const gold = goldSentences(p);
  const onPath = st.plan.every((t, i) => t === gold[i]);
  $("#gold").disabled = over || !onPath || st.plan.length >= gold.length;
  $("#gold").textContent = onPath ? "Show the next gold step" : "Off the gold path (start over to follow it)";
  $("#undo").disabled = !st.plan.length;
  renderTable(state);
}

let lastState = null;
function renderTable(state) {
  const p = problem();
  const holding = state.key && state.target ? `key, ${p.target}` : state.key ? "key" : state.target ? p.target : "nothing";
  const door = { none: "no door here", unknown: "not told", open: "open", closed: "closed", locked: "locked" }[state.door];
  const values = [state.where, holding, door, state.goal].map((v) => sk(v));
  const best = D.models["taught-every"];
  $("#slots").className = "slots" + (st.hide ? " hidden" : "");
  $("#slots").innerHTML = values.map((v, i) => {
    const changed = lastState && lastState[i] !== v ? " changed" : "";
    return `<div><dt>${SLOT_NAMES[i]}</dt><dd class="${changed.trim()}">${esc(v)}</dd>
      <span class="acc">Slots read this right ${Math.round(100 * best.slots_seen[i])}% of the time in plan skins, ${Math.round(100 * best.slots_unseen[i])}% in farm and space</span></div>`;
  }).join("");
  lastState = values;
  $("#slots-foot").textContent = st.hide
    ? "Hidden, like the plain model: it has to work all of this out again from the text at every word."
    : "Holding counts only the key and the wanted item, the two things the slot was taught. Readout figures: every-word taught slots, mean of 5 seeds, after teaching stopped.";
}

// sentence builder
const ACTIONS = [
  { id: "go", label: "Go to…", arg: "place", t: (a, x) => `the ${a} is not at the ${x} , so the ${a} goes to the ${x} .` },
  { id: "open", label: "Open the door of…", arg: "door", t: (a, x) => `the door of the ${x} is closed , so the ${a} opens the door of the ${x} .` },
  { id: "needkey", label: "Say a door is locked…", arg: "door", t: (a, x) => `the door of the ${x} is locked , so the ${a} needs the key .` },
  { id: "unlock", label: "Unlock the door of…", arg: "door", t: (a, x) => `the door of the ${x} is locked , so the ${a} opens the door of the ${x} with the key .` },
  { id: "take", label: "Take…", arg: "thing", t: (a, x) => `the ${a} takes the ${x} .` },
  { id: "search", label: "Search for…", arg: "thing", t: (a, x) => `search : where is the ${x} ?` },
  { id: "choose", label: "Choose…", arg: "item", prop: true, t: (a, x, y) => `the ${a} wants the ${x} because the ${x} is ${y} .` },
  { id: "check", label: "Say it has…", arg: "thing", t: (a, x) => `the ${a} has the ${x} , so the goal is done .` },
  { id: "done", label: "Done", arg: null, t: () => "done ." },
];
const ARGS = { place: ["Place", () => D.places], door: ["Place", () => D.door_places], thing: ["Thing", () => [...D.items, "key"]], item: ["Thing", () => D.items] };

function renderBuilder(keep = true) {
  const p = problem();
  const acts = ACTIONS.filter((a) => !a.prop || p.prop);
  const cur = keep ? $("#action").value : "";
  $("#action").innerHTML = acts.map((a) => `<option value="${a.id}">${a.label}</option>`).join("");
  if (acts.some((a) => a.id === cur)) $("#action").value = cur;
  const a = ACTIONS.find((x) => x.id === $("#action").value);
  $("#arg1-wrap").hidden = !a.arg;
  if (a.arg) {
    const prev = $("#arg1").value;
    $("#arg1-label").textContent = ARGS[a.arg][0];
    $("#arg1").innerHTML = ARGS[a.arg][1]().map((w) => `<option value="${w}">${esc(sk(w))}</option>`).join("");
    if ([...$("#arg1").options].some((o) => o.value === prev)) $("#arg1").value = prev;
  }
  $("#arg2-wrap").hidden = !a.prop;
  if (a.prop) {
    const prev = $("#arg2").value;
    $("#arg2").innerHTML = D.props.map((w) => `<option value="${w}">${esc(sk(w))}</option>`).join("");
    if (prev) $("#arg2").value = prev;
  }
  $("#preview").textContent = sk(currentSentence());
}

function currentSentence() {
  const a = ACTIONS.find((x) => x.id === $("#action").value);
  return a.t(problem().agent, $("#arg1").value, $("#arg2").value);
}

function renderBench() {
  renderSkins();
  renderProblem();
  renderBuilder();
  renderPlan();
}

// ---------------------------------------------------------------- results

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;

function renderDots() {
  let html = `<div></div>${TESTS.map(([, l]) => `<div class="col-h">${l}</div>`).join("")}`;
  for (const [k, m] of Object.entries(D.models)) {
    html += `<div class="row-h">${MODELS[k].name}<small>${MODELS[k].note}</small></div>`;
    for (const [t, label] of TESTS) {
      const vals = m.seeds.map((s) => s[t]);
      const mu = mean(vals);
      const dots = vals.map((v, i) => `<circle cx="${(v * 100).toFixed(1)}%" cy="${12 + (i % 2 ? 5 : -5)}" r="4.5" fill="var(--ink)" fill-opacity="0.55"><title>seed ${m.seeds[i].seed}: ${Math.round(v * 100)}%</title></circle>`).join("");
      const x = Math.min(Math.max(mu * 100, 2), 98);
      html += `<div class="cell" data-label="${label}"><svg role="img" aria-label="${label}: mean ${Math.round(mu * 100)}%, seeds ${vals.map((v) => Math.round(v * 100) + "%").join(", ")}">
        <line x1="0" x2="100%" y1="12" y2="12" stroke="var(--rule)" stroke-width="1"/>
        <line x1="${(mu * 100).toFixed(1)}%" x2="${(mu * 100).toFixed(1)}%" y1="0" y2="24" stroke="var(--pass)" stroke-width="3"/>
        ${dots}
        <text x="${x}%" y="42" text-anchor="${mu > 0.85 ? "end" : mu < 0.15 ? "start" : "middle"}" class="mean-label" fill="var(--ink)">${Math.round(mu * 100)}%</text>
      </svg></div>`;
    }
  }
  $("#dots").innerHTML = html;
}

function renderBars() {
  const rows = Object.entries(D.models).map(([k, m]) => {
    let book = 0, garb = 0, other = 0;
    for (const [why, n] of Object.entries(m.fails)) {
      if (BOOKKEEPING.has(why)) book += n; else if (why === "garbled") garb += n; else other += n;
    }
    return { k, m, book, garb, other, total: book + garb + other };
  });
  const max = Math.max(...rows.map((r) => r.total));
  $("#bars").innerHTML = rows.map((r) => {
    const w = (n) => `${(100 * n / max).toFixed(2)}%`;
    const detail = Object.entries(r.m.fails).sort((a, b) => b[1] - a[1]).map(([why, n]) => `${why} ${n}`).join(", ");
    return `<div class="bar-row"><span class="name">${MODELS[r.k].name}, ${MODELS[r.k].note}</span>
      <div class="bar" role="img" aria-label="${r.book} bookkeeping, ${r.garb} garbled, ${r.other} other">
        <span class="book" style="width:${w(r.book)}"></span><span class="garb" style="width:${w(r.garb)}"></span><span class="other" style="width:${w(r.other)}"></span></div>
      <span class="total">${r.book}</span>
      <span class="bar-detail">${esc(detail)}</span></div>`;
  }).join("") + `<div class="bar-key"><span><i style="background:var(--syntax)"></i>Bookkeeping (the number on the right)</span>
    <span><i style="background:var(--wrong)"></i>Garbled sentence</span><span><i style="background:var(--ink-soft)"></i>Other</span></div>`;
}

function renderReadout() {
  const te = D.models["taught-ends"], tv = D.models["taught-every"];
  const cell = (v, i) => {
    const cls = v >= 0.9 ? "high" : v < CHANCE[i] + 0.15 ? "low" : "";
    return `<td class="${cls}">${Math.round(v * 100)}%</td>`;
  };
  $("#readout").innerHTML = `<thead><tr><th>Slot</th><th>Sentence-end slots,<br>plan skins</th><th>Sentence-end slots,<br>farm and space</th>
    <th>Every-word slots,<br>plan skins</th><th>Every-word slots,<br>farm and space</th><th>Chance</th></tr></thead><tbody>${
    SLOT_NAMES.map((n, i) => `<tr><td>${n}</td>${cell(te.slots_seen[i], i)}${cell(te.slots_unseen[i], i)}${cell(tv.slots_seen[i], i)}${cell(tv.slots_unseen[i], i)}<td>${Math.round(CHANCE[i] * 100)}%</td></tr>`).join("")
  }</tbody>`;
}

// ---------------------------------------------------------------- one problem

let oneMode = "messy";
function renderOne() {
  const p = D.problems.find((x) => x.id === D.sample.problem_id);
  const facts = p.facts.join(" ") + " " + p.plan[0].text;
  $("#one-problem").textContent = (oneMode === "messy" ? facts.replace(/ \./g, "") : facts) + " plan :";
  $("#one-list").innerHTML = Object.keys(MODELS).map((k) => {
    const text = D.sample.plans[k][oneMode];
    const sents = text.split(/(?<=[.?]) /).map((s) => s.trim()).filter(Boolean);
    const sim = new Sim(p, "home", S, places());
    const items = [];
    for (const s of sents) {
      if (s.startsWith("result :")) { items.push(`<li class="result">${esc(s)}</li>`); continue; }
      sim.step(s.split(" "));
      if (sim.status === "fail") { items.push(`<li class="fail">${esc(s)}<span class="why">${esc(sim.why)}: ${esc(WHY[sim.why] || "")}</span></li>`); break; }
      items.push(`<li>${esc(s)}</li>`);
      if (sim.status === "ok") break;
    }
    if (sim.status === "ok") items.push(`<li class="won">Goal reached.</li>`);
    return `<div class="one-item"><h3>${MODELS[k].name}<small>${MODELS[k].note}</small></h3><ol class="plan">${items.join("")}</ol></div>`;
  }).join("");
  document.querySelectorAll("#one-mode button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === oneMode)));
}

// ---------------------------------------------------------------- wiring

async function main() {
  D = await (await fetch("data/registers.json")).json();
  S = makeSkins(D);
  $("#problem").innerHTML = ["short", "long"].map((split) => `<optgroup label="${split === "short" ? "Short: 1–3 obstacles" : "Long: 4–5 obstacles"}">${
    D.problems.filter((p) => p.split === split).map((p) => `<option value="${p.id}">${esc(problemLabel(p))}</option>`).join("")}</optgroup>`).join("");
  $("#problem").value = st.pid;
  renderBench();
  renderDots();
  renderBars();
  renderReadout();
  renderOne();

  const reset = () => { st.plan = []; lastState = null; };
  $("#problem").addEventListener("change", (e) => { st.pid = e.target.value; reset(); renderBench(); });
  $("#another").addEventListener("click", () => {
    const others = D.problems.filter((p) => p.id !== st.pid);
    st.pid = others[Math.floor(Math.random() * others.length)].id;
    $("#problem").value = st.pid;
    reset();
    renderBench();
  });
  $("#skins").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-skin]");
    if (!b) return;
    st.skin = b.dataset.skin;
    lastState = null;
    renderBench();
  });
  $("#messy").addEventListener("change", (e) => { st.messy = e.target.checked; renderProblem(); });
  $("#hide-table").addEventListener("change", (e) => { st.hide = e.target.checked; renderPlan(); });
  $("#action").addEventListener("change", () => renderBuilder());
  $("#arg1").addEventListener("change", () => { $("#preview").textContent = sk(currentSentence()); });
  $("#arg2").addEventListener("change", () => { $("#preview").textContent = sk(currentSentence()); });
  $("#add").addEventListener("click", () => { st.plan.push(currentSentence()); renderPlan(); });
  $("#gold").addEventListener("click", () => {
    const gold = goldSentences(problem());
    if (st.plan.length < gold.length) st.plan.push(gold[st.plan.length]);
    renderPlan();
  });
  $("#undo").addEventListener("click", () => { st.plan.pop(); renderPlan(); });
  $("#restart").addEventListener("click", () => { reset(); renderPlan(); });
  $("#one-mode").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-mode]");
    if (b) { oneMode = b.dataset.mode; renderOne(); }
  });
}

main().catch((err) => {
  $("#plan").innerHTML = `<li class="fail">The page's data didn't load (${esc(err.message)}). Reload to try again.</li>`;
});
