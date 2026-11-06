GIST: Casual, swear-prone chat with the user, a hobbyist fine-tuning Llama 3.2 1B (LoRA) on a self-scraped Reddit slang dataset. He runs LR experiments, found an eval-leak bug, and also chats about his toddler Bo's sleep and espresso. Only the ML runs bear on this message.

REFERENCES RESOLVED: "that bs" = the whole saga of runs a-g and the data leak. "the leaky one" = run-b (lr 5e-5, v2 data), which first looked like the winner at 78.9. "the real one" = the best run on clean (leak-free) evaluation.

RELEVANT FACTS:
- Setup: Llama 3.2 1B, LoRA rank 16, alpha 32, 3 epochs, batch size 8. Base model scored about 58 on his eval.
- Leak: v2 data (about 36k, 3x v1) contained 312 of the 1000 eval examples (exact matches). v1 (about 12k) had zero overlap. His original dedup only checked within the training set. Runs on v2 were rescored on the 688 clean examples. Runs on v1 were unaffected, and rescoring a and c on the 688 gave the same scores within about 0.1.
- Final clean results:
  - run-a: v1, lr 2e-4, 71.4
  - run-b: v2, lr 5e-5, 70.3 (leaky score was 78.9, "leaked, do not use")
  - run-c: v1, lr 1e-4, 74.2
  - run-d: v2, lr 3e-4, 68.2 (leaky score was 76.5)
  - run-e: cleaned v2, lr 1e-4, 72.9
  - run-f: v1, lr 5e-5, 73.1
  - run-g: v1, lr 5e-4, 62.0 (the "cliff")
- Winner on clean data: run-c, lr 1e-4, v1 data, 74.2. The v1 curve is smooth: 5e-5 gives 73.1, 1e-4 gives 74.2, 2e-4 gives 71.4, 5e-4 gives 62.0. At the same lr of 1e-4, cleaned v2 (72.9) is slightly below v1 (74.2). That 1.3 point gap is within noise on about 688 examples.
- Caveat: run-c's 74.2 is from the original 1000-example eval (v1 had no overlap). Rescoring on the 688 gave the same score, so the comparison is fair.
- He plans to use the best clean run as the base for a later lookup-tool model. He has also written a normalized sha256 eval-hash guardrail into his dedup script.
- Preferences: he curses casually, so swearing isn't aggression. Refer to the model as Llama 3.2 1B. He wants direct answers.
