// Board
interface Board {
  [index: string]: string;
}

// Game state
let board: Board = [
  [' ', ' ', ' '],
  [' ', ' ', ' '],
  [' ', ' ', ' ']
];

// Minimax algorithm
function minimax(board: Board): [number, number] {
  // Check if the current player can win
  if (checkWin(board)) {
    return [0, 0];
  }

  // Check if the game is over
  if (checkGameOver(board)) {
    return [1, -1];
  }

  // Check if it's a draw
  if (checkDraw(board)) {
    return [1, -1];
  }

  // Determine current player
  let currentPlayer = 'X';
  
  // Try all possible moves
  let bestMove = [0, 0];
  
  for (let i = 0; i < 9; i++) {
    const cell = board[i];
    const index = cell === 'X' ? '0' : '1';
    
    // Place the current player on the cell
    board[i] = cell;
    
    // Recursively call minimax
    const result = minimax(board);
    
    // Update the best move based on the result
    if (currentPlayer === 'X') {
      bestMove[0] = result[0];
      bestMove[1] = result[1];
    } else {
      bestMove[0] = result[0];
      bestMove[1] = -result[1];
    }
    
    // Undo the move
    board[i] = cell;
  }

  return bestMove;
}

// Score counter
let xCount: number = 0;
let oCount: number = 0;

// Restart button
document.getElementById('restart-button').addEventListener('click', () => {
  board = [
    [' ', ' ', ' '],
    [' ', ' ', ' '],
    [' ', ' ', ' ']
  ];
  xCount = 0;
  oCount = 0;
});

// Game setup
const boardContainer = document.getElementById('board');
const restartButton = document.getElementById('restart-button');

// Initialize game
boardContainer.innerHTML = `
  <div id="board">
    <div class="cell" onclick="placeX('0')">X</div>
    <div class="cell" onclick="placeX('1')">O</div>
    <div class="cell" onclick="placeX('2')">X</div>
    <div class="cell" onclick="placeO('0')">O</div>
    <div class="cell" onclick="placeO('1')">O</div>
    <div class="cell" onclick="placeO('2')">O</div>
    <div class="cell" onclick="placeX('0')">X</div>
    <div class="cell" onclick="placeX('1')">X</div>
    <div class="cell" onclick="placeX('2')">X</div>
  </div>
`;
restartButton.addEventListener('click', () => {
  boardContainer.innerHTML = `
    <div id="board">
      <div class="cell" onclick="placeX('0')">X</div>
      <div class="cell" onclick="placeX('1')">O</div>
      <div class="cell" onclick="placeX('2')">X</div>
      <div class="cell" onclick="placeO('0')">O</div>
      <div class="cell" onclick="placeO('1')">O</div>
      <div class="cell" onclick="placeO('2')">O</div>
      <div class="cell" onclick="placeX('0')">X</div>
      <div class="cell" onclick="placeX('1')">X</div>
      <div class="cell" onclick="placeX('2')">X</div>
    </div>
  `;
});

// Initialize game
boardContainer.addEventListener('click', (e) => {
  const cell = e.target;
  const index = cell.innerText === 'X' ? '0' : '1';
  board[cell.innerText] = index;
  placeX(index);
  placeO(index);
  updateScore();
});

// Helper function to place a player
function placeX(index: number) {
  // Get the cell's text, which is 'X' or 'O'
  const cell = document.querySelector(`[onclick="placeX('${index}')"]`);
  // Set the cell's value to the index
  cell.innerText = index;
  // Update the board
  board[cell.innerText] = index;
}

function placeO(index: number) {
  // TODO
}

// Helper function to update scores
function updateScore() {
  // TODO
}

// Game loop (not needed in this code block, but for demonstration)
function gameLoop() {
  // TODO
}

// Check if player wins
function checkWin(): boolean {
  // TODO
}

// Check if the game is over
function checkGameOver(): boolean {
  // TODO
}

// Check if the game is a draw
function checkDraw(): boolean {
  // TODO
}

// Determine who's turn it is
function playerTurn(): string {
  // TODO
}

// Restart the game
function restart() {
  // TODO
}
// Initialize game
boardContainer.addEventListener('click', (e) => {
  const cell = e.target;
  const index = cell.innerText === 'X' ? '0' : '1';
  board[cell.innerText] = index;
  placeX(index);
  placeO(index);
  updateScore();
}););

console.assert(placeX(0) === 'X');
