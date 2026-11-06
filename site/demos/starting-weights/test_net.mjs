// node site/demos/starting-weights/test_net.mjs
// Checks net.js: backprop against finite differences, and the behaviours the page claims.
import assert from "node:assert/strict";
import { rng, makeSpiral, makeNet, lossAndGrads, applyGrads, layerStats, WIDTH } from "./net.js";

const data = makeSpiral(rng(1), 20);

for (const act of ["tanh", "relu"]) {
  const net = makeNet({ depth: 3, act, init: "scaled", rand: rng(7) });
  const { grads } = lossAndGrads(net, data.X, data.Y, data.n);
  const eps = 1e-6;
  let worst = 0;
  for (let l = 0; l < net.layers.length; l++) {
    const L = net.layers[l];
    for (const i of [0, Math.floor(L.W.length / 2), L.W.length - 1]) {
      const keep = L.W[i];
      L.W[i] = keep + eps;
      const up = lossAndGrads(net, data.X, data.Y, data.n).loss;
      L.W[i] = keep - eps;
      const down = lossAndGrads(net, data.X, data.Y, data.n).loss;
      L.W[i] = keep;
      const num = (up - down) / (2 * eps), ana = grads[l].gW[i];
      const err = Math.abs(num - ana) / Math.max(1e-8, Math.abs(num) + Math.abs(ana));
      worst = Math.max(worst, err);
    }
  }
  assert.ok(worst < 1e-4, `${act}: backprop disagrees with finite differences (${worst})`);
  console.log(`ok  ${act} gradients match finite differences (worst relative error ${worst.toExponential(1)})`);
}

function train(init, act, steps, lr = 0.3) {
  const net = makeNet({ depth: 3, act, init, rand: rng(3) });
  let step;
  for (let i = 0; i < steps; i++) {
    step = lossAndGrads(net, data.X, data.Y, data.n);
    applyGrads(net, step.grads, lr);
  }
  step = lossAndGrads(net, data.X, data.Y, data.n);
  return { net, step, stats: layerStats(net, step) };
}

{
  const { stats } = train("same", "tanh", 300);
  assert.ok(stats.every((s) => s.unique === 1), "same init should stay one neuron per layer");
  console.log("ok  all-the-same init stays 1 unique neuron per layer after 300 steps");
}
{
  const { stats } = train("zero", "tanh", 50);
  assert.ok(stats.every((s) => s.grad === 0), "zero init should give exactly zero hidden gradients");
  console.log("ok  all-zeros init gives exactly zero hidden-layer gradients");
}
{
  const { stats } = train("scaled", "tanh", 1);
  assert.ok(stats.every((s) => s.unique === WIDTH), "scaled init should start with every neuron different");
  const tiny = train("tiny", "tanh", 1).stats;
  assert.ok(tiny[tiny.length - 1].spread < 0.01, "tiny init should shrink the signal by the last layer");
  console.log("ok  scaled init: every neuron different; tiny init: signal fades by the last layer");
}
