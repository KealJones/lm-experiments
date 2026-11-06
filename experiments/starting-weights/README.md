# Starting weights: why random numbers, and how big

Keal: "when a model starts from 0. there are no weights yet. what makes it go to a different parameter instead of it like only ever using like 1 line?"

**Question:** if every weight started equal, would every neuron learn the same thing, and how much does the size of the random starting numbers matter?

A fully connected network (2 inputs, 1 to 8 hidden layers of 12 neurons, 1 output) learns to separate two spiral arms, 200 points, with full-batch gradient descent and backprop written by hand in [`site/demos/starting-weights/net.js`](../../site/demos/starting-weights/net.js). Five ways to start the weights:

- **all zeros**, and **all the same** (every weight 0.5)
- **tiny random**: normal(0, 0.01)
- **scaled random**: normal(0, gain / √inputs), gain 5/3 for tanh (Xavier-style) and √2 for ReLU (He / Kaiming)
- **huge random**: normal(0, 3)

The demo page trains it live in the browser. `node site/demos/starting-weights/test_net.mjs` checks the backprop against finite differences and checks the claims the page makes. Spend: $0.

## Results (Node on CPU, step size 0.3, 3 random draws, 6,000 steps; free)

**Equal starting weights never become different: every layer stays one neuron copied 12 times. Scaled random learns the spiral in 12 to 60 steps; tiny random never leaves the coin-flip loss; huge random kills every ReLU.**

| starting weights | tanh, 3 layers | tanh, 6 layers | ReLU, 3 layers | ReLU, 6 layers |
|---|---|---|---|---|
| all zeros | 50%, never moves | 50%, never moves | 50%, never moves | 50%, never moves |
| all the same | 80%, 1 neuron per layer | 58%, 1 neuron per layer | 50%, all dead | 50%, all dead |
| tiny random | loss stuck at 0.693 | loss stuck at 0.693 | loss stuck at 0.693 | loss stuck at 0.693 |
| scaled random | 97% by step 40–52 | 97% by step 12–25 | 97% by step 38–55 | 97% by step 22–60 |
| huge random | 97% by step 11–24 | 1 of 3 at step 2,417; others 68%, 75% | 50%, all dead | 50%, all dead |

- All zeros: every hidden gradient is exactly 0, so only the output bias can move.
- Tiny random: the signal shrinks about 30× per layer with tanh (6 layers: about 1e-10 at the last). The accuracy floats at 23–89% only because the output is a hair off zero; the loss stays at ln 2.
- Huge random with tanh surprised me: most neurons sit pinned at ±1, yet at 3 layers it learned faster than scaled. It bites with depth.
- Huge random with ReLU doesn't overflow. The first update is big enough to push every neuron negative, a ReLU that outputs 0 for every input gets no gradient, and none come back.
