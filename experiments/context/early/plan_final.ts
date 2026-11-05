// ---- step 1 ----


// ---- step 2 ----


// ---- step 3 ----
score = 0
while True:
    move = input("Enter a move: ")
    score += 1
    print(f"Your score is now {score}.")

// ---- step 4 ----
<button id="restart">Restart</button>
<script>
  document.getElementById('restart').addEventListener('click', () => {
    // Clear board and reset score
    document.getElementById('board').innerHTML = '';
    document.getElementById('score').textContent = '0';
  });
</script>