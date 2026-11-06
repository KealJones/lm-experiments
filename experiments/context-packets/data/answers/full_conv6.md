Run-c won. It's Llama 3.2 1B with LoRA on v1 data at **lr 1e-4**, and it scored **74.2**.

That's the real result. v1 had zero overlap with the eval set, and when you rescored it on the clean 688 it came out the same. Here's the clean leaderboard:

- **run-c**: v1, 1e-4, **74.2**
- run-f: v1, 5e-5, 73.1
- run-e: cleaned v2, 1e-4, 72.9
- run-a: v1, 2e-4, 71.4
- run-b: v2, 5e-5, 70.3 (clean 688; the leaky score was 78.9)
- run-d: v2, 3e-4, 68.2 (clean 688; the leaky score was 76.5)
- run-g: v1, 5e-4, 62.0 (the cliff)

So the "leaky one" you're thinking of is run-b at 5e-5. It looked like the winner at 78.9, but on clean data it's second to last.

One honest caveat: c only beats f by 1.1 points, and on a 1000-example eval that's about at the noise floor. 1e-4 is clearly the best of what you tried, and the v1 curve has a nice hill shape around it. But I wouldn't claim 1e-4 is definitely better than 5e-5 unless you rerun both with a different seed and c still comes out ahead. Either way, run-c is the one to build the lookup stuff on.
