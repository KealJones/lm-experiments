type Cell = 'X' | 'O' | '';
let board: Cell[] = Array(9).fill('');
const score = { you: 0, computer: 0 };
const app = document.getElementById('app')!;
const LINES = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
function winner(b: Cell[]): Cell | 'draw' | null {
  for (const [a, c, d] of LINES) if (b[a] && b[a] === b[c] && b[a] === b[d]) return b[a];
  return b.every(x => x) ? 'draw' : null;
}
function minimax(b: Cell[], turn: Cell): number {
  const w = winner(b);
  if (w === 'O') return 1; if (w === 'X') return -1; if (w === 'draw') return 0;
  const scores = b.map((x, i) => { if (x) return null; b[i] = turn; const s = minimax(b, turn === 'O' ? 'X' : 'O'); b[i] = ''; return s; }).filter(s => s !== null) as number[];
  return turn === 'O' ? Math.max(...scores) : Math.min(...scores);
}
function bestMove(b: Cell[]): number {
  let best = -2, move = -1;
  b.forEach((x, i) => { if (!x) { b[i] = 'O'; const s = minimax(b, 'X'); b[i] = ''; if (s > best) { best = s; move = i; } } });
  return move;
}
function render(): void {
  app.innerHTML = `<div id="score">You ${score.you} - Computer ${score.computer}</div>`;
  board.forEach((c, i) => { const b = document.createElement('button'); b.className = 'cell'; b.textContent = c; b.onclick = () => play(i); app.appendChild(b); });
  const r = document.createElement('button'); r.id = 'restart'; r.textContent = 'Restart'; r.onclick = () => { board = Array(9).fill(''); render(); }; app.appendChild(r);
}
function play(i: number): void {
  // TODO
}
render();
