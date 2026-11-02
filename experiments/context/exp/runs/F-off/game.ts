const board = document.getElementById('board');
const startButton = document.getElementById('start-button');

// Initialize board
function createBoard() {
  board.innerHTML = '';
  for (let row = 0; row < 3; row++) {
    const rowEl = document.createElement('div');
    rowEl.className = 'board-cell';
    rowEl.innerHTML = ' ';
    board.appendChild(rowEl);
  }
}

// Initialize board
createBoard();

// Set up the start button
startButton.addEventListener('click', () => {
  createBoard();
  board.textContent = 'Player 1';
  board.textContent += ' vs. ';
  board.textContent += 'Player 2';
});

// Minimax algorithm for AI
function minimax(board, depth, isMaximizing, memo) {
  if (isMaximizing) {
    // Try all possible moves
    let max = -Infinity;
    for (let cell = 0; cell < 9; cell++) {
      const [row, col] = cell;
      const cellValue = board[row][col];
      const move = () => {
        if (cellValue === 'X' || cellValue === 'O') {
          return;
        }
        board[row][col] = 'X';
        max = Math.max(max, minimax(board, depth + 1, !isMaximizing, memo));
        board[row][col] = 'O';
      };
      move();
    }
    return max;
  }

  // Try all possible moves
  let min = Infinity;
  for (let cell = 0; cell < 9; cell++) {
    const [row, col] = cell;
    const cellValue = board[row][col];
    const move = () => {
      if (cellValue === 'X' || cellValue === 'O') {
        return;
      }
      board[row][col] = 'X';
      min = Math.min(min, minimax(board, depth + 1, !isMaximizing, memo));
      board[row][col] = 'O';
    };
    move();
  }
  return min;
}

// Get the board
function getBoard() {
  let boardValue = '';
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 3; col++) {
      boardValue += board[row][col];
    }
    boardValue += ' ';
  }
  return boardValue;
}

// Update the board
function updateBoard(value) {
  let boardValue = getBoard();
  boardValue = boardValue.replace(/[^a-zA-Z]/g, '');
  boardValue = boardValue.replace(/\s+/g, '');
  board.innerHTML = boardValue;
  board.textContent = value;
}

// Game logic
let currentPlayer = 'X';
let boardValue = '';
let score = { x: 0, o: 0 };

// Get the board
function getBoard() {
  let boardValue = '';
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 3; col++) {
      boardValue += board[row][col];
    }
    boardValue += ' ';
  }
  return boardValue;
}

// Update the board
function updateBoard(value) {
  let boardValue = getBoard();
  boardValue = boardValue.replace(/[^a-zA-Z]/g, '');
  boardValue = boardValue.replace(/\s+/g, '');
  board.innerHTML = boardValue;
  board.textContent = value;
}

// Start game
startButton.addEventListener('click', () => {
  createBoard();
  board.textContent = 'Player 1';
  board.textContent += ' vs. ';
  board.textContent += 'Player 2';
});

// Check for win
function checkWin() {
  const winningConditions = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],
    [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6]
  ];
  for (const win of winningConditions) {
    const [r, c] = win;
    if (board[r][c] === currentPlayer && board[r][c] !== 'X' && board[r][c] !== 'O') {
      return true;
    }
  }
  return false;
}

// Check for tie
function checkTie() {
  for (let i = 0; i < 9; i++) {
    if (board[i] === ' ') {
      return false;
    }
  }
  return true;
}

// Update the score
function updateScore() {
  if (currentPlayer === 'X') {
    score.x++;
  } else {
    score.o++;
  }
  board.textContent = score.x + ' x' + score.o;
}

// Game loop
function gameLoop() {
  if (checkWin()) {
    alert('Player ' + currentPlayer + ' wins!');
    board.textContent = 'Player ' + currentPlayer + ' wins!';
    return;
  } else if (checkTie()) {
    alert('It is a draw!');
    board.textContent = 'It is a draw!';
    return;
  }
  updateBoard(boardValue);
  updateScore();
  gameLoop();
}

// Game state
let gameRunning = false;

// Handle restart
function restartGame() {
  createBoard();
  board.textContent = 'Player 1';
  board.textContent += ' vs. ';
  board.textContent += 'Player 2';
  gameRunning = true;
}

// Start the game
startButton.addEventListener('click', () => {
  gameRunning = true;
  gameLoop();
});

// Initialize the game
createBoard();
updateBoard(' ');
updateScore();
restartGame();