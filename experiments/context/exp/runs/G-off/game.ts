const board = document.createElement('div');
board.id = 'tic-tac-toe-board';
board.className = 'board';

document.body.appendChild(board);

const boardElement = board;
const boardRows = boardElement.querySelectorAll('.cell');

const game = {
  board: boardElement,
  rows: boardRows,
  isGameRunning: false,
  score: {
    player1: 0,
    player2: 0
  },
  restartButton: document.createElement('button'), 
  restartButton.textContent = 'Restart Game'

};

// Initialize game
game.initialize();

function initialize() {
  game.isGameRunning = true;
  game.score.player1 = 0;
  game.score.player2 = 0;

  // Set up board
  for (let i = 0; i < 9; i++) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.addEventListener('click', () => game.handleClick(i));
    boardElement.appendChild(cell);
  }

  // Add restart button
  game.restartButton.addEventListener('click', () => game.resetGame());
  game.restartButton.textContent = 'Restart Game';
  boardElement.appendChild(game.restartButton);
}

function handleClick(index) {
  if (game.isGameRunning && game.rows[index].textContent !== ' ') {
    game.rows[index].textContent = 'X';
    game.score.player1++;
    game.checkWin();
  }
}

function checkWin() {
  // Check rows
  for (let i = 0; i < 3; i++) {
    if (game.rows[i].textContent === game.rows[i + 1].textContent && game.rows[i + 1].textContent === game.rows[i + 2].textContent) {
      game.score.player1++;
      game.score.player2--;
      game.isGameRunning = false;
      return;
    }
  }

  // Check columns
  for (let i = 0; i < 3; i++) {
    if (game.rows[i].textContent === game.rows[i + 3].textContent && game.rows[i + 3].textContent === game.rows[i + 6].textContent) {
      game.score.player1++;
      game.score.player2--;
      game.isGameRunning = false;
      return;
    }
  }

  // Check diagonals
  if (game.rows[0].textContent === game.rows[2].textContent && game.rows[2].textContent === game.rows[4].textContent) {
    game.score.player1++;
    game.score.player2--;
    game.isGameRunning = false;
    return;
  }
  if (game.rows[0].textContent === game.rows[6].textContent && game.rows[6].textContent === game.rows[2].textContent) {
    game.score.player1++;
    game.score.player2--;
    game.isGameRunning = false;
    return;
  }

  // No win, check for draw
  if (game.rows.every(cell => cell.textContent !== ' ')) {
    game.score.player1++;
    game.score.player2++;
    game.isGameRunning = false;
  }
}

function resetGame() {
  game.isGameRunning = false;
  game.rows.forEach(row => row.textContent = ' ');
  game.score.player1 = 0;
  game.score.player2 = 0;
}

// Start the game
game.initialize();