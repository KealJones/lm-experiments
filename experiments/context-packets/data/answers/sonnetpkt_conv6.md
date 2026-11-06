**run-c. lr 1e-4, on the v1 data. Clean score is 74.2.**

The leaky one was run-b at 5e-5 on v2. It showed 78.9, but on the 688 clean examples it drops to 70.3, so it's actually down near the bottom of the pack. Ignore that 78.9 completely.

The clean leaderboard:

| run | data | lr | clean score |
|---|---|---|---|
| **c** | v1 | **1e-4** | **74.2** |
| f | v1 | 5e-5 | 73.1 |
| e | cleaned v2 | 1e-4 | 72.9 |
| a | v1 | 2e-4 | 71.4 |
| b | v2 (leaky) | 5e-5 | 70.3 |
| d | v2 (leaky) | 3e-4 | 68.2 |
| g | v1 | 5e-4 | 62.0 |

The 74.2 is a fair number. v1 never overlapped the eval set, and rescoring run-c on the 688 clean examples gave the same score.

Don't read it as a blowout, though. On roughly 688 examples, run-f (73.1) and run-e on cleaned v2 (72.9) are both within noise of run-c. What the data does support is the shape of the v1 curve: it peaks around 1e-4 and falls off hard above 2e-4 (5e-4 tanks to 62). So 1e-4 is the right call. It's just not a sure thing that it's *better* than 5e-5. And the 3x bigger cleaned v2 data didn't buy you anything, which is worth knowing before you scrape more.

For the lookup-tool model, I'd start from run-c. That's Llama 3.2 1B, LoRA r16/alpha 32, 3 epochs, batch 8, lr 1e-4, v1 data. Up from the base model's ~58, that's about +16 points.
