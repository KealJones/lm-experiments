// A tiny fully connected network with hand-written backprop, so nothing is hidden behind a library.
// 2 inputs -> `depth` hidden layers of WIDTH neurons -> 1 logit. Binary cross-entropy, full-batch gradient descent.
// Checked against finite differences by test_net.mjs.

export const WIDTH = 12;

export const INITS = {
  zero: "All zeros",
  same: "All the same (0.5)",
  tiny: "Tiny random (std 0.01)",
  scaled: "Scaled random (Xavier / He)",
  huge: "Huge random (std 3)",
};

// mulberry32: small, fast, seedable, so a seed is a reproducible starting point
export function rng(seed) {
  let a = seed >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  next.normal = () => {
    let u = 0, v = 0;
    while (!u) u = next();
    while (!v) v = next();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  return next;
}

// Two interleaved spiral arms, about two-thirds of a turn each.
export function makeSpiral(rand, perClass = 100) {
  const xs = [], ys = [];
  for (let c = 0; c < 2; c++) {
    for (let i = 0; i < perClass; i++) {
      const r = 0.15 + 0.85 * i / perClass;
      const t = 4 * i / perClass + c * Math.PI + rand.normal() * 0.15;
      xs.push(r * Math.sin(t), r * Math.cos(t));
      ys.push(c);
    }
  }
  return { X: new Float64Array(xs), Y: new Float64Array(ys), n: ys.length };
}

// The gain for "scaled": 5/3 for tanh (Xavier-style, PyTorch's tanh gain), sqrt(2) for ReLU (He / Kaiming).
export function makeNet({ depth = 3, act = "tanh", init = "scaled", rand }) {
  const dims = [2, ...Array(depth).fill(WIDTH), 1];
  const layers = [];
  for (let l = 0; l < dims.length - 1; l++) {
    const L = { in: dims[l], out: dims[l + 1] };
    L.W = new Float64Array(L.in * L.out);
    L.b = new Float64Array(L.out);
    const isOut = l === dims.length - 2;
    const gain = isOut ? 1 : act === "relu" ? Math.SQRT2 : 5 / 3;
    for (let i = 0; i < L.W.length; i++) {
      L.W[i] =
        init === "zero" ? 0 :
        init === "same" ? 0.5 :
        init === "tiny" ? rand.normal() * 0.01 :
        init === "huge" ? rand.normal() * 3 :
        rand.normal() * gain / Math.sqrt(L.in);
    }
    layers.push(L);
  }
  return { layers, act, depth };
}

// Returns the post-activation output of every layer; acts[0] is the input, the last is the logit.
export function forward(net, X, m) {
  const acts = [X];
  let a = X;
  net.layers.forEach((L, l) => {
    const z = new Float64Array(m * L.out);
    for (let s = 0; s < m; s++) {
      const ao = s * L.in, zo = s * L.out;
      for (let j = 0; j < L.out; j++) {
        let sum = L.b[j];
        const wo = j * L.in;
        for (let k = 0; k < L.in; k++) sum += L.W[wo + k] * a[ao + k];
        z[zo + j] = sum;
      }
    }
    if (l < net.layers.length - 1) {
      for (let i = 0; i < z.length; i++) z[i] = net.act === "relu" ? (z[i] > 0 ? z[i] : 0) : Math.tanh(z[i]);
    }
    acts.push(z);
    a = z;
  });
  return acts;
}

export function lossAndGrads(net, X, Y, n) {
  const acts = forward(net, X, n);
  const out = acts[acts.length - 1];
  let loss = 0, correct = 0;
  let dz = new Float64Array(n);
  for (let s = 0; s < n; s++) {
    const z = out[s], y = Y[s];
    loss += Math.max(z, 0) - z * y + Math.log1p(Math.exp(-Math.abs(z)));  // stable BCE with logits
    const p = 1 / (1 + Math.exp(-z));
    dz[s] = (p - y) / n;
    if ((p > 0.5) === (y === 1)) correct++;
  }
  loss /= n;

  const grads = [];
  for (let l = net.layers.length - 1; l >= 0; l--) {
    const L = net.layers[l], aIn = acts[l];
    const gW = new Float64Array(L.W.length), gb = new Float64Array(L.out);
    for (let s = 0; s < n; s++) {
      for (let j = 0; j < L.out; j++) {
        const d = dz[s * L.out + j];
        if (d === 0) continue;
        gb[j] += d;
        const wo = j * L.in, ao = s * L.in;
        for (let k = 0; k < L.in; k++) gW[wo + k] += d * aIn[ao + k];
      }
    }
    let prev = null;
    if (l > 0) {
      prev = new Float64Array(n * L.in);
      for (let s = 0; s < n; s++) {
        for (let j = 0; j < L.out; j++) {
          const d = dz[s * L.out + j];
          if (d === 0) continue;
          const wo = j * L.in, ao = s * L.in;
          for (let k = 0; k < L.in; k++) prev[ao + k] += L.W[wo + k] * d;
        }
      }
      for (let i = 0; i < prev.length; i++) {
        const a = aIn[i];
        prev[i] *= net.act === "relu" ? (a > 0 ? 1 : 0) : 1 - a * a;
      }
    }
    grads[l] = { gW, gb };
    dz = prev;
  }
  return { loss, acc: correct / n, acts, grads };
}

export function applyGrads(net, grads, lr) {
  net.layers.forEach((L, l) => {
    const { gW, gb } = grads[l];
    for (let i = 0; i < L.W.length; i++) L.W[i] -= lr * gW[i];
    for (let j = 0; j < L.out; j++) L.b[j] -= lr * gb[j];
  });
}

const rms = (arr) => {
  let s = 0;
  for (const v of arr) s += v * v;
  return Math.sqrt(s / arr.length);
};

// Per hidden layer: activation spread, gradient size, how many neurons are actually different,
// and the share that are dead (ReLU never fires) or stuck (tanh pinned near +-1).
export function layerStats(net, step) {
  const { acts, grads } = step;
  const out = [];
  for (let l = 1; l <= net.depth; l++) {
    const a = acts[l], L = net.layers[l - 1];
    const n = a.length / L.out;
    let mean = 0;
    for (const v of a) mean += v;
    mean /= a.length;
    let v2 = 0;
    for (const v of a) v2 += (v - mean) ** 2;
    let bad = 0;
    if (net.act === "tanh") {
      for (const v of a) if (Math.abs(v) > 0.97) bad++;
      bad /= a.length;
    } else {
      for (let j = 0; j < L.out; j++) {
        let alive = false;
        for (let s = 0; s < n && !alive; s++) alive = a[s * L.out + j] > 0;
        if (!alive) bad++;
      }
      bad /= L.out;
    }
    const keys = new Set();
    for (let j = 0; j < L.out; j++) {
      let k = "";
      for (let i = 0; i < L.in; i++) k += L.W[j * L.in + i].toFixed(5) + ",";
      keys.add(k + L.b[j].toFixed(5));
    }
    out.push({ spread: Math.sqrt(v2 / a.length), grad: rms(grads[l - 1].gW), unique: keys.size, bad });
  }
  return out;
}
