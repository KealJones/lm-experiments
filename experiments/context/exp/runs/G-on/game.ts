const board = [
  [' ', ' ', ' '],
  [' ', ' ', ' '],
  [' ', ' ', ' ']
];

const boardElement = document.getElementById('board');
const scoreElement = document.getElementById('score');
const restartButton = document.getElementById('restart');

function renderBoard() {
  boardElement.innerHTML = '';
  board.forEach((row, index) => {
    row.forEach(cell => {
      const cellElement = document.createElement('div');
      cellElement.textContent = cell;
      boardElement.appendChild(cellElement);
    });
  });
}

function updateScore(player) {
  if (player === 'X') {
    scoreElement.textContent = 'X';
  } else {
    scoreElement.textContent = 'O';
  }
}

function checkWin() {
  const winningConditions = [
    [0, 1, 2], [0, 2, 1], [1, 0, 3], [1, 3, 5], [2, 1, 4], [2, 4, 6], [3, 5, 7], [3, 7, 9],
    [4, 5, 6]
  ];
  
  winningConditions.forEach(([rowIndex, colIndex]) => {
    const cell = board[rowIndex][colIndex];
    if (cell === 'X' || cell === 'O') {
      for (let i = 0; i < 3; i++) {
        const cellAt = [rowIndex + i, colIndex];
        if (board[cellAt[0]][cellAt[1]] === cell) {
          // Check if this is a win
          updateScore(cell);
          boardElement.classList.add('win');
          boardElement.classList.remove('loss');
          return;
        }
      }
    }
  });
}

function minimax(board, depth, player) {
  if (player === 'X') {
    const best = -Infinity;
    for (let i = 0; i < 9; i++) {
      const cell = board[i];
      if (cell[0] === ' ') {
        board[i][0] = 'X';
        best = Math.max(best, minimax(board, depth + 1, 'O'));
        board[i][0] = ' ';
      }
    }
    return best;
  } else {
    const best = Infinity;
    for (let i = 0; i < 9; i++) {
      const cell = board[i];
      if (cell[0] === ' ') {
        board[i][0] = 'O';
        best = Math.min(best, minimax(board, depth + 1, 'X'));
        board[i][0] = ' ';
      }
    }
    return best;
  }
}

function playGame() {
  renderBoard();
  restartButton.addEventListener('click', () => {
    board.fill([' ', ' ', ' ']);
    updateScore(' ');
    renderBoard();
  });
}

renderBoard();
playGame();