// A 2-layer GPT-2 (width 128, 2 heads, 256 positions, GPT-2's 50,257-token vocab) that never trains.
// Same shape and same four fill recipes as experiments/random-weights/model.py. The random numbers come from this
// page's own generator, not PyTorch's, so each seed is a fresh draw of the same kind of model, not the exact
// weights the experiment recorded.

const V = 50257, D = 128, H = 2, HD = 64, T = 256, F = 512, L = 2;
let W = null; // weights

// ---------------------------------------------------------------- randomness

function rng(seed) {
  let s = (Math.imul(seed >>> 0, 0x9e3779b1) ^ 0x632be5ab) | 0;
  return () => {
    // splitmix32
    s = (s + 0x9e3779b9) | 0;
    let z = s;
    z = Math.imul(z ^ (z >>> 16), 0x85ebca6b);
    z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35);
    return ((z ^ (z >>> 16)) >>> 0) / 4294967296;
  };
}

function makeFill(init, seed) {
  const u = rng(seed);
  const normal = () => {
    let a = u();
    while (a === 0) a = u();
    return Math.sqrt(-2 * Math.log(a)) * Math.cos(2 * Math.PI * u());
  };
  // returns fn(kind, n): kind is "w" (weight), "proj" (residual projection), "bias", "lnw", "lnb"
  return (kind, n) => {
    const a = new Float32Array(n);
    if (init === "default") {
      if (kind === "bias" || kind === "lnb") return a;
      if (kind === "lnw") return a.fill(1);
      const std = kind === "proj" ? 0.02 / Math.sqrt(2 * L) : 0.02;
      for (let i = 0; i < n; i++) a[i] = normal() * std;
      return a;
    }
    if (init === "uniform") { for (let i = 0; i < n; i++) a[i] = u() * 2 - 1; return a; }
    const std = init === "normal1" ? 1 : 10;
    for (let i = 0; i < n; i++) a[i] = normal() * std;
    return a;
  };
}

function build(init, seed) {
  const fill = makeFill(init, seed);
  const w = { wte: fill("w", V * D), wpe: fill("w", T * D), layers: [] };
  for (let l = 0; l < L; l++) {
    w.layers.push({
      ln1w: fill("lnw", D), ln1b: fill("lnb", D),
      attnW: fill("w", D * 3 * D), attnB: fill("bias", 3 * D),
      projW: fill("proj", D * D), projB: fill("bias", D),
      ln2w: fill("lnw", D), ln2b: fill("lnb", D),
      fcW: fill("w", D * F), fcB: fill("bias", F),
      fc2W: fill("proj", F * D), fc2B: fill("bias", D),
    });
  }
  w.lnfw = fill("lnw", D);
  w.lnfb = fill("lnb", D);
  return w;
}

// ---------------------------------------------------------------- forward pass

function layerNorm(x, g, b) {
  let m = 0;
  for (let i = 0; i < D; i++) m += x[i];
  m /= D;
  let v = 0;
  for (let i = 0; i < D; i++) v += (x[i] - m) ** 2;
  const r = 1 / Math.sqrt(v / D + 1e-5);
  const y = new Float64Array(D);
  for (let i = 0; i < D; i++) y[i] = (x[i] - m) * r * g[i] + b[i];
  return y;
}

// x (n) @ W (n x m, row-major) + b
function matvec(x, Wt, b, n, m) {
  const y = new Float64Array(m);
  for (let j = 0; j < m; j++) y[j] = b[j];
  for (let i = 0; i < n; i++) {
    const xi = x[i];
    if (xi === 0) continue;
    const row = i * m;
    for (let j = 0; j < m; j++) y[j] += xi * Wt[row + j];
  }
  return y;
}

const gelu = (x) => 0.5 * x * (1 + Math.tanh(Math.sqrt(2 / Math.PI) * (x + 0.044715 * x ** 3)));

// final hidden states for every position
function hidden(ids) {
  const n = ids.length;
  let xs = ids.map((id, t) => {
    const x = new Float64Array(D);
    for (let i = 0; i < D; i++) x[i] = W.wte[id * D + i] + W.wpe[t * D + i];
    return x;
  });
  for (const ly of W.layers) {
    const qkv = xs.map((x) => matvec(layerNorm(x, ly.ln1w, ly.ln1b), ly.attnW, ly.attnB, D, 3 * D));
    xs = xs.map((x, t) => {
      const att = new Float64Array(D);
      for (let h = 0; h < H; h++) {
        const qo = h * HD, ko = D + h * HD, vo = 2 * D + h * HD;
        const s = new Float64Array(t + 1);
        let mx = -Infinity;
        for (let u = 0; u <= t; u++) {
          let d = 0;
          for (let i = 0; i < HD; i++) d += qkv[t][qo + i] * qkv[u][ko + i];
          s[u] = d / Math.sqrt(HD);
          if (s[u] > mx) mx = s[u];
        }
        let z = 0;
        for (let u = 0; u <= t; u++) { s[u] = Math.exp(s[u] - mx); z += s[u]; }
        for (let u = 0; u <= t; u++) {
          const p = s[u] / z;
          for (let i = 0; i < HD; i++) att[h * HD + i] += p * qkv[u][vo + i];
        }
      }
      const o = matvec(att, ly.projW, ly.projB, D, D);
      const y = new Float64Array(D);
      for (let i = 0; i < D; i++) y[i] = x[i] + o[i];
      const f = matvec(layerNorm(y, ly.ln2w, ly.ln2b), ly.fcW, ly.fcB, D, F).map(gelu);
      const m = matvec(f, ly.fc2W, ly.fc2B, F, D);
      for (let i = 0; i < D; i++) y[i] += m[i];
      return y;
    });
  }
  return xs.map((x) => layerNorm(x, W.lnfw, W.lnfb));
}

function logits(h) {
  const z = new Float64Array(V);
  for (let v = 0; v < V; v++) {
    let d = 0;
    const o = v * D;
    for (let i = 0; i < D; i++) d += h[i] * W.wte[o + i];
    z[v] = d;
  }
  return z;
}

function softmax(z) {
  let mx = -Infinity;
  for (const x of z) if (x > mx) mx = x;
  let s = 0;
  const p = new Float64Array(z.length);
  for (let i = 0; i < z.length; i++) { p[i] = Math.exp(z[i] - mx); s += p[i]; }
  for (let i = 0; i < z.length; i++) p[i] /= s;
  return { p, logZ: mx + Math.log(s) };
}

function top(p, k) {
  const best = [];
  for (let i = 0; i < p.length; i++) {
    if (best.length < k || p[i] > best[best.length - 1][1]) {
      best.push([i, p[i]]);
      best.sort((a, b) => b[1] - a[1]);
      if (best.length > k) best.pop();
    }
  }
  return best.map(([id, prob]) => ({ id, prob }));
}

// ---------------------------------------------------------------- messages

self.onmessage = ({ data: msg }) => {
  try {
    if (msg.type === "build") {
      const t0 = performance.now();
      W = build(msg.init, msg.seed);
      self.postMessage({ type: "built", ms: performance.now() - t0 });
    } else if (msg.type === "generate") {
      // first-step probabilities, then 20 sampled tokens and 12 greedy ones, like the experiment
      const r = rng(msg.seed * 7919 + 17);
      const first = softmax(logits(hidden(msg.ids).at(-1))).p;
      const firstTop = top(first, 5);
      const run = (n, sample) => {
        const ids = msg.ids.slice(), out = [];
        for (let k = 0; k < n && ids.length < T; k++) {
          const { p } = softmax(logits(hidden(ids).at(-1)));
          let next;
          if (sample) {
            let x = r(), i = 0;
            while (i < V - 1 && (x -= p[i]) > 0) i++;
            next = i;
          } else next = top(p, 1)[0].id;
          ids.push(next);
          out.push(next);
          self.postMessage({ type: "token", sample, id: next });
        }
        return out;
      };
      const sampled = run(20, true);
      const greedy = run(12, false);
      self.postMessage({ type: "generated", firstTop, sampled, greedy });
    } else if (msg.type === "score") {
      const ids = msg.ids;
      const hs = hidden(ids);
      let total = 0;
      const top1 = new Set();
      for (let t = 0; t < ids.length - 1; t++) {
        const z = logits(hs[t]);
        const { logZ } = softmax(z);
        total += logZ - z[ids[t + 1]];
        let bi = 0;
        for (let v = 1; v < V; v++) if (z[v] > z[bi]) bi = v;
        top1.add(bi);
        if (t % 16 === 15) self.postMessage({ type: "progress", done: t + 1, of: ids.length - 1 });
      }
      self.postMessage({ type: "scored", loss: total / (ids.length - 1), distinct: top1.size });
    }
  } catch (e) {
    self.postMessage({ type: "error", message: String(e && e.message || e) });
  }
};
