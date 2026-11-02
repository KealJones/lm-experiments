// Types
type Board = number[][];

// Top-level variables
let board: Board = [
  [0, 0, 0],
  [0, 0, 0],
  [0, 0, 0]
];

let score: number = 0;

// Functions
renderBoard() {
  const boardElement = document.getElementById('board');
  const cellElements = Array.from({ length: 9 }, (_, i) => {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.textContent = i + 1;
    cell.addEventListener('click', () => {
      const cell = document.getElementById(`${i + 1}`);
      cell.textContent = cell.textContent;
    });
    boardElement.appendChild(cell);
  });
}

function updateScore(scoreValue: number) {
  const scoreElement = document.getElementById('score');
  scoreElement.textContent = `Score: ${scoreValue}`;
}

function getComputerMove(): number {
  // Minimax algorithm implementation
  // This is a simplified version for demonstration
  const moves = [
    [0, 2], [1, 0], [2, 1], [3, 5], [4, 3], [5, 4],
    [6, 8], [7, 6], [8, 7]
  ];
  return moves[Math.floor(Math.random() * moves.length - 1)];
}

// Game loop
function gameLoop() {
  // TODO
}

// Start game
function startGame() {
  // TODO
}

// Setup and start
const boardElement = document.getElementById("board");
const restartButton = document.createElement("button");

boardElement.addEventListener("click", () => {
  board.fill(0);
  updateScore(0);
  restartButton.textContent = "Restart";
  boardElement.appendChild(restartButton);
});

boardElement.appendChild(restartButton);

startGame();

boardElement.addEventListener("click", () => {
  board.fill(0);
  updateScore(0);
  restartButton.textContent = "Restart";
  boardElement.appendChild(restartButton);
});

boardElement.appendChild(restartButton);

const boardElement = document.getElementById('board');

// Initialize the board
board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];

// Create the board element
boardElement.innerHTML = "";
for (let i = 0; i < 3; i++) {
    boardElement.innerHTML += "<div id="cell" class="cell" onclick="updateScore(1)" data-row="${i}" data-col="0">" + i + "</div>");
}

// Set up the restart button
const restartButton = document.createElement('button');
restartButton.textContent = 'Restart';
boardElement.appendChild(restartButton);

const boardElement = document.getElementById('board');

// Initialize the board
board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];

// Create the board element
boardElement.innerHTML = "";
for (let i = 0; i < 3; i++) {
    boardElement.innerHTML += "<div id="cell" class="cell" onclick="updateScore(1)" data-row="${i}" data-col="0">" + i + "</div>");
}

// Set up the restart button
const restartButton = document.createElement('button');
restartButton.textContent = 'Restart';
boardElement.appendChild(restartButton);

const boardElement = document.getElementById('board');

// Initialize the board
board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];

// Create the board element
boardElement.innerHTML = "";
for (let i = 0; i < 3; i++) {
    boardElement.innerHTML += "<div id="cell" class="cell" onclick="updateScore(1)" data-row="${i}" data-col="0">" + i + "</div>");
}

// Set up the restart button
const restartButton = document.createElement('button');
restartButton.textContent = 'Restart';
boardElement.appendChild(restartButton);

function updateScore(scoreValue: number) {
    score += scoreValue;
    scoreElement.textContent = score;
}

function getComputerMove() {
    // Simulate minimax
    let bestMove = 0;
    let max = -Infinity;

    // Minimax implementation (simplified for this example)
    function dfs(board, depth, player) {
        if (isTerminal(board)) {
            return { score: 0, moves: [] };
        }

        const currentScore = calculateScore(board);
        if (depth === 1) {
            return { score: currentScore, moves: [] };
        }

        max = Math.max(max, dfs(board, depth - 1, player));
        return { score: max, moves: [] };
    }

    // Get a random move if it's the first move
    if (depth === 0) {
        return getMove();
    }

    // Evaluate the current board
    const currentScore = calculateScore(board);
    return currentScore;
}}

function gameLoop() {
    // Update the board
    updateBoard();
    
    // Check for win
    checkWin();
    
    // Check for draw
    if (isDraw()) {
        score.textContent = 'Draw';
    } else {
        score.textContent = `Score: ${score}`;
    }
    
    // Check for restart
    if (restartButton.classList.contains('selected')) {
        restartButton.classList.remove('selected');
        restartButton.textContent = 'Restart';
    } else {
        restartButton.textContent = 'Restart';
    }
}}
