const board = document.createElement('div');
board.innerHTML = `
  <div class="cell" id="cell00"></div>
  <div class="cell" id="cell01"></div>
  <div class="cell" id="cell02"></div>
  <div class="cell" id="cell03"></div>
  <div class="cell" id="cell04"></div>
  <div class="cell" id="cell05"></div>
  <div class="cell" id="cell06"></div>
  <div class="cell" id="cell07"></div>
  <div class="cell" id="cell08"></div>

const boardElement = document.getElementById('board');
boardElement.appendChild(board);

const cellDivs = document.querySelectorAll('.cell');
for (let i = 0; i < 9; i++) {
  cellDivs[i].addEventListener('click', () => {
    const cell = document.getElementById(`${i + 100 + i % 3}`);
    cell.textContent = 'X' if player === 'O' else 'O';
  });

const currentPlayer = 'X';
function minimax(board, depth, isMaximizer) {
  if (isMaximizer) {
    let bestMove = null;
    for (let i = 0; i < 9; i++) {
      const state = board.copy();
      state[i] = player;
      const result = minimax(...);
      if (result > bestMove) {
        bestMove = i;
      }
    }
    return bestMove;
  } else {
    let bestMove = null;
    for (let i = 0; i < 9; i++) {
      const state = board.copy();
      state[i] = player;
      const result = minimax(...);
      if (result < bestMove) {
        bestMove = i;
      }
    }
    return bestMove;
  }
}

const restartButton = document.createElement('button');
restartButton.textContent = 'Restart';
restartButton.addEventListener('click', () => {
  board.textContent = '  X  O  X  X  X  O  X  X  
  X  X  X  O  X  X  X  O  X  
  X  X  X  O  X  X  X  O  X  
';
  boardElement.textContent = 'Score: 0/0';
  document.getElementById('restart').textContent = 'Restart';
});

boardElement.appendChild(restartButton);
