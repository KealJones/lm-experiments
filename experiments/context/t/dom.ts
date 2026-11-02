const app = document.getElementById('app')!;
let turn = 'X';
for (let i = 0; i < 9; i++) { const b = document.createElement('button'); b.className='cell'; b.addEventListener('click', () => { if (i === 4) (null as any).boom(); b.textContent = turn; turn = turn === 'X' ? 'O' : 'X'; }); app.appendChild(b); }
