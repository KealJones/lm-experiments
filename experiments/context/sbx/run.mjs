// Sandbox for the model's run_typescript tool.
// usage: node run.mjs <file.ts>   -> prints a short report (type errors, runtime errors, console output)
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const { JSDOM } = require('jsdom');

const file = process.argv[2];
const src = fs.readFileSync(file, 'utf8');
const out = [];

// 1. type-check (syntax + type errors)
const opts = { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, strict: false,
  noEmit: true, lib: ['lib.es2020.d.ts', 'lib.dom.d.ts'], types: [] };
const host = ts.createCompilerHost(opts);
const prog = ts.createProgram([file], opts, host);
const diags = ts.getPreEmitDiagnostics(prog).filter(d => d.file && d.file.fileName === file);
if (diags.length) {
  out.push(`TypeScript errors (${diags.length}):`);
  for (const d of diags.slice(0, 8)) {
    const { line } = d.file.getLineAndCharacterOfPosition(d.start);
    out.push(`  line ${line + 1}: ${ts.flattenDiagnosticMessageText(d.messageText, ' ')}`);
  }
} else out.push('TypeScript: no errors.');

// 2. run it (fake browser via jsdom; prompt() returns null, alert() is logged)
const js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
const logs = [];
const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>');
const g = dom.window;
const fakeConsole = { assert: (c, ...a) => { if (!c) logs.push('[assert failed] ' + a.join(' ')); }, info: (...a) => logs.push(a.join(' ')), log: (...a) => logs.push(a.join(' ')), error: (...a) => logs.push('[error] ' + a.join(' ')), warn: (...a) => logs.push('[warn] ' + a.join(' ')) };
g.alert = m => logs.push('[alert] ' + m);
const moves = ['1,1', '0,0', '2,2', '0,2', '2,0', '1,0', '0,1', '2,1', '1,2'];
let pi = 0;
g.prompt = () => (pi < moves.length ? moves[pi++] : null);  // scripted moves, then null
let runtime = 'Ran without runtime errors.';
const errs = [];
g.addEventListener('error', e => errs.push(e.message));
try {
  const fn = new Function('window', 'document', 'console', 'alert', 'prompt', 'require', 'module', 'exports', js);
  const mod = { exports: {} };
  fn(g, g.document, fakeConsole, g.alert, g.prompt, require, mod, mod.exports);
  g.document.dispatchEvent(new g.Event('DOMContentLoaded'));
  g.dispatchEvent(new g.Event('load'));
} catch (e) { runtime = `Runtime error: ${e && e.message}`; }
out.push(runtime);
if (pi) out.push(`prompt() was answered with ${pi} scripted moves.`);
// play by clicking: click up to 5 board-looking elements and report what changed
const clickable = [...g.document.querySelectorAll('button, td, .cell, [data-index], [data-cell], #board > *, .board > *')];
if (clickable.length) {
  const before = g.document.body.textContent.replace(/\s+/g, ' ').trim();
  let clickErr = null;
  for (const el of clickable.slice(0, 5)) {
    try { el.dispatchEvent(new g.MouseEvent('click', { bubbles: true })); } catch (e) { clickErr = e.message; break; }
  }
  const after = g.document.body.textContent.replace(/\s+/g, ' ').trim();
  out.push(`Clicked ${Math.min(5, clickable.length)} of ${clickable.length} clickable elements. ` +
    (clickErr ? `Click handler error: ${clickErr}` : before === after ? 'Page text did NOT change after clicking.' : 'Page text changed after clicking.'));
  out.push(`Page text now: "${after.slice(0, 200)}"`);
  const cnt = (s, ch) => (s.match(new RegExp(ch, 'g')) || []).length;
  if (process.env.SCORE) out.push(`SCORE_MARKS X:${cnt(after, 'X') - cnt(before, 'X')} O:${cnt(after, 'O') - cnt(before, 'O')}`);
} else if (g.document.body.querySelectorAll('*').length <= 1 && !logs.length) {
  out.push('The page has no board elements (nothing was added to the DOM).');
}
if (errs.length) out.push('Errors in event handlers: ' + errs.slice(0, 3).join(' | '));
if (logs.length) { out.push(`Console output (${logs.length} lines, first 15):`); out.push(...logs.slice(0, 15).map(l => '  ' + l.slice(0, 120))); }
const html = g.document.body.innerHTML;
if (html.length > 40) out.push(`Page has ${g.document.body.querySelectorAll('*').length} elements after running.`);
console.log(out.join('\n').slice(0, 1200));
process.exit(0);
