const board = document.getElementById('board');
const score = document.getElementById('score');
const restartBtn = document.getElementById('restart');

// Initialize board
const boardCells = Array(9)
  .fill(null)
  .map(() => Array(3).fill(''));

// Game state
let currentPlayer = 'X';
let xScore = 0;
let oScore = 0;

// Minimax algorithm
function minimax(board, depth, isMaximizing, memo) {
  if (memo[board] !== undefined) return memo[board];
  
  if (isMaximizing) {
    let bestMove = null;
    for (let i = 0; i < 9; i++) {
      if (board[i] === null) {
        const move = board.slice().map((cell, idx) => cell === null ? i : cell);
        const result = minimax(move, depth + 1, !isMaximizing, memo);
        if (result > bestMove) {
          bestMove = i;
        }
      }
    }
    return bestMove;
  } else {
    let bestMove = null;
    for (let i = 0; i < 9; i++) {
      if (board[i] === null) {
        const move = board.slice().map((cell, idx) => cell === null ? i : cell);
        const result = minimax(move, depth, !isMaximizing, memo);
        if (result < bestMove) {
          bestMove = i;
        }
      }
    }
    return bestMove;
  }
}

// Update board and scores
function updateBoard() {
  board.innerHTML = '';
  for (let i = 0; i < 9; i++) {
    const cell = document.createElement('div');
    cell.textContent = board[i];
    board.appendChild(cell);
  }
}

// Start game
function startGame() {
  restartBtn.textContent = 'Restart';
  board.innerHTML = '  X  X  X  ';
  xScore = 0;
  oScore = 0;
  currentPlayer = 'X';
}

// Restart game
function restartGame() {
  board.innerHTML = '';
  xScore = 0;
  oScore = 0;
  currentPlayer = 'X';
  restartBtn.textContent = 'Restart';
}

// Handle user input
board.addEventListener('click', (e) => {
  const cell = document.querySelector(`[cell='${e.target.textContent}']`);
  if (cell && cell.textContent === 'X' || cell.textContent === 'O') return;
  
  cell.textContent = currentPlayer;
  cell.textContent = (cell.textContent === 'X' ? 'X' : 'O');
  
  updateBoard();
  if (currentPlayer === 'X') xScore++;
  else oScore++;
});

// Game loop
function gameLoop() {
  const boardCells = Array(9)
    .fill(null)
    .map(() => Array(3).fill(''));
  
  // Check for win
  const isWinner = (currentPlayer, board) => {
    return [
      [board[0][0], board[0][1], board[0][2]],
      [board[1][0], board[1][1], board[1][2]],
      [board[2][0], board[2][1], board[2][2]],
    ].some(([row]) => row.every(cell => cell === currentPlayer));
  };
  
  // Check for draw
  const isDraw = board.every(cell => cell !== null);
  
  // Check for game over
  if (isWinner(currentPlayer, board) || isDraw) {
    restartGame();
    return;
  }
  
  // Check minimax for optimal move
  const bestMove = minimax(board, 0, false, { [board]: false });
  if (bestMove !== null) {
    boardCells[bestMove] = 'X';
    board.innerHTML = '';
    updateBoard();
    updateScore();
  }
}

// Start the game
startGame();
gameLoop();