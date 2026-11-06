const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fmt = (n) => n.toLocaleString("en-US");
// just enough markdown for the replies: bold, inline code, headings, fenced code
const md = (s) => esc(s)
  .replace(/```[a-z]*\n([\s\S]*?)```/g, (_, c) => `<code class="blk">${c}</code>`)
  .replace(/^#{1,4} (.+)$/gm, "<strong>$1</strong>")
  .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  .replace(/`([^`\n]+)`/g, "<code>$1</code>");

const KIND = { messy: "Messy, with a trap", clean: "Clean baseline", last: "Only the last message matters" };
const CTX = { full: "the full history", opus: "the Opus packet", sonnet: "the Sonnet packet", haiku: "the Haiku packet" };
const WHO = { opus: "Opus", haiku: "Haiku" };

let D;
const st = { test: 1, ctx: "opus", who: "opus", noisy: "N1" };

const test = () => D.tests.find((t) => t.n === st.test);
const run = (t, ctx, who) => t.runs.find((r) => r.context === ctx && r.answerer === who);

// ---------------------------------------------------------------- bench

function setSeg(id, value, avail) {
  for (const b of $$(`#${id} button`)) {
    const ok = avail ? avail(b.dataset.v) : true;
    b.disabled = !ok;
    b.setAttribute("aria-pressed", String(b.dataset.v === value));
  }
}

function fixChoice(t) {
  // keep the chosen pair if it was run, else move to the nearest one that was
  if (run(t, st.ctx, st.who)) return;
  if (run(t, st.ctx, "opus")) { st.who = "opus"; return; }
  st.ctx = "opus"; st.who = run(t, "opus", st.who) ? st.who : "opus";
}

function renderBench() {
  const t = test();
  fixChoice(t);
  $("#trap").innerHTML = `<strong>${esc(KIND[t.kind])}.</strong> ${esc(t.trap)}`;
  setSeg("ctx", st.ctx, (v) => t.runs.some((r) => r.context === v));
  setSeg("who", st.who, (v) => !!run(t, st.ctx, v));

  // meter
  const words = st.ctx === "full" ? t.conv_words : t.packets[st.ctx].words;
  $("#meter-fill").style.width = `${Math.max(1.5, (100 * words) / t.conv_words)}%`;
  $("#meter-lab").innerHTML = st.ctx === "full"
    ? `<strong>${fmt(t.conv_words)} words</strong>: the whole conversation, ${t.turns.length} turns.`
    : `<strong>${fmt(words)} words</strong>: ${Math.round((100 * words) / t.conv_words)}% of the ${fmt(t.conv_words)}-word conversation.`;

  // facts + what it saw
  const facts = $("#facts");
  const saw = $("#saw");
  if (st.ctx === "full") {
    $("#saw-h").textContent = "What it saw: the whole conversation";
    facts.innerHTML = t.facts.map((f) => `<li class="buried">${esc(f)}</li>`).join("") +
      `<li class="buried">all in there, somewhere</li>`;
    saw.className = "saw";
    saw.innerHTML = t.turns.map(([w, x]) => `<div class="t ${w}"><span class="w">${w === "U" ? "U" : "A"}</span><span class="x">${esc(x)}</span></div>`).join("");
  } else {
    const p = t.packets[st.ctx];
    $("#saw-h").textContent = `What it saw: ${CTX[st.ctx]}`;
    facts.innerHTML = t.facts.map((f, i) => `<li class="${p.facts[i] ? "have" : "miss"}">${esc(f)}</li>`).join("");
    saw.className = "saw packet";
    saw.textContent = p.text;
  }
  saw.scrollTop = 0;

  $("#newmsg").textContent = t.question;
  const r = run(t, st.ctx, st.who);
  const reply = $("#reply");
  reply.className = "reply";
  reply.innerHTML = md(r.answer);
  reply.scrollTop = 0;
  const lists = [r.missed.length ? `Missed: ${r.missed.join("; ")}` : "", r.traps.length ? `Traps hit: ${r.traps.join("; ")}` : ""]
    .filter(Boolean).map((s) => `<p class="lst">${esc(s)}</p>`).join("");
  $("#grade").innerHTML = `<p class="verdict ${r.pass ? "pass" : "fail"}">${r.pass ? "Pass" : "Fail"}, ${r.score}/10</p>
    <p>${esc(r.note)}</p>${lists}`;
  $("#key").textContent = t.key;
}

function initBench() {
  const sel = $("#test");
  for (const kind of ["messy", "clean", "last"]) {
    const g = document.createElement("optgroup");
    g.label = KIND[kind];
    for (const t of D.tests.filter((x) => x.kind === kind)) {
      const o = document.createElement("option");
      o.value = t.n; o.textContent = `${t.n}. ${t.title}`;
      g.append(o);
    }
    sel.append(g);
  }
  sel.addEventListener("change", () => { st.test = +sel.value; renderBench(); });
  $("#ctx").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b || b.disabled) return; st.ctx = b.dataset.v; renderBench(); });
  $("#who").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b || b.disabled) return; st.who = b.dataset.v; renderBench(); });
  for (const b of $$(".jump")) {
    b.addEventListener("click", () => {
      st.test = +b.dataset.test; st.ctx = b.dataset.ctx; st.who = b.dataset.who;
      sel.value = st.test; renderBench();
      $("#play-h").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }
  renderBench();
}

// ---------------------------------------------------------------- score table

function renderScore() {
  const rows = [
    ["opus", "full", "Opus, full history"], ["opus", "opus", "Opus, Opus packet"], ["opus", "sonnet", "Opus, Sonnet packet"],
    ["opus", "haiku", "Opus, Haiku packet"], ["haiku", "full", "Haiku, full history"], ["haiku", "opus", "Haiku, Opus packet"],
  ];
  const groups = [["messy", "Messy 1–8"], ["clean", "Clean 9–12"], ["last", "Last message 13–16"]];
  const main = D.tests.filter((t) => t.kind !== "last");
  const avgWords = (ctx) => Math.round(main.reduce((s, t) => s + (ctx === "full" ? t.conv_words : t.packets[ctx].words), 0) / main.length);
  let h = `<thead><tr><th>Who answers, from what</th><th>Words seen</th>${groups.map(([, l]) => `<th>${l}</th>`).join("")}<th>All of 1–12</th></tr></thead><tbody>`;
  for (const [who, ctx, label] of rows) {
    const cell = (tests) => {
      const rs = tests.map((t) => run(t, ctx, who)).filter(Boolean);
      if (!rs.length) return `<td class="dim">not run</td>`;
      const p = rs.filter((r) => r.pass).length;
      const avg = rs.reduce((s, r) => s + r.score, 0) / rs.length;
      return `<td><span class="${p === rs.length ? "v-pass" : "v-fail"}">${p}/${rs.length}</span>, ${avg.toFixed(1)}</td>`;
    };
    h += `<tr${who === "opus" && ctx === "opus" ? ' class="best"' : ""}><td>${label}</td><td>${fmt(avgWords(ctx))}</td>` +
      groups.map(([k]) => cell(D.tests.filter((t) => t.kind === k))).join("") + cell(main) + "</tr>";
  }
  $("#score").innerHTML = h + "</tbody>";
}

// ---------------------------------------------------------------- noisy

function renderNoisy() {
  const c = D.noisy.find((x) => x.id === st.noisy);
  setSeg("case", st.noisy);
  const TAG = { good: "Source", wrong: "Wrong", junk: "Junk" };
  $("#lines").innerHTML = c.lines.map((l) => `<li class="${l.kind}"><span class="tag">${TAG[l.kind]}</span><span>${esc(l.text)}</span></li>`).join("");
  $("#nmsg").textContent = c.message;
  $("#nkey").textContent = `Key: ${c.key}`;
  $("#nreplies").innerHTML = `<h3 class="col-h">The replies</h3>` + ["opus", "sonnet", "haiku"].map((m) => {
    const r = c.replies[m];
    const name = m[0].toUpperCase() + m.slice(1);
    return `<div class="nr"><div class="nr-head"><span>${name}</span><span class="${r.pass ? "v-pass" : "v-fail"}">${r.pass ? "Pass" : "Fail"}, ${r.score}/10</span></div>
      <div class="nr-text">${md(r.text)}</div><div class="nr-note">${esc(r.note)}</div></div>`;
  }).join("");
}

function initNoisy() {
  const seg = $("#case");
  seg.innerHTML = D.noisy.map((c) => `<button type="button" data-v="${c.id}">${c.id}: ${esc(c.message)}</button>`).join("");
  seg.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; st.noisy = b.dataset.v; renderNoisy(); });
  renderNoisy();
}

// ---------------------------------------------------------------- go

D = await (await fetch("data/packets.json")).json();
initBench();
renderScore();
initNoisy();
