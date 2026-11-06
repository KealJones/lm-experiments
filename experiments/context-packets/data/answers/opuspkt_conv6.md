**run-c wins: lr 1e-4 on v1 data, scoring 74.2.**

That's the real number. run-c was trained on v1, which had zero overlap with the eval set, and when we rescored it on the 688 clean examples it barely moved (about 0.1), so there's no leak inflating it.

How the clean board shakes out:

| run | data | lr | clean score |
|---|---|---|---|
| **run-c** | v1 | **1e-4** | **74.2** |
| run-f | v1 | 5e-5 | 73.1 |
| run-e | cleaned v2 | 1e-4 | 72.9 |
| run-a | v1 | 2e-4 | 71.4 |
| run-b | v2 (leaky) | 5e-5 | 70.3 (was "78.9") |
| run-d | v2 (leaky) | 3e-4 | 68.2 (was "76.5") |
| run-g | v1 | 5e-4 | 62.0 (training went unstable) |

Two things worth taking from it:

- **Your old "winner" was fake.** run-b's 78.9 was the leak talking. On clean examples it lands at 70.3, which puts it in the bottom half.
- **More data didn't help once it was cleaned.** run-e used the same lr as run-c on the scrubbed v2 and got 72.9 vs 74.2. On v1, the lr curve is a clean hill that peaks at 1e-4 and falls off a cliff by 5e-4.

One caveat, though: 74.2 vs 73.1 vs 72.9 on ~688 examples is close enough that noise could flip the order. I'd call run-c the best pick, not a proven winner over run-f and run-e. If you want to be sure before you build word lookup on top of it, rerun c, f and e with a couple of different seeds and see if the order holds. If it doesn't, you've got a three-way tie, and run-c is still a perfectly good base for Llama 3.2 1B (LoRA r16, alpha 32, 3 epochs, batch 8, same as all the others).
