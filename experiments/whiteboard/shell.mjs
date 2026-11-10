// Squiggle's bash tool for the replay: just-bash (Squiggle's vendored build at PR 7, fetched by the job) with one
// in-memory filesystem per chat, a fresh shell per command starting in /home (as tools/bash.js does).
// Reads JSON lines {id, chat, cmd} on stdin, writes {id, stdout, stderr, exitCode} on stdout.
// Squiggle's custom commands: man and bc work; git, gh, curl, search, wiki and node say there is no network or
// sandbox in this test (the original context-packets answerers had no web either).
import { Bash, InMemoryFs, defineCommand } from './just-bash.js';
import readline from 'node:readline';

const HELP_ALL = `Custom commands here (each has --help):
  git      clone, status, log, show <commit>:<path>, checkout/switch/branch <name>, add, commit -m, push, pull
  gh       gh repo list (your GitHub repos), gh repo clone, gh pr create
  curl     curl URL: a web page as readable text (pipe it: curl URL | grep -i word)
  search   search WORDS: web search results with links
  wiki     wiki NAME: Wikipedia and Wikidata facts about something
  node     node -e CODE: run JavaScript
  bc       echo "5*5/129" | bc -l: maths with decimals and %
Everything else is ordinary bash: cat, ls, grep, sed, awk, find, head, tail, wc, sort, jq, pipes, loops.
Files: /home (yours, synced to the user's devices), /repos/<name> (git clones), /web (saved pages), /tmp.`;

const offline = (name) => defineCommand(name, async () => ({ stdout: '', stderr: `${name}: not available in this test (no network)\n`, exitCode: 1 }));
const man = defineCommand('man', async () => ({ stdout: HELP_ALL + '\n', stderr: '', exitCode: 0 }));
// bc: decimals, $ and thousands commas, x% (Squiggle's calc.js does the same kinds of input).
const bc = defineCommand('bc', async (argv, ctx) => {
  const exprs = String(ctx.stdin || argv.filter(a => !a.startsWith('-')).join(' ')).split(/[\n;]+/).map(s => s.trim()).filter(Boolean);
  if (!exprs.length) return { stdout: '', stderr: 'usage: echo "2.5 * 4" | bc -l\n', exitCode: 1 };
  const out = [];
  for (let e of exprs) {
    e = e.replace(/\$/g, '').replace(/(\d),(?=\d{3}\b)/g, '$1').replace(/(\d+(?:\.\d+)?)\s*%\s*of\s*/gi, '($1/100)*').replace(/(\d+(?:\.\d+)?)%/g, '($1/100)').replace(/\^/g, '**').replace(/sqrt/g, 'Math.sqrt');
    if (!/^[\d\s+\-*/().,a-zA-Z_]*$/.test(e) || /[a-zA-Z_]/.test(e.replace(/Math\.sqrt/g, ''))) return { stdout: '', stderr: `bc: can't read ${e}\n`, exitCode: 1 };
    try { const v = Function(`"use strict"; return (${e});`)(); out.push(String(Math.round(v * 1e10) / 1e10)); }
    catch (err) { return { stdout: '', stderr: `bc: ${err.message}\n`, exitCode: 1 }; }
  }
  return { stdout: out.join('\n') + '\n', stderr: '', exitCode: 0 };
});
const custom = [man, bc, ...['git', 'gh', 'curl', 'search', 'wiki', 'node'].map(offline)];

const fss = new Map();
async function fsFor(chat) {
  if (!fss.has(chat)) {
    const fs = new InMemoryFs();
    for (const d of ['/home', '/repos', '/web', '/tmp']) await fs.mkdir(d, { recursive: true });
    fss.set(chat, fs);
  }
  return fss.get(chat);
}

const rl = readline.createInterface({ input: process.stdin });
for await (const line of rl) {
  if (!line.trim()) continue;
  const { id, chat, cmd } = JSON.parse(line);
  let r;
  try {
    const shell = new Bash({ fs: await fsFor(chat), cwd: '/home', customCommands: custom,
      executionLimits: { maxExecutionTimeMs: 20000, maxOutputSize: 200000 } });
    r = await shell.exec(String(cmd));
  } catch (e) { r = { stdout: '', stderr: String(e && e.message || e), exitCode: 1 }; }
  process.stdout.write(JSON.stringify({ id, stdout: String(r.stdout || ''), stderr: String(r.stderr || ''), exitCode: r.exitCode ?? 1 }) + '\n');
}
