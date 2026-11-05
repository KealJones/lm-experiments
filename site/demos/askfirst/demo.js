const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const pct = (x) => `${Math.round(100 * x)}%`;

const TOPIC_LABEL = { who: "Who's coming", from: "Leaving from", budget: "Budget", when: "When", trip_why: "Why they want to go" };
const PART_LABEL = {
  found_need: "found the real need", adapted: "adapted the gift to it", connect: "suggested staying in touch",
  no_wrong_place: "sent it to the right state", in_budget: "stayed in budget", nothing_forbidden: "nothing they can't eat",
  fits_kitchen: "fits the kitchen", safety_note: "made the safety point", fix: "fixed the actual error",
  found_who: "found out who's coming", found_why: "found out why", fits_who: "suits who's coming", fits_why: "suits why they're going",
  has_code: "wrote code", reverses: "reverses every other row",
};
const STEP_LABEL = { think: "Thinks", ask: "Asks", reply: "Person", fact: "Notes down", search: "Searches", result: "Search result",
  check: "Checks", notes: "Its notes", answer: "Answers", text: "Answers" };
const DUNNO = "idk what you mean lol";

let D;

// ---------------------------------------------------------------- you be the model
// A port of scenarios.Person: it answers only the topics a question mentions, in a fixed order, once each.

const play = { trip: 0, revealed: new Set(), asked: 0 };

function personReply(q) {
  const t = D.trips[play.trip];
  const ql = q.toLowerCase();
  const parts = [];
  for (const topic of t.order) {
    if (play.revealed.has(topic)) continue;
    const words = D.topic_words[topic];
    if (!words.some((w) => ql.includes(w))) continue;
    parts.push(t.topics[topic]);
    play.revealed.add(topic);
  }
  if (!parts.length) return DUNNO;
  return parts.map((p) => (/[.?!]$/.test(p.trimEnd()) ? p : p + ".")).join(" ");
}

function gradeTrip(answer) {
  const t = D.trips[play.trip];
  const a = answer.toLowerCase();
  const money = [...answer.matchAll(/\$\s?(\d{1,4})/g)].map((m) => Number(m[1]));
  const parts = {
    found_who: play.revealed.has("who"), found_why: play.revealed.has("trip_why"),
    fits_who: t.who_words.some((k) => a.includes(k)), fits_why: t.why_words.some((k) => a.includes(k)),
    in_budget: !money.some((m) => m > t.budget),
  };
  return { ok: Object.values(parts).every(Boolean), parts };
}

function renderHidden() {
  const t = D.trips[play.trip];
  $("#hidden-list").innerHTML = t.order.map((k) => {
    const found = play.revealed.has(k);
    const key = k === "who" || k === "trip_why";
    return `<li class="${found ? "found" : ""}${key ? " key" : ""}"><span class="topic">${TOPIC_LABEL[k]}</span>
      <span class="val">${found ? esc(t.topics[k]) : "not found yet"}</span></li>`;
  }).join("");
}

function addMsg(who, text, cls = "") {
  const chat = $("#chat");
  chat.insertAdjacentHTML("beforeend", `<div class="msg ${who} ${cls}"><span class="who">${who === "you" ? "You" : "Them"}</span>${esc(text)}</div>`);
  chat.scrollTop = chat.scrollHeight;
}

function resetPlay() {
  play.revealed = new Set();
  play.asked = 0;
  $("#chat").innerHTML = "";
  addMsg("them", D.trips[play.trip].request);
  $("#grade").innerHTML = "";
  $("#answer-input").value = "";
  renderHidden();
  renderModelTurn();
}

function renderModelTurn() {
  const ep = D.families.find((f) => f.id === "trip (unseen)").episodes.patched[play.trip];
  const turns = ep.steps.filter((s) => s.tag === "ask" || s.tag === "reply" || s.tag === "answer");
  $("#model-turn").innerHTML = turns.map((s) => {
    if (s.tag === "reply") return `<div class="msg them${s.body === DUNNO ? " dunno" : ""}"><span class="who">Them</span>${esc(s.body)}</div>`;
    return `<div class="msg you"><span class="who">Qwen3 0.6B, patched${s.tag === "answer" ? ", final answer" : ""}</span>${esc(s.body)}</div>`;
  }).join("") + `<p class="v-fail" style="margin:0;font:700 1.05rem var(--display)">Failed: it never found out who's coming or why.</p>`;
}

// ---------------------------------------------------------------- score

const NOTHING_HIDDEN = new Set(["given", "keal-coeliac", "keal-boustrophedon"]); // the message already says everything

function renderScore() {
  const head = `<thead><tr><th>Kind of request</th><th>Runs</th><th>Untouched<br>passes</th><th>Patched<br>passes</th>
    <th>Untouched<br>asks</th><th>Patched<br>asks</th><th>Patched finds<br>the real need</th></tr></thead>`;
  const body = D.families.map((f) => `<tr class="${f.id === "trip (unseen)" ? "trip" : ""}"><td>${esc(f.label)}</td><td>${f.n}</td>
    <td>${pct(f.untouched.success)}</td><td class="${f.patched.success === 1 ? "v-pass" : f.patched.success === 0 ? "v-fail" : ""}">${pct(f.patched.success)}</td>
    <td>${pct(f.untouched.asked)}</td><td>${pct(f.patched.asked)}</td>
    <td>${NOTHING_HIDDEN.has(f.id) ? `<span class="na" title="Nothing is held back, so there's nothing to find">n/a</span>` : pct(f.patched.found_need)}</td></tr>`).join("");
  $("#score").innerHTML = head + `<tbody>${body}</tbody>`;
}

// ---------------------------------------------------------------- replay

const rp = { fam: "trip (unseen)", arm: "patched", ep: 0, shown: 1, gold: false };

function episode() {
  return D.families.find((f) => f.id === rp.fam).episodes[rp.arm][rp.ep];
}

function stepHTML(s, cls = "") {
  const dunno = s.tag === "reply" && s.body === DUNNO ? " dunno" : "";
  const label = STEP_LABEL[s.tag] + (s.key ? ` (${esc(s.key)})` : "");
  return `<div class="step ${s.tag}${dunno} ${cls}"><span class="lab">${label}</span><div class="body">${esc(s.body)}</div></div>`;
}

function renderReplay() {
  const e = episode();
  const goldBodies = new Set((e.gold || []).map((s) => s.tag + "|" + s.body));
  const showGold = rp.gold && e.gold;
  const req = { tag: "reply", body: e.request };
  const steps = e.steps.slice(0, rp.shown);
  $("#steps").innerHTML = `<div class="step reply"><span class="lab">Request</span><div class="body">${esc(e.request)}</div></div>` +
    steps.map((s) => stepHTML(s, showGold && goldBodies.has(s.tag + "|" + s.body) && !["reply", "result", "notes"].includes(s.tag) ? "match" : "")).join("");
  void req;
  const done = rp.shown >= e.steps.length;
  $("#next").disabled = done;
  $("#all").disabled = done;
  const out = $("#outcome");
  out.hidden = !done;
  if (done) {
    const missed = Object.entries(e.parts).filter(([, v]) => !v).map(([k]) => PART_LABEL[k] || k);
    out.innerHTML = e.ok ? `<span class="v-pass">Passed the checker.</span>`
      : `<span class="v-fail">Failed the checker.</span><span class="parts">Missed: ${esc(missed.join(", "))}.</span>`;
  }

  $("#gold-toggle-wrap").hidden = !e.gold;
  $(".replay").classList.toggle("with-gold", !!showGold);
  $("#gold-col").hidden = !showGold;
  if (showGold) {
    $("#gold-head").innerHTML = `Training-style conversation for the same request. The model's version is
      <strong>${Math.round(100 * e.same_as_gold)}%</strong> the same text${e.same_as_gold === 1 ? ", character for character" : ""}.`;
    $("#gold").innerHTML = e.gold.map((s) => stepHTML(s)).join("");
  }
  $("#shots-note").hidden = rp.arm !== "untouched";
}

function renderEpPicker() {
  const f = D.families.find((x) => x.id === rp.fam);
  $("#ep").innerHTML = f.episodes[rp.arm].map((e, i) =>
    `<option value="${i}"${i === rp.ep ? " selected" : ""}>${i + 1}: ${e.ok ? "passed" : "failed"}</option>`).join("");
}

// ---------------------------------------------------------------- wiring

async function main() {
  D = await (await fetch("data/askfirst.json")).json();

  $("#trip").innerHTML = D.trips.map((t, i) => `<option value="${i}">${i + 1}: “${esc(t.request)}”</option>`).join("");
  resetPlay();
  $("#trip").addEventListener("change", (e) => { play.trip = Number(e.target.value); resetPlay(); });
  $("#ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#ask-input").value.trim();
    if (!q) return;
    addMsg("you", q);
    const r = personReply(q);
    addMsg("them", r, r === DUNNO ? "dunno" : "");
    $("#ask-input").value = "";
    renderHidden();
  });
  $("#answer-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const a = $("#answer-input").value.trim();
    if (!a) { $("#grade").innerHTML = `<p class="verdict v-part">Write a suggestion first, then grade it.</p>`; return; }
    const g = gradeTrip(a);
    $("#grade").innerHTML = `<p class="verdict ${g.ok ? "v-pass" : "v-fail"}">${g.ok ? "Passed. That's more than the model managed." : "Not yet."}</p>
      <ul class="checks">${Object.entries(g.parts).map(([k, v]) => `<li class="${v ? "ok" : "no"}">${PART_LABEL[k]}</li>`).join("")}</ul>`;
  });
  $("#show-model").addEventListener("click", (e) => {
    const open = $("#model-turn").hidden;
    $("#model-turn").hidden = !open;
    e.currentTarget.setAttribute("aria-expanded", String(open));
    e.currentTarget.textContent = open ? "Hide what the model asked" : "Show what the trained model asked";
  });

  renderScore();

  $("#fam").innerHTML = D.families.map((f) => `<option value="${esc(f.id)}"${f.id === rp.fam ? " selected" : ""}>${esc(f.label)}</option>`).join("");
  renderEpPicker();
  renderReplay();
  const reset = () => { rp.shown = 1; renderEpPicker(); renderReplay(); };
  $("#fam").addEventListener("change", (e) => { rp.fam = e.target.value; rp.ep = 0; reset(); });
  $("#arm").addEventListener("change", (e) => { rp.arm = e.target.value; rp.ep = 0; reset(); });
  $("#ep").addEventListener("change", (e) => { rp.ep = Number(e.target.value); rp.shown = 1; renderReplay(); });
  $("#next").addEventListener("click", () => { rp.shown++; renderReplay(); });
  $("#all").addEventListener("click", () => { rp.shown = episode().steps.length; renderReplay(); });
  $("#restart").addEventListener("click", () => { rp.shown = 1; renderReplay(); });
  $("#gold-toggle").addEventListener("change", (e) => { rp.gold = e.target.checked; if (rp.gold) rp.shown = episode().steps.length; renderReplay(); });

  // reciting numbers, from the data
  const sims = D.families.flatMap((f) => f.episodes.patched.map((e) => e.same_as_gold)).filter((x) => typeof x === "number");
  $("#sim-range").textContent = `${Math.floor(100 * Math.min(...sims))}–${Math.round(100 * Math.max(...sims))}%`;
  $("#sim-exact").textContent = `${sims.filter((x) => x === 1).length} of the ${sims.length}`;

  $("#ppl-a").textContent = D.ppl.untouched.toFixed(0);
  $("#ppl-b").textContent = D.ppl.patch_on.toFixed(0);
  $("#ppl-c").textContent = D.ppl.patch_off.toFixed(0);
  $("#plain-a").textContent = D.plain_chat["keal-mom"].untouched;
  $("#plain-b").textContent = D.plain_chat["keal-mom"].patched;
}

main().catch((err) => {
  $("#chat").innerHTML = `<p class="v-fail">The page's data didn't load (${esc(err.message)}). Reload to try again.</p>`;
});
