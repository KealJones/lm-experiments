GIST: The user, a casual and sweary hobbyist ML tinkerer, has been LoRA fine-tuning Llama 3.2 1B on scraped slang conversations, with run-a through run-g. The chat also drifted into his toddler Bo's sleep and espresso dialing, none of which matters here.

REFERENCES RESOLVED:
- "all that bs": the eval-leak saga. His dedup script never checked training data against the eval set, and 312 of the 1000 eval examples turned up in dataset v2. v1 had zero overlap.
- "the leaky one": run-b, which scored 78.9 at lr 5e-5 on leaky v2. It looked like the winner but was inflated. Its clean score is 70.3.
- "the real one": the best run on clean data.

RELEVANT FACTS (final clean results; the leaky 78.9 and 76.5 are superseded and labeled "leaked, do not use"):
- run-a: v1, lr 2e-4, 71.4
- run-b: v2 (leaky), lr 5e-5, clean-subset 70.3
- run-c: v1, lr 1e-4, 74.2 (WINNER)
- run-d: v2 (leaky), lr 3e-4, clean-subset 68.2 (was 76.5)
- run-e: cleaned v2 (312 leaked items removed), lr 1e-4, 72.9
- run-f: v1, lr 5e-5, 73.1
- run-g: v1, lr 5e-4, 62.0, a cliff where training goes unstable
- Clean scoring used the 688 non-leaked eval examples. Runs a and c were rescored on the 688 and came out essentially unchanged (within about 0.1), so the comparison is apples to apples.
- Answer: run-c is the winner, at lr 1e-4 on v1 data with 74.2. The v1 lr curve forms a hill that peaks at 1e-4. Bigger v2 data did not help once cleaned (run-e 72.9 vs run-c 74.2 at the same lr).
- Caveat: the gaps between the top runs (74.2 vs 73.1 vs 72.9) are small enough on about 688 examples that noise matters.
- The other settings were the same for every run: LoRA rank 16, alpha 32, 3 epochs, batch size 8.
- The user wants the best clean slang model as a base, and later wants to add word lookup on top.
