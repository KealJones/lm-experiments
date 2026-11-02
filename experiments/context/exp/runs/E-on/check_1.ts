const board = document.getElementById('board');
const computer = document.getElementById('computer');
const score = document.getElementById('score');
const restart = document.getElementById('restart');

function initialize() {
  board.innerHTML = '';
  computer.innerHTML = '';
  score.textContent = 0;
  restart.addEventListener('click', () => { board.innerHTML = '';
    computer.innerHTML = '';
    score.textContent = 0; });
}

function checkWin(board, computer, score) {
  // Check rows
  for (let i = 0; i < 3; i += 1) {
    if (board.children[i].innerHTML === board.children[i + 1].innerHTML && board.children[i + 2].innerHTML === board.children[i].innerHTML) {
      score.textContent = 'Winner: ' + board.children[i + 1].innerHTML;
      return true;
    }
  }
  // Check columns
  for (let i = 0; i < 3; i += 1) {
    if (board.children[0].innerHTML === board.children[2].innerHTML && board.children[1].innerHTML === board.children[3].innerHTML) {
      score.textContent = 'Winner: ' + board.children[1].innerHTML;
      return true;
    }
  }
  // Check diagonals
  if (board.children[0].innerHTML === board.children[2].innerHTML && board.children[1].innerHTML === board.children[3].innerHTML) {
    score.textContent = 'Winner: ' + board.children[2].innerHTML;
    return true;
  }
  return false;
}

function minimax(board, depth, isMaximizer) {
  if (checkWin(board, computer, score)) {
    return 1; // Win for computer
  }
  if (depth === 0) {
    return -Infinity;
  }
  if (isMaximizer) {
    let max = -Infinity;
    for (let cell of board.children) {
      const newBoard = board.clone();
      newBoard.children[cell.index].innerHTML = cell.innerHTML;
      max = Math.max(max, minimax(newBoard, depth - 1, !isMaximizer));
    }
    return max;
  } else {
    let min = Infinity;
    for (let cell of board.children) {
      const newBoard = board.clone();
      newBoard.children[cell.index].innerHTML = cell.innerHTML;
      min = Math.min(min, minimax(newBoard, depth - 1, !isMaximizer));
    }
    return min;
  }
}

function play() {
  initialize();
  let moves = minimax(board, 0, true);
  if (moves === 1) {
    computer.innerHTML = 'Computer wins!';
    restart.click();
  } else {
    score.textContent = 'Player wins!';
    restart.click();
  }
}

play();