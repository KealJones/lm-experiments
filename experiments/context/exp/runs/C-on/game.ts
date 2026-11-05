// board: 3x3 grid of strings
let board: string[] = [
  "   ", "   ", "   ",
  "   ", "   ", "   ",
  "   ", "   ", "   "
];

// minimax function to find best move for computer
function minimax(board, player) {
  // Check if this is a winning position
  let bestMove = null;
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      // Check if placing player's symbol here leads to a win
      if (checkWin(board, player, i, j)) {
        return [i, j]; // Return the move and symbol
      }
    }
  }

  // If no winning move found, check for losing positions
  for (let i = 0; i < 3; i++) {
    for (let j = 0;
      j < 3 && (i === 0 || j === 0 || i === 2 || j === 2); 
      j++) {
      // Check if placing player's symbol here leads to a loss
      if (checkLose(board, player, i, j)) {
        return [i, j]; // Return the move and symbol
      }
    }
  }

  // If no winning or losing move found, return -1
  return [-1, -1];
}

function checkWin(board, player, i, j) {
  // Check rows
  if (board[i][0] === player && board[i][1] === player && board[i][2] === player) {
    return true;
  }
  
  // Check columns
  if (board[0][i] === player && board[1][i] === player && board[2][i] === player) {
    return true;
  }
  
  // Check diagonals
  if (board[0][0] === player && board[1][1] === player && board[2][2] === player) {
    return true;
  }
  
  return false;
}

function checkLose(board, player, i, j) {
  // Check rows
  if (board[i][0] === player && board[i][1] === player && board[i][2] === player) {
    return false;
  }
  
  // Check columns
  if (board[0][i] === player && board[1][i] === player && board[2][i] === player) {
    return false;
  }
  
  // Check diagonals
  if (board[0][0] === player && board[1][1] === player && board[2][2] === player) {
    return false;
  }
  
  return true;
}

// game is over
function gameIsOver(board) {
  // Check if board is full
  if (board.length === 9) {
    // Check for a draw (both players have made moves)
    let xCount = 0;
    let oCount = 0;
    
    for (let i = 0; i < 9; i++) {
      if (board[i] === "X") xCount++;
      else if (board[i] === "O") oCount++;
    
    if (xCount === oCount) {
      return true; // Draw
    }
    
    // Check for a win
    if (checkWin(board, "X", 0, 0) || checkWin(board, "X", 0, 2) ||
        checkWin(board, "X", 2, 0) || checkWin(board, "X", 2, 2)) {
      return true; // Player X has won
    }
    
    if (checkWin(board, "O", 0, 0) || checkWin(board, "O", 0, 2) ||
        checkWin(board, "O", 2, 0) || checkWin(board, "O", 2, 2)) {
      return true; // Player O has won
    }
  }
  
  // Game is not over
  return false;
}

// score variables
let boardScore = 0;
let drawScore = 0;
let playerScore = 0;

// DOM elements
let boardContainer = document.getElementById("boardContainer");
let restartButton = document.getElementById("restartButton");

// game state
let isGameRunning = false;
let currentPlayer = "X";
let gameStarted = false;

// initialize game
function initGame() {
  // TODO
}

// restart function
function restart() {
  // TODO
}

// game loop
function gameLoop() {
  // TODO
}

// start game
initGame();
gameLoop();
// Initialize the game and start the loop
document.addEventListener("DOMContentLoaded", () => {
  initGame();
  gameLoop();
});
// Set up the page and start the game
document.getElementById("boardContainer").style.display = "block";
restartButton.textContent = "Restart";

// Initialize the game board
function initGame() {
  // Create the 3x3 board
  const board = [
    "   ", "   ", "   ",
    "   ", "   ", "   ",
    "   ", "   ", "   "
  ];

  // Set up the minimax function to find the best move for the computer
  function minimax(board, player) {
    if (player === 'X') {
      // Check if the current player can win
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          if (checkWin(board, player, i, j)) {
            return i * 3 + j;
          }
        }
      }
      // If no winning move, explore all possible moves
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          if (canMove(board, i, j)) {
            return minimax(board, player);
          }
        }
      }
    } else if (player === 'O') {
      // Check if the current player can win
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          if (checkWin(board, player, i, j)) {
            return i * 3 + j;
          }
        }
      }
      // If no winning move, explore all possible moves
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          if (canMove(board, i, j)) {
            return minimax(board, player);
          }
        }
      }
    }

    // If the game is over
    return -1;
  }

  // Check if the game is over
  function gameIsOver(board) {
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        if (checkWin(board, 'X', i, j) || checkWin(board, 'O', i, j)) {
          return true;
        }
      }
    }
    return false;
  }

  // Function to check if a cell is a valid move
  function canMove(board, i, j) {
    // Check if the cell is within bounds
    if (i < 0 || j < 0 || i >= 3 || j >= 3) return false;
    
    // Check if the cell is empty
    if (board[i * 3 + j] !== " ") return false;
    
    return true;
  }

  // Set up the game
  const game = {
    board,
    minimax,
    gameIsOver
  };

  // Game starts when the restart button is clicked
  document.getElementById("restartButton").addEventListener("click", () => {
    initGame();
  });

  // Start the game
  gameIsOver(board);
}

function restart() {
  const newBoard = [" ", " ", " ", " ", " ", " ", " ", " ", " "];
  board = newBoard;
}

function gameLoop() {
  // Initialize board with empty cells
  const board = [
    "   ", "   ", "   ",
    "   ", "   ", "   ",
    "   ", "   ", "   "
  ];

  // Define player symbols
  const playerSymbols = ["X", "O"];
  
  // Check for win
  function checkWin(board, player) {
    // Check rows
    for (let i = 0; i < 3; i++) {
      if (board[i][0] === player && board[i][1] === player && board[i][2] === player) return true;
    }
    
    // Check columns
    for (let j = 0; j < 3; j++) {
      if (board[0][j] === player && board[1][j] === player && board[2][j] === player) return true;
    }
    
    // Check diagonals
    if (board[0][0] === player && board[1][1] === player && board[2][2] === player) return true;
    if (board[0][2] === player && board[1][1] === player && board[2][0] === player) return true;
    
    return false;
  }

  // Check for loss
  function checkLose(board, player) {
    // Check rows
    for (let i = 0; i < 3; i++) {
      if (board[i][0] === player && board[i][1] === player && board[i][2] === player) return true;
    }
    
    // Check columns
    for (let j = 0; j < 3; j++) {
      if (board[0][j] === player && board[1][j] === player && board[2][j] === player) return true;
    }
    
    // Check diagonals
    if (board[0][0] === player && board[1][1] === player && board[2][2] === player) return true;
    if (board[0][2] === player && board[1][1] === player && board[2][0] === player) return true;
    
    return false;
  }

  // Game is over
  function gameIsOver(board) {
    return checkWin(board, "X") || checkLose(board, "X");
  }

  // Update board based on current player's move
  function updateBoard(board, player, move) {
    const cell = move[0] + move[1];
    board[move[0]][move[1]] = player;
  }

  // Game loop
  while (!gameIsOver(board)) {
    // Check if it's the player's turn
    if (playerSymbols.includes("X")) {
      // Find best move for computer
      let bestMove = minimax(board, "X");
      updateBoard(board, "X", bestMove);
    } else {
      // Find best move for computer
      let bestMove = minimax(board, "O");
      updateBoard(board, "O", bestMove);
    }

    // Check for win
    if (checkWin(board, playerSymbols[0])) {
      // Player wins
      updateScore(board, playerSymbols[0]);
      return;
    }
    
    // Check for loss
    if (checkLose(board, playerSymbols[0])) {
      // Player loses
      updateScore(board, playerSymbols[0]);
      return;
    }
    
    // Check if game is over
    if (gameIsOver(board)) {
      // Game is over
      updateScore(board, playerSymbols[0]);
      return;
    }
  }

  // Restart game
  document.getElementById("restartBtn").addEventListener("click", () => {
    board = [
      "   ", "   ", "   ",
      "   ", "   ", "   ",
      "   ", "   ", "   "
    ];
    updateScore(board, playerSymbols[0]);
  });
}

// Helper function to update the score counter
function updateScore(board, player) {
  // Increment score for the current player
  const score = document.getElementById("score").innerText;
  if (player === "X") {
    score += "X";
  } else {
    score += "O";
  }
  document.getElementById("score").innerText = score;
}
