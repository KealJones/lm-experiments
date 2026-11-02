const board = ['', '', ''];
const boardDiv = document.getElementById('board');
const currentPlayer = 'X';
let score = 0;

function checkWin() {
  // Check rows
  for (let i = 0; i < 3; i += 1) {
    if (board[i][0] === board[i][1] && board[i][1] === board[i][2]) {
      return true;
    }
  } 
  // Check columns
  for (let j = 0; j < 3; j += 1) {
    if (board[0][j] === board[1][j] && board[1][j] === board[2][j]) {
      return true;
    }
  } 
  // Check diagonals
  if (board[0][0] === board[1][1] && board[1][1] === board[2][2]) {
    return true;
  } else if (board[0][2] === board[1][1] && board[1][1] === board[2][0]) {
    return true;
  }
  return false;
}

function getMove() {
  // Check if the current player has a move
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      if (board[i][j] === '') {
        return [i, j];
      }
    }
  }
  return [-1, -1];
}

function minimax(board, depth, isMaximizing) {
  if (checkWin()) {
    return [0, 0];
  }
  if (depth === 2) {
    return [0, 0];
  }
  let bestMove = [-1, -1];
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      if (board[i][j] === '') {
        board[i][j] = isMaximizing ? 'X' : 'O';
        const move = getMove();
        bestMove = minimax(board, depth + 1, !isMaximizing);
        board[i][j] = '';
        if (bestMove[0] !== -1) {
          return bestMove;
        }
      }
    }
  }
  return bestMove;
}

// Initialize game
boardDiv.innerHTML = '';
for (let i = 0; i < 9; i++) {
  const cell = document.createElement('td');
  cell.textContent = '';
  boardDiv.appendChild(cell);
  board[i][0] = cell;
  board[i][1] = cell;
  board[i][2] = cell;
}

// Start game
function startGame() {
  const move = minimax(board, 0, true);
  if (move[0] !== -1) {
    board[move[0]][move[1]].textContent = 'X';
    score += 1;
    updateScore();
    document.getElementById('restart').addEventListener('click', () => startGame());
  }
}

// Update score
function updateScore() {
  document.getElementById('score').textContent = score;
}

// Restart game
document.getElementById('restart').addEventListener('click', startGame);