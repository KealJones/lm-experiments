const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const pct = (x, d = 1) => `${(100 * x).toFixed(d)}%`;
const seg = (el, items, current, onPick) => {
  el.innerHTML = items.map(([v, label, disabled]) =>
    `<button type="button" data-v="${esc(v)}" aria-pressed="${String(v) === String(current)}"${disabled ? " disabled" : ""}>${esc(label)}</button>`).join("");
  el.onclick = (e) => { const b = e.target.closest("button"); if (b && !b.disabled) onPick(b.dataset.v); };
};

// ---------------------------------------------------------------- the jobs (from experiments/lfm3-mlc/hf-*/steps.txt and the job logs)

const JOBS = [
  { n: 1, cls: "fail", min: 2.1, title: "Build the compiler from source",
    tried: "Build TVM at WebLLM 0.2.87's commit (e345029) with its TIRx package, Debian's LLVM 16 and emscripten, on a Hugging Face CPU box.",
    log: "CMake 3.26 or higher is required.  You are running version 3.25.1",
    why: "Debian 12 ships CMake 3.25, and TVM's TIRx part needs 3.26.",
    fix: "Install CMake and Ninja from pip instead of apt." },
  { n: 2, cls: "fail", min: "<1", title: "Same build, newer CMake",
    tried: "The same build with pip's CMake.",
    log: "== 20:32:02 ninja -j64\n(the log stops here)",
    why: "The container was killed mid-build, almost certainly out of memory: nproc reported the host's 64 cores, but the container had 8, so ninja started 64 compilers at once.",
    fix: "Cap the build at 10 parallel jobs." },
  { n: 3, cls: "fail", min: 22.7, title: "The compiler builds",
    tried: "TVM and TIRx built in about 15 minutes; mlc-llm loaded with LFM3 registered; LFM3's weights converted to 4-bit. Then compile the WebGPU model library.",
    log: "== 21:25:47 compile webgpu q4f16_1\nclang: error: clang frontend command failed with exit code 70 (use -v to see invocation)\nclang version 24.0.0git",
    why: "emscripten's clang crashed while compiling the CPU half of the model library. Job 5 saved the full message: TVM's LLVM 16 writes that half as bitcode, and clang 24 refuses it because the two LLVMs disagree on one detail of the data layout.",
    fix: "Save the built compiler as a 40 MB tarball so later jobs skip the 15-minute build, and add a fallback that has TVM write object files instead of bitcode." },
  { n: 4, cls: "fail", min: 1.1, title: "Reuse the saved compiler",
    tried: "Unpack job 3's compiler and go straight to the compile.",
    log: "OSError: libLLVM-16.so.1: cannot open shared object file: No such file or directory",
    why: "The saved compiler links against LLVM 16's runtime library, and the fresh container only got git, zstd and curl.",
    fix: "Install the same LLVM 16 libraries the compiler was built against." },
  { n: 5, cls: "fail", min: 6.2, title: "Both linking routes, side by side",
    tried: "Weights convert, the model compiles. Link the .wasm with bitcode, then with object files.",
    log: "bitcode:\nfatal error: error in backend: Can't create a MachineFunction using a Module with a Target-incompatible DataLayout attached\n  Target DataLayout: e-m:e-p:32:32-p10:8:8-p20:8:8-i64:64-i128:128-f128:64-n32:64-S128-ni:1:10:20\n  Module DataLayout: e-m:e-p:32:32-p10:8:8-p20:8:8-i64:64-i128:128-n32:64-S128-ni:1:10:20\nobject files:\nwasm-ld: error: …/wasm_runtime.o: undefined symbol: typeinfo for std::bad_alloc\nemcc: warning: link failed with undefined C++ symbols. Try linking with 'em++' or passing '-sDEFAULT_TO_CXX'",
    why: "The object-file route gets past clang, but TVM links with emcc, which leaves out the C++ standard library that TVM's own web runtime needs.",
    fix: "Link with em++ (the linker's own suggestion) and try the object-file route first." },
  { n: 6, cls: "pass", min: 8.1, title: "It links",
    tried: "Object files, linked with em++.",
    log: "uploaded https://huggingface.co/kealjones/LFM3-1.7B-q4f16_1-MLC\nuploaded https://huggingface.co/kealjones/LFM3-1.7B-q4f32_1-MLC",
    why: "A 6.7 MB model library and 973 MB of 4-bit weights, in a 16-bit build for phones (WebGPU's shader-f16) and a 32-bit one for GPUs without it. On Keal's iPhone it greets correctly at 13.7 tokens a second.",
    fix: "Nothing. But the iPhone sits at its memory edge: a long task still crashes it." },
  { n: 7, cls: "part", min: 6.4, title: "A 3-bit build",
    tried: "The same build with MLC's 3-bit format (q3f16_1), 788 MB of weights, plus a 32-bit 3-bit for testing.",
    log: "argument --quantization: invalid choice: 'q3f32_1'",
    why: "The 3-bit phone build worked; MLC has no 32-bit 3-bit. On the phone the 3-bit build runs and writes fluent English, but it can't tell that \"Hii\" is a greeting (see below).",
    fix: "Keep 4 bits, and find the memory somewhere else." },
  { n: 8, cls: "pass", min: 4.0, title: "Liquid's trained weights, a lighter library",
    tried: "Copy Liquid's quantization-aware-trained 4-bit weights into the build exactly, and compile a model library for one conversation at a time.",
    log: "replaced 107 linear layers with QAD weights; wrote /work/qad-pkg\nLFM3-1.7B-q4f16_1-b1-webgpu.wasm: \"memory_usage\": {… \"batch_decode\": 635936, \"batch_prefill\": 16510976, …}\nLFM3-1.7B-q4f16_1-webgpu.wasm:    \"memory_usage\": {… \"batch_decode\": 81399808, \"batch_prefill\": 81534976, …}",
    why: "MLC's default reserves room for 128 conversations at once. WebLLM runs one. Building for one frees about 146 MB.",
    fix: "In Squiggle as \"Test: LFM3 1.7B QAD (GPU)\"." },
];
let job = 6;
function renderJobs() {
  $("#jobs").innerHTML = JOBS.map((j) =>
    `<button type="button" class="job ${j.cls}" data-n="${j.n}" aria-pressed="${j.n === job}"><span class="n">${j.n}</span><span class="t">${j.min} min</span></button>`).join("");
  const j = JOBS[job - 1];
  const verdict = { fail: `<span class="v-fail">failed</span>`, part: `<span class="v-part">half worked</span>`, pass: `<span class="v-pass">worked</span>` }[j.cls];
  $("#job-card").innerHTML = `<h3>Job ${j.n}: ${esc(j.title)} (${verdict})</h3>
    <dl class="kv"><dt>Tried</dt><dd>${esc(j.tried)}</dd>
    <dt>The log</dt><dd><pre class="code">${esc(j.log)}</pre></dd>
    <dt>Why</dt><dd>${esc(j.why)}</dd>
    <dt>Next</dt><dd>${esc(j.fix)}</dd></dl>`;
}
$("#jobs").addEventListener("click", (e) => { const b = e.target.closest(".job"); if (b) { job = Number(b.dataset.n); renderJobs(); } });

// ---------------------------------------------------------------- versions

const VERSIONS = [
  { cls: "bad", title: "WebLLM 0.2.87 + the community LFM2.5 build", lib: "runtime.TVMTensorAllocWithScope", js: "runtime.TensorAllocWithScope",
    verdict: "Cannot find global function runtime.TensorAllocWithScope" },
  { cls: "ok", title: "WebLLM 0.2.86 + the community LFM2.5 build", lib: "runtime.TVMTensorAllocWithScope", js: "runtime.TVMTensorAllocWithScope",
    verdict: "Loads (what Squiggle uses for LFM2.5)" },
  { cls: "ok", title: "WebLLM 0.2.87 + our LFM3 build", lib: "runtime.TensorAllocWithScope", js: "runtime.TensorAllocWithScope",
    verdict: "Loads: compiled with TVM e345029, built from source" },
];
$("#versions").innerHTML = VERSIONS.map((v) => `<div class="ver ${v.cls}"><h3>${esc(v.title)}</h3>
  <p class="names" style="margin:0">model library has: ${esc(v.lib)}<br>WebLLM calls: ${esc(v.js)}</p>
  <p class="verdict ${v.cls === "ok" ? "v-pass" : "v-fail"}" style="margin:0">${esc(v.verdict)}</p></div>`).join("");

// ---------------------------------------------------------------- layers and how far back they read (LiquidAI/LFM3-1.7B config.json)

const TYPES = ["conv", "conv", "full_attention", "conv", "sliding_attention", "conv", "full_attention", "conv", "sliding_attention", "conv",
  "full_attention", "conv", "sliding_attention", "conv", "full_attention", "conv", "sliding_attention", "conv", "full_attention", "conv",
  "sliding_attention", "conv", "full_attention", "conv"].map((t) => ({ conv: "conv", sliding_attention: "sliding", full_attention: "global" })[t]);
const KIND = {
  conv: { label: "Convolution", reach: 7, about: "a short convolution over the last 7 tokens, carried between tokens as a small state (no attention cache at all)" },
  sliding: { label: "Window attention", reach: 256, about: "attention over the last 256 tokens, with its own rotary positions (theta 10,000, the whole head)" },
  global: { label: "Full attention", reach: Infinity, about: "attention over everything so far, with rotary positions on half of each head (theta 1,000,000), query/key norms and a per-head gate on the output" },
};
let picked = 4;
function renderLayers() {
  $("#layers").innerHTML = TYPES.map((t, i) => `<button type="button" class="layer ${t}" data-i="${i}" aria-pressed="${i === picked}" aria-label="Layer ${i}: ${KIND[t].label}">${i}</button>`).join("");
  const len = Number($("#reach-len").value);
  $("#reach-len-out").textContent = `${len.toLocaleString()} tokens`;
  const kind = TYPES[picked];
  const ticks = [];
  for (let c = 256; c < len; c += 256) ticks.push(`<span class="tick" style="left:${(100 * c) / len}%"></span>`);
  $("#reach-rows").innerHTML = ["conv", "sliding", "global"].map((k) => {
    const seen = Math.min(KIND[k].reach, len);
    const count = TYPES.filter((t) => t === k).length;
    return `<div class="reach-row${k === kind ? "" : " dim"}"><span class="lab"><span class="legend-key seen ${k}" style="position:static;display:inline-block"></span>${KIND[k].label} ×${count}</span>
      <div class="track" title="${seen.toLocaleString()} tokens">${ticks.join("")}<span class="seen ${k}" style="width:${Math.max(0.4, (100 * seen) / len)}%"></span><span class="now"></span></div></div>`;
  }).join("");
  const chunks = Math.ceil(len / 256);
  $("#reach-note").innerHTML = `Layer ${picked} is ${KIND[kind].about}. The red mark is the token being written; the shading is what this kind of layer
    can see. The thin lines are where MLC splits the prompt: a window layer's cache only works if no chunk is longer than the window, so the build feeds
    prompts in 256-token chunks (${chunks} for this one). Only the 11 attention layers keep a cache that grows with the prompt.`;
}
$("#layers").addEventListener("click", (e) => { const b = e.target.closest(".layer"); if (b) { picked = Number(b.dataset.i); renderLayers(); } });
$("#reach-len").addEventListener("input", renderLayers);

// ---------------------------------------------------------------- rounding (data/weights.json, from build_data.py)

let W;
const rstate = { g: 0, bits: 4, how: "mlc" };
function mlcRound(w, bits) {
  const maxInt = 2 ** (bits - 1) - 1;
  const s = Math.max(...w.map(Math.abs)) / maxInt || 1;
  const q = w.map((x) => Math.min(2 * maxInt, Math.max(0, Math.round(x / s + maxInt))));
  return { vals: q.map((k) => (k - maxInt) * s), levels: Array.from({ length: 2 * maxInt + 1 }, (_, j) => (j - maxInt) * s), q };
}
function rounded(g) {
  if (rstate.bits === 4 && rstate.how === "qad") return { vals: g.qad_k.map((k) => (k - 8) * g.qad_d), levels: Array.from({ length: 16 }, (_, j) => (j - 8) * g.qad_d) };
  if (rstate.bits === 4 && rstate.how === "q40") return { vals: g.plain_k.map((k) => (k - 8) * g.plain_d), levels: Array.from({ length: 16 }, (_, j) => (j - 8) * g.plain_d) };
  return mlcRound(g.w, rstate.bits);
}
function renderRound() {
  const g = W.groups[rstate.g];
  if (rstate.bits !== 4) rstate.how = "mlc";
  seg($("#pick-bits"), [[8, "8"], [4, "4"], [3, "3"], [2, "2"]], rstate.bits, (v) => { rstate.bits = Number(v); renderRound(); });
  seg($("#pick-how"), [["mlc", "Plain (MLC)"], ["q40", "Plain (llama.cpp)", rstate.bits !== 4], ["qad", "Liquid's training", rstate.bits !== 4]], rstate.how,
    (v) => { rstate.how = v; renderRound(); });
  const r = rounded(g);
  const movedIdx = rstate.how === "qad" ? g.qad_k.map((k, i) => k !== g.plain_k[i]) : g.w.map(() => false);
  const M = Math.max(...g.w.map(Math.abs), ...r.levels.map(Math.abs)) * 1.08;
  const Wd = 760, H = 300, L = 46, R = 12, T = 12, B = 22;
  const x = (i) => L + ((i + 0.5) * (Wd - L - R)) / 32;
  const y = (v) => T + ((M - v) * (H - T - B)) / (2 * M);
  const showLevels = r.levels.length <= 31;
  let svg = `<svg viewBox="0 0 ${Wd} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  if (showLevels) for (const l of r.levels) svg += `<line class="lvl" x1="${L}" x2="${Wd - R}" y1="${y(l)}" y2="${y(l)}"/>`;
  svg += `<line class="zero" x1="${L}" x2="${Wd - R}" y1="${y(0)}" y2="${y(0)}"/>`;
  svg += `<text x="${L - 6}" y="${y(M / 1.08) + 4}" text-anchor="end">${(M / 1.08).toFixed(3)}</text><text x="${L - 6}" y="${y(0) + 4}" text-anchor="end">0</text><text x="${L - 6}" y="${y(-M / 1.08) + 4}" text-anchor="end">${(-M / 1.08).toFixed(3)}</text>`;
  g.w.forEach((w, i) => {
    svg += `<line class="err" x1="${x(i)}" x2="${x(i)}" y1="${y(w)}" y2="${y(r.vals[i])}"/>`;
    svg += `<rect class="rnd${movedIdx[i] ? " moved" : ""}" x="${x(i) - 4}" y="${y(r.vals[i]) - 4}" width="8" height="8"/>`;
    if (movedIdx[i]) svg += `<circle class="moved-ring" cx="${x(i)}" cy="${y(r.vals[i])}" r="9"/>`;
    svg += `<circle class="orig" cx="${x(i)}" cy="${y(w)}" r="4.5"><title>weight ${g.cols[0] + i}: ${w} → ${r.vals[i].toPrecision(4)}</title></circle>`;
  });
  svg += `<text x="${L}" y="${H - 4}">weights ${g.cols[0]}–${g.cols[1]} of row ${g.row}</text></svg>`;
  $("#plot").outerHTML = svg.replace("<svg ", `<svg id="plot" role="img" aria-label="32 weights and their rounded values" `);
  const m = g.w.reduce((a, b) => a + Math.abs(b), 0) / 32;
  const e = g.w.reduce((a, w, i) => a + Math.abs(w - r.vals[i]), 0) / 32;
  const lv = rstate.how === "mlc" ? `${2 * (2 ** (rstate.bits - 1) - 1) + 1} levels` : "16 levels";
  $("#readout").innerHTML = `${lv}: rounding moves these weights ${pct(e / m)} on average${rstate.how === "qad" ? `, and ${movedIdx.filter(Boolean).length} of 32 sit on a different level than plain llama.cpp rounding puts them (orange)` : ""}.`;
  const notes = {
    mlc: rstate.bits === 3 ? "MLC's 3-bit actually rounds in groups of 40; this is the same rounding on these 32. Note how few levels are left." :
      rstate.bits === 2 ? "MLC has no 2-bit mode. This is what its rounding would do with 3 levels: most weights become zero." :
      rstate.bits === 8 ? "At 8 bits the levels are too close together to draw. This is why 8-bit models are nearly lossless and twice the size." :
      "MLC's 4-bit: scale = the biggest weight / 7, so 15 levels, one of the 16 a 4-bit number can hold unused. Our first build.",
    q40: "llama.cpp's Q4_0 uses all 16 levels: the scale is the biggest weight / −8, so the biggest weight lands exactly on the end level.",
    qad: g.same_scale ? "Same scale as plain llama.cpp rounding, so the orange weights are pure nudges: Liquid's training moved them to the next level over, on purpose." :
      "Here Liquid's training also picked a different scale than plain rounding would, so the whole grid moved. That happened in 70–78% of groups.",
  };
  $("#round-note").textContent = notes[rstate.how];
}
function renderStats() {
  $("#stats-table").innerHTML = `<thead><tr><th>Matrix (256 rows)</th><th>Plain 4-bit (llama.cpp)</th><th>Plain 4-bit (MLC, our first build)</th><th>Liquid's trained 4-bit</th><th>Plain 3-bit (MLC)</th><th>Weights the training moved</th></tr></thead><tbody>` +
    W.stats.map((s) => `<tr><td class="model">${esc(s.matrix)}</td><td>${pct(s.q4_0_plain)}</td><td>${pct(s.mlc4_plain)}</td><td>${pct(s.qad)}</td><td class="v-fail">${pct(s.mlc3_plain)}</td><td>${pct(s.moved)}</td></tr>`).join("") + "</tbody>";
}

// ---------------------------------------------------------------- the flip

function renderFlip() {
  const k = Number($("#flip-k").value), d = 0.00195, q = 15 - k;
  const bits = (n) => `<div class="nibbles" aria-hidden="true">${[3, 2, 1, 0].map((b) => `<span class="${(n >> b) & 1 ? "on" : ""}"></span>`).join("")}</div>`;
  $("#flip").innerHTML = `<div class="side"><h3>Liquid's file (llama.cpp Q4_0)</h3>${bits(k)}
      <p class="eq" style="margin:0">stored k = ${k}, scale d = ${d}<br>weight = (k − 8) × d = (${k} − 8) × ${d}</p><p class="val" style="margin:0">${((k - 8) * d).toFixed(5)}</p></div>
    <div class="side"><h3>Our build (MLC q4f16_1)</h3>${bits(q)}
      <p class="eq" style="margin:0">stored q = 15 − k = ${q}, scale s = −d = ${-d}<br>weight = (q − 7) × s = (${q} − 7) × ${-d}</p><p class="val" style="margin:0">${((q - 7) * -d).toFixed(5)}</p></div>`;
}
$("#flip-k").addEventListener("input", renderFlip);

// ---------------------------------------------------------------- which build wrote this (Keal's iPhone and llama.cpp, 9–10 Nov 2026)

const BUILDS = { q4: "Our 4-bit (phone)", q3: "Our 3-bit (phone)", liquid: "Liquid's 4-bit (llama.cpp)" };
const REPLIES = [
  { said: "Hii", build: "q3", think: "We need to handle the user's request. The user just said \"Hii\" which is likely a placeholder or nothing, but we should respond appropriately. … Given the ambiguity, I'll proceed to use the tool calls? But there's no specific query.", out: "(still thinking when Squiggle cut it off at its 400-token thinking budget)" },
  { said: "Hii", build: "liquid", think: "The user said \"Hii\" which is a greeting. I should respond in a friendly manner. No need for tools or planning here. Just greet them back and offer help.", out: "Hello! 👋 How can I help you today?" },
  { said: "Hi (no instructions, tools still listed)", build: "q3", think: "… Given the tools available, we might need to use them. But without a clear question, I should ask for more details. Perhaps the user typed by mistake?", out: "I'd be happy to help! Could you clarify what you'd like assistance with? For example, are you looking to search information, manage files, or work with code repositories?" },
  { said: "Hii", build: "q4", think: "(collapsed in the screenshot)", out: "Hello! How can I help you today?  (first word after 15.3 s, then 13.7 tokens a second)" },
];
let round = 0, score = 0, answered = false;
function renderHii() {
  if (round >= REPLIES.length) {
    $("#hii").innerHTML = `<p class="called">${score} of ${REPLIES.length}.</p><p style="margin:0">The tell is the first line of thinking: the 4-bit builds read "Hii" as a greeting; the 3-bit one reads it as a placeholder, and starts looking for a task.</p><div class="guess-buttons"><button type="button" class="primary" data-again>Again</button></div>`;
    return;
  }
  const r = REPLIES[round];
  $("#hii").innerHTML = `<div class="reply"><p class="said">Keal: "${esc(r.said)}"</p><p class="think">${esc(r.think)}</p><p class="out">${esc(r.out)}</p></div>
    <div class="guess-buttons">${Object.entries(BUILDS).map(([k, l]) => `<button type="button" class="primary" data-b="${k}">${esc(l)}</button>`).join("")}</div>
    <p class="tally" aria-live="polite">${answered ? "" : `Reply ${round + 1} of ${REPLIES.length}`}</p>`;
}
$("#hii").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.again !== undefined) { round = 0; score = 0; renderHii(); return; }
  if (b.dataset.next !== undefined) { round += 1; renderHii(); return; }
  const r = REPLIES[round];
  const right = b.dataset.b === r.build;
  if (right) score += 1;
  $("#hii .guess-buttons").innerHTML = `<p class="called ${right ? "v-pass" : "v-fail"}">${right ? "Right" : "No"}: ${esc(BUILDS[r.build])}.</p><button type="button" data-next>Next</button>`;
});

// ---------------------------------------------------------------- memory (job 8's model-library metadata; tensor-cache.json sizes)

const MB = 1e6;
const MEM = {
  weights: { q4: 973.0 * MB, q3: 788.1 * MB },
  scratch: { b128: (81.53 + 81.40) * MB, b1: (16.51 + 0.64) * MB },
  kvPerToken: 11 * 2 * 4 * 128 * 2, // 11 attention layers, keys and values, 4 KV heads of 128, fp16
  budget: 2000 * MB,
};
const mstate = { w: "q4", lib: "b128", ctx: 4096 };
function renderMem() {
  seg($("#mem-w"), [["q4", "4-bit"], ["q3", "3-bit"]], mstate.w, (v) => { mstate.w = v; renderMem(); });
  seg($("#mem-lib"), [["b128", "for 128 chats (default)"], ["b1", "for 1 chat"]], mstate.lib, (v) => { mstate.lib = v; renderMem(); });
  seg($("#mem-ctx"), [[4096, "4K tokens"], [2048, "2K tokens"]], mstate.ctx, (v) => { mstate.ctx = Number(v); renderMem(); });
  const parts = [
    ["m-weights", "Weights", MEM.weights[mstate.w]],
    ["m-scratch", "Scratch", MEM.scratch[mstate.lib]],
    ["m-kv", "Attention cache", MEM.kvPerToken * mstate.ctx],
  ];
  const total = parts.reduce((a, p) => a + p[2], 0);
  $("#membar").innerHTML = parts.map(([c, l, v]) => `<div class="seg-m ${c}" style="width:${(100 * v) / MEM.budget}%" title="${l}: ${Math.round(v / MB)} MB">${v / MEM.budget > 0.07 ? Math.round(v / MB) : ""}</div>`).join("");
  $("#membar").setAttribute("aria-label", `Model reserves ${Math.round(total / MB)} MB of about 2,000`);
  $("#memlegend").innerHTML = parts.map(([c, l, v]) => `<span><span class="legend-key ${c}"></span>${l} ${Math.round(v / MB)} MB</span>`).join("") +
    `<span><span class="legend-key" style="background:repeating-linear-gradient(135deg,var(--paper) 0 3px,var(--grid) 3px 6px);border:1px solid var(--rule)"></span>Left for Safari, the page and WebGPU: ${Math.round((MEM.budget - total) / MB)} MB</span>`;
  const notes = [];
  if (mstate.w === "q3") notes.push("3-bit saves 185 MB of weights, and it's the build that couldn't recognise a greeting.");
  if (mstate.lib === "b1") notes.push("The one-chat library frees ~146 MB without touching the model: it's what Squiggle's \"Test: LFM3 1.7B QAD (GPU)\" uses. It hasn't had a long task on the phone yet.");
  else notes.push("The default library keeps ~163 MB of scratch for 128 parallel chats. WebLLM runs one.");
  if (mstate.ctx === 2048) notes.push("Halving the context frees 46 MB and makes Squiggle compress the chat sooner.");
  $("#mem-note").textContent = `${notes.join(" ")} Not counted: the model library's batch_verify scratch (147 MB, for speculative decoding, which WebLLM doesn't call) and the convolution layers' state (a few hundred KB). The ~2 GB is what memtest measured on this iPhone, not a published limit.`;
}

// ---------------------------------------------------------------- go

renderJobs();
renderLayers();
renderFlip();
renderHii();
renderMem();
W = await fetch("data/weights.json").then((r) => r.json());
$("#pick-group").innerHTML = W.groups.map((g, i) =>
  `<option value="${i}">${esc(g.matrix)}, row ${g.row}${g.same_scale ? (g.moved ? ` (${g.moved} nudged)` : "") : " (new scale)"}</option>`).join("");
$("#pick-group").addEventListener("change", (e) => { rstate.g = Number(e.target.value); renderRound(); });
renderRound();
renderStats();
