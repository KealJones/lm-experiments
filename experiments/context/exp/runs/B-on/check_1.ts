const board = [['', '', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', ''], ['', '']];
let currentPlayer = 'X';
let score = 0;

function check_win() {
  // Check rows
  for (let row of board) {
    if (row[0] === row[1] && row[1] === row[2] && row[0] !== '') {
      return true;
    }
  }
  // Check columns
  for (let col = 0; col < 3; col++) {
    if (board[0][col] === board[1][col] && board[1][col] === board[2][col] && board[0][col] !== '') {
      return true;
    }
  }
  // Check diagonals
  if (board[0][0] === board[1][1] && board[1][1] === board[2][2] && board[0][0] !== '') {
    return true;
  } else if (board[0][2] === board[1][1] && board[1][1] === board[2][0] && board[0][2] !== '') {
    return true;
  }
  return false;
}

function check_draw() {
  for (let row of board) {
    if (row.every(cell => cell === '')) {
      return true;
    }
  }
  return false;
}

function update_score() {
  if (currentPlayer === 'X') {
    score += 1;
  } else {
    score -= 1;
  }
  return score;
}

function is_game_over() {
  return check_win() || check_draw() || score <= 0;
}

function handleClick(index) {
  const cell = board[index / 3][index % 3];
  if (cell === '' && !is_game_over()) {
    board[index / 3][index % 3] = currentPlayer;
    update_score();
    if (check_win() || check_draw()) {
      alert('You win!');
      return;
    }
    if (check_draw()) {
      alert('It's a draw!');
      return;
    }
    currentPlayer = currentPlayer === 'X' ? 'O' : 'X';
  } else if (cell !== '' && !is_game_over()) {
    alert(`Cell ${index + 1} is occupied by ${currentPlayer}.`);
    return;
  }
}

// Start game
function startGame() {
  document.addEventListener('click', (e) => {
    const cell = e.target.dataset.cell;
    handleClick(cell);
  });
}

startGame();