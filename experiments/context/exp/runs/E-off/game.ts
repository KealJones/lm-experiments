const board = [['', '', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', '']];

const cell = document.getElementById('cell');

function playMove(row, col) {
  if (board[row][col] === '') {
    cell.innerHTML = 'X';
    board[row][col] = 'X';
    return true;
  }
  return false;
}

function checkWin() {
  const winConditions = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],
    [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6]
  ];
  for (const win of winConditions) {
    if (board[win[0]][win[1]] === board[win[0]][win[2]] && board[win[0]][win[1]] === board[win[0]][win[2]]) {
      return true;
    }
  }
  return false;
}

function isFull() {
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 3; col++) {
      if (board[row][col] === '') {
        return false;
      }
    }
  }
  return true;
}

function restartBoard() {
  board = [['', '', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', '']];
  document.getElementById('cell').innerHTML = 'X';
}

const game = new Game();

document.addEventListener('click', (event) => {
  const row = Math.floor(event.target.row / 3);
  const col = event.target.col;
  if (game.playMove(row, col)) {
    game.checkWin();
    game.isFull();
    if (game.checkWin() && game.isFull()) {
      game.restartBoard();
    }
  } else if (game.isFull()) {
    alert('It is a draw!');
  } else {
    game.checkWin();
  }
});