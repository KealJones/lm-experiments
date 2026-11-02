// Tic Tac Toe Game

const board: string[][] = [
  [' ', ' ', ' '],
  [' ', ' ', ' '],
  [' ', ' ', ' ']
];

function printBoard() {
  for (let row of board) {
    console.log(row.join(' | '));
  }
}

function makeMove(board, player, position) {
  const [row, col] = position;
  if (board[row][col] === ' ') {
    board[row][col] = player;
    return true;
  }
  return false;
}

function isWinner(player) {
  // Check rows
  for (let i = 0; i < 3; i++) {
    if (board[i][0] === player && board[i][1] === player && board[i][2] === player) {
      return true;
    }
  }

  // Check columns
  for (let j = 0; j < 3; j++) {
    if (board[0][j] === player && board[1][j] === player && board[2][j] === player) {
      return true;
    }
  }

  // Check diagonals
  if (board[0][0] === player && board[1][1] === player && board[2][2] === player) {
    return true;
  }
  if (board[0][2] === player && board[1][1] === player && board[2][0] === player) {
    return true;
  }

  return false;
}

function isDraw() {
  for (let row of board) {
    if (row.every(cell => cell === ' ')) {
      return false;
    }
  }
  return true;
}

// Game loop
function startGame() {
  const currentPlayer = 'X';
  printBoard();

  while (!isDraw()) {
    const position = prompt("Enter your move (row, column):");
    if (!position) break;

    const [row, col] = position.split(',');
    const result = makeMove(board, currentPlayer, [row, col]);

    if (result) {
      printBoard();
      if (isWinner(currentPlayer)) {
        alert(`Player ${currentPlayer} wins!`);
        break;
      }
      currentPlayer = currentPlayer === 'X' ? 'O' : 'X';
    } else {
      alert("Invalid move. Try again.");
    }
  }

  printBoard();
}

startGame();
