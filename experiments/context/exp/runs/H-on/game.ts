import { Board } from './game';
import { minimax, checkWin, checkDraw, gameOver } from './gameLogic';

const board = new Board(3);

function startGame() {
  board.reset();
  document.getElementById('board').innerHTML = board.render();
  document.getElementById('score').textContent = '0-0';
  document.getElementById('restart').addEventListener('click', () => startGame());
}

startGame();