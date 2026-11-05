// @types/brightleaf-notes
// @types/brightleaf-boards
// @types/brightleaf-sync
// @types/brightleaf-pulse

// Board
type Board = {
  row1: string;
  row2: string;
  row3: string;
};

// Player
type Player = {
  name: string;
  symbol: string;
};

// Score
type Score = {
  player1: number;
  player2: number;
  total: number;
};

// Game
type Game = {
  board: Board;
  player1: Player;
  player2: Player;
  score: Score;
};

// Game state
type GameState = {
  game: Game;
  isGameRunning: boolean;
  isGameOver: boolean;
};

// Functions
function initBoard(): void {
  const board = [
    " ", " ", " ",
    " ", " ", " ",
    " ", " ", " "
  ];
  
  // Set up the board DOM elements
  const boardContainer = document.getElementById('board');
  boardContainer.innerHTML = `
    <div class="cell" data-row="0" data-col="0"> </div>
    <div class="cell" data-row="0" data-col="1"> </div>
    <div class="cell" data-row="0" data-col="2"> </div>
    <div class="cell" data-row="1" data-col="0"> </div>
    <div class="cell" data-row="1" data-col="1"> </div>
    <div class="cell" data-row="1" data-col="2"> </div>
    <div class="cell" data-row="2" data-col="0"> </div>
    <div class="cell" data-row="2" data-col="1"> </div>
    <div class="cell" data-row="2" data-col="2"> </div>
  `;
  
  // Set up the board as a reference
  this.game.board = board;
}

function startGame(): void {
  const board = initializeBoard();
  const player1 = createPlayer("AI", "X");
  const player2 = createPlayer("User", "O");
  const score = initializeScore();
  const game = { board, player1, player2, score };

  initBoard();
  startGameLoop(game);
}

function startGameLoop(game: GameState): void {
  // Initialize the board and update the score
  initBoard();
  updateScore(game.score);
  
  // Start the game loop
  while (game.isGameRunning) {
    // Handle the move
    const move = getMove(game);
    
    // Update the board and score
    updateBoard(game.board, move);
    updateScore(game.score);
    
    // Check if the game is over
    checkGameOver(game);
    
    // Restart the game if it's over
    if (game.isGameOver) {
      restartGame();
    }
  }
}

function getMove(game: GameState): string | null {
  // Simulate a computer's move
  const availableMoves = ['X', 'O'];
  const randomIndex = Math.floor(Math.random() * 9);
  return availableMoves[randomIndex] || null;
}

function updateBoard(board: Board, move: string): void {
  // Update the board with the new move
  board.row1 = move;
  board.row2 = move;
  board.row3 = move;
}

function updateScore(score: Score): void {
  // Update player scores
  score.player1 += 1;
  score.player2 += 1;
  
  // Calculate total score
  score.total = score.player1 + score.player2;
}

function checkGameOver(game: GameState): void {
  // Check rows, columns, and diagonals for a win
  if (game.board.row1 === game.board.row2 && game.board.row1 === game.board.row3) {
    game.isGameOver = true;
  } else if (game.board.row2 === game.board.row3 && game.board.row2 === game.board.row1) {
    game.isGameOver = true;
  } else if (game.board.row1 === game.board.row2 && game.board.row1 === game.board.row3) {
    game.isGameOver = true;
  } else if (game.board.row3 === game.board.row2 && game.board.row3 === game.board.row1) {
    game.isGameOver = true;
  } else if (game.board.row1 === game.board.row2 && game.board.row1 === game.board.row3) {
    game.isGameOver = true;
  } else if (game.board.row2 === game.board.row3 && game.board.row2 === game.board.row1) {
    game.isGameOver = true;
  } else if (game.board.row1 === game.board.row2 && game.board.row1 === game.board.row3) {
    game.isGameOver = true;
  } else if (game.board.row2 === game.board.row3 && game.board.row2 === game.board.row1) {
    game.isGameOver = true;
  }
}

function restartGame(): void {
  // Reset game state
  const game = {
    board: {
      row1: " ",
      row2: " ",
      row3: " ",
    },
    player1: {
      name: "Player 1",
      symbol: "X",
    },
    player2: {
      name: "Player 2",
      symbol: "O",
    },
    score: {
      player1: 0,
      player2: 0,
      total: 0,
    },
    isGameRunning: true,
    isGameOver: false,
  };

  // Reset game state and restart the game
  initBoard();
  startGameLoop(game);
}

// Game state
type GameState = {
  game: Game;
  isGameRunning: boolean;
  isGameOver: boolean;
};

// Initialize the game
initBoard();
startGame();
// Sets up the page and starts the game
function setupGame(): void {
  const board = createBoard();
  const player1 = createPlayer("Player 1", "X");
  const player2 = createPlayer("Player 2", "O");
  const score = createScore();

  game.state.game = {
    board,
    player1,
    player2,
    score,
    isGameRunning: true,
    isGameOver: false
  };

  document.getElementById("board").innerHTML = renderBoard(game.state.board);
  document.getElementById("score").innerHTML = renderScore(game.state.score);
  document.getElementById("restart").addEventListener("click", restartGame);
  document.getElementById("start").addEventListener("click", startGameLoop);
}

setupGame();