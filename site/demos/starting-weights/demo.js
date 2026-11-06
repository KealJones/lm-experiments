import { INITS, WIDTH, rng, makeSpiral, makeNet, forward, lossAndGrads, applyGrads, layerStats } from "./net.js";

const $ = (id) => document.getElementById(id);
const state = { init: "scaled", act: "tanh", depth: 3, lr: 0.3, seed: 1, running: true };
const data = makeSpiral(rng(12345), 100);
const MAX_STEPS = 12000, STEPS_PER_FRAME = 6, GRID = 40, R = 1.2;
let net, step = 0, losses = [], last = null, blown = false, learnedAt = null, frame = 0;

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function seg(id, options, key) {
  const el = $(id);
  el.innerHTML = Object.entries(options)
    .map(([v, label]) => `<button type="button" data-v="${v}" aria-pressed="${v === state[key]}">${label}</button>`).join("");
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state[key] = b.dataset.v;
    el.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    restart();
  });
}

function restart() {
  net = makeNet({ depth: state.depth, act: state.act, init: state.init, rand: rng(state.seed) });
  step = 0; losses = []; blown = false; learnedAt = null;
  trainStep(false);
  state.running = !blown;
  setPlay();
  render(true);
}

function trainStep(update = true) {
  const s = lossAndGrads(net, data.X, data.Y, data.n);
  if (!Number.isFinite(s.loss)) { blown = true; state.running = false; setPlay(); return; }
  last = s;
  losses.push(s.loss);
  if (s.acc >= 0.97 && learnedAt === null) learnedAt = step;
  if (update) { applyGrads(net, s.grads, state.lr); step++; }
}

const fmt = (v) => {
  if (!Number.isFinite(v)) return "NaN";
  if (v === 0) return "0";
  const a = Math.abs(v);
  return a >= 1000 || a < 0.001 ? v.toExponential(1) : v.toFixed(a < 1 ? 3 : 2);
};
const logPct = (v, lo, hi) => (v > 0 ? Math.max(1.5, Math.min(100, ((Math.log10(v) - lo) / (hi - lo)) * 100)) : 0);

function renderLayers(stats) {
  $("layers").innerHTML = stats.map((s, i) => {
    const tone = s.spread === 0 || s.spread > 3 ? "bad" : s.spread < 0.15 ? "weak" : "";
    return `<div class="lrow" role="row">
      <span role="cell">${i + 1}</span>
      <span role="cell"><span class="num">${fmt(s.spread)}</span><span class="track"><span class="fill ${tone}" style="width:${logPct(s.spread, -6, 2)}%"></span></span></span>
      <span role="cell"><span class="num">${fmt(s.grad)}</span><span class="track"><span class="fill" style="width:${logPct(s.grad, -10, 1)}%"></span></span></span>
      <span role="cell" class="${s.unique === 1 ? "warn" : ""}">${s.unique} of ${WIDTH}</span>
      <span role="cell" class="${s.bad >= 0.5 ? "warn" : ""}">${Math.round(s.bad * 100)}% ${state.act === "relu" ? "dead" : "stuck"}</span>
    </div>`;
  }).join("");
}

function status(stats) {
  let t = "";
  if (blown) t = "The numbers overflowed to NaN. Training is over.";
  else if (stats.every((s) => s.grad === 0) && stats.every((s) => s.spread === 0) && state.init === "zero")
    t = "Every hidden gradient is exactly zero. Only the output bias can move, so it can never do better than a coin flip.";
  else if (state.act === "relu" && stats.some((s) => s.bad === 1))
    t = "A whole layer of ReLUs is dead: they output 0 for every point, so they get no gradient and never come back.";
  else if (stats.every((s) => s.unique === 1))
    t = `Symmetry never breaks. Every layer is really one neuron copied ${WIDTH} times.`;
  else if (stats[stats.length - 1].spread < 0.03)
    t = "The signal shrinks every layer until there's almost nothing left, so learning crawls.";
  else if (state.act === "tanh" && stats.some((s) => s.bad > 0.5))
    t = "Most neurons are pinned near ±1. A shallow net can still learn like this; add layers and it starts to stall.";
  if (learnedAt !== null && !blown) t = (t ? t + " " : "") + `Learned the spiral (97%) at step ${learnedAt}.`;
  $("status").textContent = t;
}

function setupCanvas(c) {
  const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
  const x = c.getContext("2d");
  x.setTransform(dpr, 0, 0, dpr, 0, 0);
  x.clearRect(0, 0, w, h);
  return [x, w, h];
}

let gridX = null;
function drawBoundary() {
  const [x, w, h] = setupCanvas($("boundary"));
  const a = css("--pass"), b = css("--wrong");
  if (!gridX) {
    gridX = new Float64Array(GRID * GRID * 2);
    for (let i = 0; i < GRID; i++) for (let j = 0; j < GRID; j++) {
      gridX[(i * GRID + j) * 2] = -R + (2 * R * (j + 0.5)) / GRID;
      gridX[(i * GRID + j) * 2 + 1] = R - (2 * R * (i + 0.5)) / GRID;
    }
  }
  if (!blown) {
    const acts = forward(net, gridX, GRID * GRID), z = acts[acts.length - 1], cw = w / GRID, ch = h / GRID;
    for (let i = 0; i < GRID; i++) for (let j = 0; j < GRID; j++) {
      const p = 1 / (1 + Math.exp(-z[i * GRID + j]));
      x.globalAlpha = Math.min(1, Math.abs(p - 0.5) * 2) * 0.3;
      x.fillStyle = p > 0.5 ? b : a;
      x.fillRect(j * cw, i * ch, cw + 0.5, ch + 0.5);
    }
  }
  x.globalAlpha = 1;
  for (let s = 0; s < data.n; s++) {
    x.beginPath();
    x.arc(((data.X[2 * s] + R) / (2 * R)) * w, ((R - data.X[2 * s + 1]) / (2 * R)) * h, 3.2, 0, 2 * Math.PI);
    x.fillStyle = data.Y[s] ? b : a;
    x.fill();
  }
}

function drawLoss() {
  const [x, w, h] = setupCanvas($("loss"));
  const ink = css("--ink"), soft = css("--ink-soft"), rule = css("--rule"), red = css("--syntax");
  const L = 36, B = 20, T = 6;
  const pts = losses.filter((v) => v > 0);
  let lo = Math.log10(Math.min(...pts, Math.LN2) || 1e-6), hi = Math.log10(Math.max(...pts, Math.LN2) || 1);
  lo = Math.max(lo, -6);
  if (hi - lo < 0.3) { hi += 0.15; lo -= 0.15; }
  const y = (v) => T + (h - T - B) * (1 - (Math.log10(Math.max(v, 1e-6)) - lo) / (hi - lo));
  x.strokeStyle = rule; x.lineWidth = 1;
  x.beginPath(); x.moveTo(L, T); x.lineTo(L, h - B); x.lineTo(w - 4, h - B); x.stroke();
  x.setLineDash([4, 3]); x.strokeStyle = red;
  x.beginPath(); x.moveTo(L, y(Math.LN2)); x.lineTo(w - 4, y(Math.LN2)); x.stroke(); x.setLineDash([]);
  x.font = "600 11px 'Barlow Semi Condensed', sans-serif";
  const yl = y(Math.LN2);
  x.fillStyle = red; x.fillText("coin flip", w - 54, yl < T + 14 ? yl + 13 : yl - 4);
  x.fillStyle = soft;
  x.fillText(fmt(10 ** hi), 0, T + 9); x.fillText(fmt(10 ** lo), 0, h - B);
  x.fillText(`step ${step}`, L, h - 4);
  if (losses.length < 2) return;
  const stride = Math.max(1, Math.floor(losses.length / 500));
  x.strokeStyle = ink; x.lineWidth = 1.6;
  x.beginPath();
  for (let i = 0; i < losses.length; i += stride) {
    const px = L + ((w - 4 - L) * i) / (losses.length - 1);
    i ? x.lineTo(px, y(losses[i])) : x.moveTo(px, y(losses[i]));
  }
  x.stroke();
}

function render(full) {
  const stats = last ? layerStats(net, last) : [];
  $("m-step").textContent = step.toLocaleString();
  $("m-loss").textContent = blown ? "NaN" : last ? fmt(last.loss) : "–";
  $("m-acc").textContent = last && !blown ? `${Math.round(last.acc * 100)}%` : "–";
  $("m-uniq").textContent = stats.length ? stats.map((s) => s.unique).join(" / ") : "–";
  renderLayers(stats);
  status(stats);
  drawLoss();
  if (full) drawBoundary();
}

function setPlay() {
  $("play").textContent = state.running ? "Pause" : step >= MAX_STEPS ? "Run again" : "Play";
}

function loop() {
  if (state.running && !blown) {
    for (let i = 0; i < STEPS_PER_FRAME && !blown; i++) trainStep();
    if (step >= MAX_STEPS) { state.running = false; setPlay(); }
  }
  frame++;
  render(frame % 3 === 0 || !state.running);
  requestAnimationFrame(loop);
}

seg("init", INITS, "init");
seg("act", { tanh: "tanh", relu: "ReLU" }, "act");
$("depth").addEventListener("input", (e) => { state.depth = +e.target.value; $("depth-out").textContent = state.depth; restart(); });
$("lr").addEventListener("input", (e) => { state.lr = +e.target.value; $("lr-out").textContent = state.lr.toFixed(2); });
$("play").addEventListener("click", () => {
  if (blown || step >= MAX_STEPS) return restart();
  state.running = !state.running;
  setPlay();
});
$("reroll").addEventListener("click", () => { state.seed = (Math.random() * 1e9) >>> 0; restart(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => render(true));
window.addEventListener("resize", () => render(true));

restart();
requestAnimationFrame(loop);
