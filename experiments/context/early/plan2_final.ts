// ---- step 1 ----
const board = document.createElement('div');
board.className = 'board';
board.innerHTML = `
  <div id="cell-0"></div>
  <div id="cell-1"></div>
  <div id="cell-2"></div>
  <div id="cell-3"></div>
  <div id="cell-4"></div>
  <div id="cell-5"></div>
  <div id="cell-6"></div>
  <div id="cell-7"></div>
  <div id="cell-8"></div>
`;
document.body.appendChild(board);

// ---- step 2 ----
function minimax(board: number[][]): number {
  // Check if the current board has a winning condition
  for (let i = 0; i < 9; i++) {
    const row = board[i];
    if (row.includes(board[i])) {
      return i;
    }
  }

  // Check all possible moves for the computer
  for (let i = 0; i < 9; i++) {
    if (board[i] === 2 && checkWin(board, 2, i)) {
      return i;
    }
  }

  return -1; // No winning move found
}

function checkWin(board: number[], symbol: number, index: number): boolean {
  // Check rows
  for (let i = 0; i < 3; i++) {
    if (board[i * 3] === symbol && board[i * 3 + 1] === symbol && board[i * 3 + 2] === symbol) {
      return true;
    }
  }

  // Check columns
  for (let i = 0; i < 3; i++) {
    if (board[i * 3] === symbol && board[i * 3 + 3] === symbol && board[i * 3 + 6] === symbol) {
      return true;
    }
  }

  // Check diagonals
  if (board[0] === symbol && board[1] === symbol && board[2] === symbol) return true;
  if (board[3] === symbol && board[4] === symbol && board[5] === symbol) return true;
  if (board[6] === symbol && board[7] === symbol && board[8] === symbol) return true;

  return false;
}

// ---- step 3 ----
// Initialize the board elements with their IDs
const board = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8]
];

// Define functions for minimax and check win
function minimax(board: number[][]): number[] {
  // Placeholder for minimax logic
  return [];
}

function checkWin(board: number[], symbol: number, index: number): boolean {
  // Placeholder for win condition check
  return false;
}

// Game loop to handle turns and check for winning conditions
function gameLoop() {
  // Check if a move has been made
  if (board[i] && board[i].some(cell => cell === symbol)) {
    // Place the symbol on the board
    board[i].forEach((cell, idx) => {
      if (cell === symbol) {
        board[i][idx] = symbol;
      }
    });
    
    // Check for win
    const win = checkWin(board, symbol, i);
    if (win) {
      // Update score and display win
      updateScore();
      return;
    }
    
    // Check if it's a restart
    if (i === 8) {
      restartGame();
    }
  }
}

// Start the game loop
gameLoop();

// ---- step 4 ----
// Initialize score counter and create restart button element
const board = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8]
];

const restartButton = document.createElement('div');
restartButton.id = '#restart';
restartButton.textContent = 'Restart';

document.getElementById('cell-0').textContent = board[0][0];
document.getElementById('cell-1').textContent = board[0][1];
document.getElementById('cell-2').textContent = board[0][2];
document.getElementById('cell-3').textContent = board[1][0];
document.getElementById('cell-4').textContent = board[1][1];
document.getElementById('cell-5').textContent = board[1][2];
document.getElementById('cell-6').textContent = board[2][0];
document.getElementById('cell-7').textContent = board[2][1];
document.getElementById('cell-8').textContent = board[2][2];

// Add restart button
document.body.appendChild(restartButton);