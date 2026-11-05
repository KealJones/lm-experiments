// Game setup
const board = document.getElementById('board');
const boardWidth = 3;
const boardHeight = 3;

// Initialize board with empty cells
const boardArray = Array.from({ length: boardWidth * boardHeight }, (_, i) => {
  return {
    cell: i,
    value: '',
    isComputer: false,
    isHuman: false,
    isAI: false,
    color: 'white'
  };
});

// Score counter
let score = 0;
let scoreCounter = 0;

// Computer opponent (minimax)
const computerPlayer = {
  isComputer: true,
  isHuman: false,
  value: 0,
  bestMove: null,
  isAI: true,
  isMinimax: true
};

// Function to draw the board
drawBoard() { 
  board.innerHTML = boardArray.map((cell, index) => {
    if (cell === 'X') {
      return `<div class="cell" id="cell-${index}" data-cell="X">X</div>`;
    } else if (cell === 'O') {
      return `<div class="cell" id="cell-${index}" data-cell="O">O</div>`;
    } else {
      return `<div class="cell" id="cell-${index}" data-cell=""></div>`;
    }
  });
}

// Function to check if a cell is empty
function isCellEmpty(cell) {
  // TODO
}

// Function to check if the current player can make a move
function canMove(cell) {
  // Check if the cell is empty
  if (boardArray[cell[0]][cell[1]] !== undefined) {
    return false;
  }
  return true;
}}

// Function to handle a click event
handleClick(e) {
  const cell = e.target;
  if (canMove(cell)) {
    if (computerPlayer.isComputer) {
      // Computer moves
      const bestMove = computerPlayer.bestMove;
      if (bestMove) {
        cell.textContent = computerPlayer.value;
      } else {
        cell.textContent = 'X';
      }
    } else {
      cell.textContent = 'O';
    }
  } else {
    cell.textContent = ' ';
  }
}}

// Function to check if a player has won
function checkWin(player) {
  // Check rows
  for (let i = 0; i < 3; i++) {
    if (boardArray[i][0] === player && boardArray[i][1] === player && boardArray[i][2] === player) {
      return true;
    }
  }
  // Check columns
  for (let i = 0; i < 3; i++) {
    if (boardArray[0][i] === player && boardArray[1][i] === player && boardArray[2][i] === player) {
      return true;
    }
  }
  // Check diagonals
  if (boardArray[0][0] === player && boardArray[1][1] === player && boardArray[2][2] === player) {
    return true;
  } else if (boardArray[0][2] === player && boardArray[1][1] === player && boardArray[2][0] === player) {
    return true;
  }
  return false;
}

// Function to handle restart button
function restartGame() {
  // TODO
}

// Function to start the game
function startGame() {
  // TODO
}

// Initialize the game
startGame();