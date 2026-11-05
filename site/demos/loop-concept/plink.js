// Plink in the browser: a port of experiments/loop-concept/plink.py.
// The Python version transpiles Plink to Python and runs it, so this port copies Python's
// semantics where they show through (floor div/mod, `and`/`or` returning operands, str * int, list printing).
// Checked against plink.py on every Plink program the models wrote (see site/demos/loop-concept/test_plink.mjs).

export class PlinkSyntaxError extends Error {}
export class PlinkRuntimeError extends Error {}

const BUILTINS = new Set(["list", "item", "size", "text"]);
const WORDS = { and: "and", or: "or", not: "not", div: "//", mod: "%", true: "true", false: "false" };
const TOKEN = /\s*(?:(\d+)|("[^"]*")|([A-Za-z_][A-Za-z_0-9]*)|(<>|<=|>=|[-+*()<>=,&]))/y;
const PY_KEYWORDS = new Set(["False", "None", "True", "and", "as", "assert", "async", "await", "break", "class",
  "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is",
  "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"]);

// ------------------------------------------------------------------ expressions

function tokenize(src, names, n) {
  const toks = [];
  src = src.trim();
  if (!src) throw new PlinkSyntaxError(`line ${n}: missing expression`);
  let pos = 0;
  while (pos < src.length) {
    TOKEN.lastIndex = pos;
    const m = TOKEN.exec(src);
    if (!m || m.index + m[0].length === pos) {
      throw new PlinkSyntaxError(`line ${n}: can't read ${pyStrRepr(src.slice(pos).trim().slice(0, 20))}`);
    }
    pos = m.index + m[0].length;
    const [, num, str, word, op] = m;
    if (num) toks.push({ t: "num", v: num });
    else if (str) toks.push({ t: "str", v: str });
    else if (word) {
      if (word in WORDS) toks.push({ t: "op", v: WORDS[word] });
      else if (BUILTINS.has(word)) toks.push({ t: "builtin", v: word });
      else if (names.has(word)) toks.push({ t: "name", v: word });
      else throw new PlinkSyntaxError(`line ${n}: unknown name ${pyStrRepr(word)}`);
    } else {
      toks.push({ t: "op", v: { "=": "==", "<>": "!=", "&": "+" }[op] ?? op });
    }
  }
  return toks;
}

const CMP = new Set(["==", "!=", "<", ">", "<=", ">="]);

function parseExpr(src, names, n) {
  const toks = tokenize(src, names, n);
  let i = 0;
  const bad = () => new PlinkSyntaxError(`line ${n}: bad expression ${pyStrRepr(src)}`);
  const peek = () => toks[i];
  const isOp = (v) => toks[i] && toks[i].t === "op" && toks[i].v === v;

  function orExpr() {
    let a = andExpr();
    while (isOp("or")) { i++; a = { k: "or", a, b: andExpr() }; }
    return a;
  }
  function andExpr() {
    let a = notExpr();
    while (isOp("and")) { i++; a = { k: "and", a, b: notExpr() }; }
    return a;
  }
  function notExpr() {
    if (isOp("not")) { i++; return { k: "not", a: notExpr() }; }
    return compare();
  }
  function compare() {
    const first = arith();
    const ops = [], rest = [];
    while (peek() && peek().t === "op" && CMP.has(peek().v)) { ops.push(toks[i++].v); rest.push(arith()); }
    return ops.length ? { k: "cmp", first, ops, rest } : first;
  }
  function arith() {
    let a = term();
    while (isOp("+") || isOp("-")) { const op = toks[i++].v; a = { k: "bin", op, a, b: term() }; }
    return a;
  }
  function term() {
    let a = unary();
    while (isOp("*") || isOp("//") || isOp("%")) { const op = toks[i++].v; a = { k: "bin", op, a, b: unary() }; }
    return a;
  }
  function unary() {
    if (isOp("-") || isOp("+")) { const op = toks[i++].v; return { k: "neg", op, a: unary() }; }
    return postfix();
  }
  function postfix() {
    let a = atom();
    while (isOp("(")) {
      i++;
      const args = [];
      while (!isOp(")")) {
        if (!peek()) throw bad();
        args.push(orExpr());
        if (isOp(",")) i++;
        else if (!isOp(")")) throw bad();
      }
      i++;
      a = { k: "call", f: a, args };
    }
    return a;
  }
  function atom() {
    const tk = toks[i++];
    if (!tk) throw bad();
    if (tk.t === "num") {
      if (tk.v.length > 1 && tk.v[0] === "0" && /[1-9]/.test(tk.v)) throw bad(); // Python rejects 012
      return { k: "lit", v: Number(tk.v) };
    }
    if (tk.t === "str") return { k: "lit", v: pyUnescape(tk.v.slice(1, -1)) };
    if (tk.t === "name") return { k: "var", v: tk.v };
    if (tk.t === "builtin") return { k: "fn", v: tk.v };
    if (tk.t === "op" && (tk.v === "true" || tk.v === "false")) return { k: "lit", v: tk.v === "true" };
    if (tk.t === "op" && tk.v === "(") {
      if (isOp(")")) throw bad(); // () is an empty tuple in Python; not a Plink value
      const e = orExpr();
      if (!isOp(")")) throw bad(); // (a, b) would be a tuple in Python
      i++;
      return e;
    }
    throw bad();
  }

  const tree = orExpr();
  if (i !== toks.length) throw bad();
  return tree;
}

function pyUnescape(s) {
  return s.replace(/\\(n|t|\\|'|r|0)/g, (_, c) => ({ n: "\n", t: "\t", "\\": "\\", "'": "'", r: "\r", 0: "\0" })[c]);
}

function pyStrRepr(s) {
  const q = s.includes("'") && !s.includes('"') ? '"' : "'";
  return q + s.replace(/\\/g, "\\\\").replace(new RegExp(q, "g"), "\\" + q) + q;
}

// ------------------------------------------------------------------ statements

const RE = {
  let: /^let ([A-Za-z_]\w*) be (.+)$/,
  set: /^set ([A-Za-z_]\w*) to (.+)$/,
  show: /^show (.+)$/,
  count: /^count ([A-Za-z_]\w*) from (.+?) to (.+?)(?: by (.+))?$/,
  forIndex: /^for each index ([A-Za-z_]\w*) in (.+)$/,
  forEach: /^for each ([A-Za-z_]\w*) in (.+)$/,
  while: /^while (.+)$/,
  if: /^if (.+)$/,
  orif: /^orif (.+)$/,
};

export function parse(text) {
  const names = new Set();
  const root = { body: [] };
  const stack = []; // open blocks: { kind, node }
  const cur = () => (stack.length ? stack[stack.length - 1].body : root.body);
  const reserved = (v) => BUILTINS.has(v) || v in WORDS;
  const pyName = (v, n) => { if (PY_KEYWORDS.has("v_" + v)) throw new PlinkSyntaxError(`line ${n}: bad name`); };

  const lines = text.split(new RegExp("\\r\\n|[\\r\\n\\v\\f\\x1c\\x1d\\x1e\\x85\\u2028\\u2029]"));
  if (lines.length && lines[lines.length - 1] === "" && /(\r\n|\r|\n)$/.test(text)) lines.pop();
  lines.forEach((raw, idx) => {
    const n = idx + 1;
    const line = raw.trim();
    let m;
    if (!line || line === "note" || line.startsWith("note ")) return;
    if ((m = line.match(RE.let))) {
      const [, v, e] = m;
      if (names.has(v) || reserved(v)) throw new PlinkSyntaxError(`line ${n}: ${pyStrRepr(v)} already declared`);
      pyName(v, n);
      const ex = parseExpr(e, names, n);
      names.add(v);
      cur().push({ k: "assign", v, e: ex, n });
    } else if ((m = line.match(RE.set))) {
      const [, v, e] = m;
      if (!names.has(v)) throw new PlinkSyntaxError(`line ${n}: set before let: ${pyStrRepr(v)}`);
      cur().push({ k: "assign", v, e: parseExpr(e, names, n), n });
    } else if ((m = line.match(RE.show))) {
      cur().push({ k: "show", es: splitCommas(m[1], n).map((p) => parseExpr(p, names, n)), n });
    } else if ((m = line.match(RE.count))) {
      const [, v, a, b, step] = m;
      names.add(v);
      const node = { k: "count", v, a: parseExpr(a, names, n), b: parseExpr(b, names, n),
        step: step ? parseExpr(step, names, n) : { k: "lit", v: 1 }, body: [], n };
      cur().push(node);
      stack.push({ kind: "loop", body: node.body });
    } else if ((m = line.match(RE.forIndex)) || (m = line.match(RE.forEach))) {
      const index = RE.forIndex.test(line);
      const [, v, e] = m;
      const ex = parseExpr(e, names, n);
      names.add(v);
      const node = { k: index ? "forIndex" : "forEach", v, e: ex, body: [], n };
      cur().push(node);
      stack.push({ kind: "loop", body: node.body });
    } else if ((m = line.match(RE.while))) {
      const node = { k: "while", c: parseExpr(m[1], names, n), body: [], n };
      cur().push(node);
      stack.push({ kind: "loop", body: node.body });
    } else if ((m = line.match(RE.if))) {
      const node = { k: "if", branches: [{ c: parseExpr(m[1], names, n), body: [] }], n };
      cur().push(node);
      stack.push({ kind: "if", body: node.branches[0].body, node });
    } else if ((m = line.match(RE.orif))) {
      const top = stack[stack.length - 1];
      if (!top || top.kind !== "if") throw new PlinkSyntaxError(`line ${n}: orif outside an if`);
      const br = { c: parseExpr(m[1], names, n), body: [] };
      top.node.branches.push(br);
      top.body = br.body;
    } else if (line === "otherwise") {
      const top = stack[stack.length - 1];
      if (!top || top.kind !== "if") throw new PlinkSyntaxError(`line ${n}: otherwise outside an if`);
      const br = { c: null, body: [] };
      top.node.branches.push(br);
      stack[stack.length - 1] = { kind: "else", body: br.body };
    } else if (line === "stop") {
      if (!stack.some((s) => s.kind === "loop")) throw new PlinkSyntaxError(`line ${n}: stop outside a loop`);
      cur().push({ k: "stop", n });
    } else if (line === "end") {
      if (!stack.length) throw new PlinkSyntaxError(`line ${n}: end with nothing open`);
      stack.pop();
    } else {
      throw new PlinkSyntaxError(`line ${n}: can't read ${pyStrRepr(line.slice(0, 40))}`);
    }
  });
  if (stack.length) throw new PlinkSyntaxError(`missing end (${stack.length} block(s) still open)`);
  return root.body;
}

function splitCommas(s, n) {
  const parts = [];
  let depth = 0, cur = "", quote = false;
  for (const ch of s) {
    if (ch === '"') quote = !quote;
    if (!quote && ch === "(") depth++;
    if (!quote && ch === ")") depth--;
    if (ch === "," && depth === 0 && !quote) { parts.push(cur); cur = ""; } else cur += ch;
  }
  parts.push(cur);
  if (parts.some((p) => !p.trim())) throw new PlinkSyntaxError(`line ${n}: empty value in show`);
  return parts;
}

// ------------------------------------------------------------------ values (Python-flavoured)

const isNum = (x) => typeof x === "number" || typeof x === "boolean";
const isInt = (x) => typeof x === "number";
const num = (x) => (typeof x === "boolean" ? (x ? 1 : 0) : x);
const typeName = (x) => (typeof x === "boolean" ? "bool" : typeof x === "number" ? "int" : typeof x === "string" ? "str"
  : Array.isArray(x) ? "list" : "function");
const typeErr = (msg) => new PlinkRuntimeError(msg);

function truthy(x) {
  if (typeof x === "boolean") return x;
  if (typeof x === "number") return x !== 0;
  if (typeof x === "string" || Array.isArray(x)) return x.length > 0;
  return true;
}

function repr(x) {
  if (typeof x === "boolean") return x ? "True" : "False";
  if (typeof x === "number") return String(x);
  if (typeof x === "string") return pyStrRepr(x);
  if (Array.isArray(x)) return "[" + x.map(repr).join(", ") + "]";
  return `<function _${x.name}>`;
}

function text(x) {
  if (typeof x === "string") return x;
  if (typeof x === "boolean") return x ? "true" : "false";
  return repr(x);
}

function checkNum(x) {
  if (!Number.isSafeInteger(x)) throw new PlinkRuntimeError("number too big for this demo (Python would keep going)");
  return x;
}

function eq(a, b) {
  if (isNum(a) && isNum(b)) return num(a) === num(b);
  if (typeof a === "string" && typeof b === "string") return a === b;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => eq(x, b[i]));
  if (typeof a === "object" && typeof b === "object") return a === b;
  return false;
}

function order(a, b, op) {
  let c;
  if (isNum(a) && isNum(b)) c = num(a) - num(b);
  else if (typeof a === "string" && typeof b === "string") c = a < b ? -1 : a > b ? 1 : 0;
  else if (Array.isArray(a) && Array.isArray(b)) {
    c = 0;
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      if (!eq(a[i], b[i])) { return order(a[i], b[i], op); }
    }
    c = a.length - b.length;
  } else throw typeErr(`'${op}' not supported between ${typeName(a)} and ${typeName(b)}`);
  return { "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0 }[op];
}

function binop(op, a, b) {
  if (op === "+") {
    if (isNum(a) && isNum(b)) return checkNum(num(a) + num(b));
    if (typeof a === "string" && typeof b === "string") return a + b;
    if (Array.isArray(a) && Array.isArray(b)) return a.concat(b);
    throw typeErr(`can't add ${typeName(a)} and ${typeName(b)} (use text() to join a number to text)`);
  }
  if (op === "*") {
    if (isNum(a) && isNum(b)) return checkNum(num(a) * num(b));
    const rep = (s, k) => { k = Math.max(0, num(k)); return Array.isArray(s) ? Array.from({ length: k }, () => s).flat() : s.repeat(k); };
    if ((typeof a === "string" || Array.isArray(a)) && isNum(b)) return rep(a, b);
    if (isNum(a) && (typeof b === "string" || Array.isArray(b))) return rep(b, a);
    throw typeErr(`can't multiply ${typeName(a)} by ${typeName(b)}`);
  }
  if (!isNum(a) || !isNum(b)) throw typeErr(`'${op === "//" ? "div" : op === "%" ? "mod" : op}' needs numbers`);
  const x = num(a), y = num(b);
  if (op === "-") return checkNum(x - y);
  if (y === 0) throw new PlinkRuntimeError(op === "//" ? "division by zero" : "modulo by zero");
  if (op === "//") return Math.floor(x / y);
  return ((x % y) + y) % y; // Python's mod takes the divisor's sign
}

const FNS = {
  list: (...a) => a,
  item: (xs, i, ...extra) => {
    if (extra.length || i === undefined) throw typeErr("item takes 2 values: item(xs, i)");
    if (!Array.isArray(xs)) throw new PlinkRuntimeError("item needs a list");
    if (!isInt(i)) throw new PlinkRuntimeError(`expected a number, got ${repr(i)}`);
    if (!(i >= 0 && i < xs.length)) throw new PlinkRuntimeError(`item ${i} out of range`);
    return xs[i];
  },
  size: (xs, ...extra) => {
    if (extra.length || xs === undefined) throw typeErr("size takes 1 value");
    if (!Array.isArray(xs) && typeof xs !== "string") throw new PlinkRuntimeError("size needs a list or text");
    return xs.length;
  },
  text: (x, ...extra) => {
    if (extra.length || x === undefined) throw typeErr("text takes 1 value");
    return text(x);
  },
};
for (const k of Object.keys(FNS)) Object.defineProperty(FNS[k], "name", { value: k });

// ------------------------------------------------------------------ running

class Stop {}

export function run(source, { maxSteps = 2_000_000 } = {}) {
  const program = parse(source);
  const env = new Map();
  const out = [];
  let steps = 0;
  const tick = () => { if (++steps > maxSteps) throw new PlinkRuntimeError("took too long (stopped after 2 million steps)"); };

  function ev(e) {
    switch (e.k) {
      case "lit": return e.v;
      case "var":
        if (!env.has(e.v)) throw new PlinkRuntimeError(`${e.v} has no value yet`);
        return env.get(e.v);
      case "fn": return FNS[e.v];
      case "or": { const a = ev(e.a); return truthy(a) ? a : ev(e.b); }
      case "and": { const a = ev(e.a); return truthy(a) ? ev(e.b) : a; }
      case "not": return !truthy(ev(e.a));
      case "neg": {
        const a = ev(e.a);
        if (!isNum(a)) throw typeErr(`bad operand for unary ${e.op}: ${typeName(a)}`);
        return e.op === "-" ? -num(a) || 0 : num(a);
      }
      case "bin": return binop(e.op, ev(e.a), ev(e.b));
      case "cmp": {
        let left = ev(e.first);
        for (let j = 0; j < e.ops.length; j++) {
          const right = ev(e.rest[j]);
          const op = e.ops[j];
          const ok = op === "==" ? eq(left, right) : op === "!=" ? !eq(left, right) : order(left, right, op);
          if (!ok) return false;
          left = right;
        }
        return true;
      }
      case "call": {
        const f = ev(e.f);
        if (typeof f !== "function") throw typeErr(`${typeName(f)} can't be called`);
        return f(...e.args.map(ev));
      }
    }
  }

  function truth(x) {
    if (typeof x !== "boolean") throw new PlinkRuntimeError(`condition must be true/false, got ${repr(x)}`);
    return x;
  }

  function exec(body) {
    for (const s of body) {
      tick();
      switch (s.k) {
        case "assign": env.set(s.v, ev(s.e)); break;
        case "show": out.push(s.es.map((e) => text(ev(e))).join(" ")); break;
        case "stop": throw new Stop();
        case "count": {
          const a = ev(s.a), b = ev(s.b), step = ev(s.step);
          for (const x of [a, b, step]) if (!isInt(x)) throw new PlinkRuntimeError(`expected a number, got ${repr(x)}`);
          if (step === 0) throw new PlinkRuntimeError("count step of 0");
          const end = b + (step > 0 ? 1 : -1);
          for (let i = a; step > 0 ? i < end : i > end; i += step) {
            env.set(s.v, i);
            if (loopBody(s.body)) break;
          }
          break;
        }
        case "forEach": case "forIndex": {
          const xs = ev(s.e);
          let items;
          if (s.k === "forEach") {
            if (!Array.isArray(xs)) throw new PlinkRuntimeError("for each needs a list");
            items = xs.slice();
          } else {
            items = [...Array(FNS.size(xs)).keys()];
          }
          for (const x of items) { env.set(s.v, x); if (loopBody(s.body)) break; }
          break;
        }
        case "while":
          while (truth(ev(s.c))) { tick(); if (loopBody(s.body)) break; }
          break;
        case "if":
          for (const br of s.branches) {
            if (br.c === null || truth(ev(br.c))) { exec(br.body); break; }
          }
          break;
      }
    }
  }

  function loopBody(body) {
    tick();
    try { exec(body); return false; } catch (e) { if (e instanceof Stop) return true; throw e; }
  }

  try {
    exec(program);
  } catch (e) {
    if (e instanceof PlinkRuntimeError) { e.output = out.join("\n"); }
    throw e;
  }
  return out.join("\n");
}

// Run and report the way plink.py's command line does: { ok, stdout, error, kind: "ok" | "syntax" | "runtime" }
export function runReport(source) {
  try {
    return { kind: "ok", stdout: run(source), error: "" };
  } catch (e) {
    if (e instanceof PlinkSyntaxError) return { kind: "syntax", stdout: "", error: "syntax error: " + e.message };
    if (e instanceof PlinkRuntimeError) return { kind: "runtime", stdout: e.output || "", error: "runtime error: " + e.message };
    throw e;
  }
}
