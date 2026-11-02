// node outline.mjs <file.ts>  -> JSON outline of top-level declarations (tolerates broken code)
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');

const file = process.argv[2];
const text = fs.readFileSync(file, 'utf8');
const sf = ts.createSourceFile(file, text, ts.ScriptTarget.ES2020, true, ts.ScriptKind.TS);
const lineOf = pos => sf.getLineAndCharacterOfPosition(pos).line + 1;
const out = { functions: [], vars: [], types: [], ids: [], todos: [], lines: text.split('\n').length };

function sigOf(node, name) {
  const params = node.parameters.map(p => p.getText(sf)).join(', ');
  const ret = node.type ? ': ' + node.type.getText(sf) : '';
  return `${name}(${params})${ret}`;
}
function bodyInfo(body) {
  if (!body) return { todo: true };
  const inner = text.slice(body.getStart(sf) + 1, body.end - 1);
  const stripped = inner.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').trim();
  return { todo: stripped === '' || /TODO/.test(inner) && stripped.length < 20,
           bodyStart: body.getStart(sf), bodyEnd: body.end };
}
function leadingComment(node) {
  const r = ts.getLeadingCommentRanges(text, node.getFullStart()) || [];
  return r.map(c => text.slice(c.pos, c.end).replace(/^\/\/\s?|^\/\*+|\*+\/$/g, '').trim()).join(' ').slice(0, 120);
}

for (const st of sf.statements) {
  if (ts.isFunctionDeclaration(st) && st.name) {
    out.functions.push({ name: st.name.text, sig: sigOf(st, st.name.text), line: lineOf(st.getStart(sf)), nodeStart: st.getStart(sf),
      start: st.getFullStart(), end: st.end, comment: leadingComment(st), ...bodyInfo(st.body) });
  } else if (ts.isVariableStatement(st)) {
    for (const d of st.declarationList.declarations) {
      const name = d.name.getText(sf);
      const init = d.initializer;
      if (init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))) {
        out.functions.push({ name, sig: sigOf(init, name), line: lineOf(st.getStart(sf)), nodeStart: st.getStart(sf), start: st.getFullStart(), end: st.end,
          comment: leadingComment(st), ...(ts.isBlock(init.body) ? bodyInfo(init.body) : { todo: false }) });
      } else {
        const kind = st.declarationList.flags & ts.NodeFlags.Const ? 'const' : 'let';
        const type = d.type ? d.type.getText(sf) : (init ? '= ' + init.getText(sf).replace(/\s+/g, ' ').slice(0, 60) : '');
        out.vars.push({ name, start: st.getFullStart(), end: st.end, decl: `${kind} ${name}${d.type ? ': ' + type : ' ' + type}`, line: lineOf(st.getStart(sf)), comment: leadingComment(st) });
      }
    }
  } else if (ts.isTypeAliasDeclaration(st) || ts.isInterfaceDeclaration(st) || ts.isEnumDeclaration(st)) {
    out.types.push({ name: st.name.text, text: st.getText(sf).replace(/\s+/g, ' ').slice(0, 160), line: lineOf(st.getStart(sf)) });
  }
}
const idRe = /(?:id\s*=\s*["'`]|getElementById\(\s*["'`]|\.id\s*=\s*["'`]|querySelector\(\s*["'`]#)([\w-]+)/g;
let m; const ids = new Set();
while ((m = idRe.exec(text))) ids.add(m[1]);
out.ids = [...ids];
text.split('\n').forEach((l, i) => { if (/TODO/.test(l)) out.todos.push(i + 1); });
console.log(JSON.stringify(out));
