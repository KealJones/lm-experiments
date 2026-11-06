The winner on clean scores is **run-c: lr 1e-4, trained on v1, 74.2.**

Here's the clean board, with b and d rescored on the 688 non-leaked examples:

| run | lr | data | score |
|---|---|---|---|
| **c** | **1e-4** | **v1** | **74.2** |
| f | 5e-5 | v1 | 73.1 |
| e | 1e-4 | cleaned v2 | 72.9 |
| a | 2e-4 | v1 | 71.4 |
| b | 5e-5 | v2 | 70.3 |
| d | 3e-4 | v2 | 68.2 |
| g | 5e-4 | v1 | 62.0 (unstable) |

The 78.9 and 76.5 numbers are gone. Those were b and d getting graded partly on their own training data.

I wouldn't call c a clear win yet, though. It only beats run-f by 1.1 points. Each run used one seed and was scored on about 688 examples, so a gap that small could just be noise. What the data does show clearly:
- v1 data beats v2
- lr around 5e-5 to 1e-4 is the sweet spot, and 2e-4 and up starts getting worse (g went off the rails at 5e-4)
- every run beats the base model's ~58 by a lot

Two loose ends before you trust the ranking:
1. **Make sure every run is scored on the same eval set.** I don't know whether f, g and e were scored on the 688 subset or the full 1000. If any of them used the full 1000, the comparison isn't apples to apples. Rescoring them on the 688 is cheap, since it's just inference.
2. **Rerun c and f with another seed or two.** That's about 4 to 8 hours of GPU time. If c still comes out ahead, it's your real winner. If they swap places, then 5e-5 vs 1e-4 doesn't really matter and you can pick either.

If you need a pick right now, go with run-c at 1e-4 on v1. Just don't treat it as final until you've done those two checks. And once the eval set is frozen and hashed, put an "eval subset" column in the spreadsheet so this kind of mixup can't happen again.
