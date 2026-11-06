GIST: The user (casual, chatty, toddler son Bo) has been running LoRA fine-tunes of Llama 3.2 1B to understand slang, scored on a 1000-example eval set he built from scraped slang conversations. The base model scored about 58. Espresso and toddler-sleep chat is off-topic here.

REFERENCES RESOLVED: "the real one not the leaky one" means the leak-corrected scores. "Which run won" means the best clean run. "All that bs" means the eval-leak detour.

RELEVANT FACTS:
- Leak: the v2 training set shared 312 of the 1000 eval examples (exact matches). His dedup script only checked within training data. v1 had zero overlap.
- Runs b and d were trained on v2, so their leaked scores (78.9 and 76.5) are invalid. He is labeling them "leaked, do not use." Rescored on the 688 non-leaked eval examples: run-b 70.3, run-d 68.2.
- Latest clean scores, which supersede every earlier table:
  - run-c: lr 1e-4, v1 data, 74.2 (best clean run)
  - run-f: lr 5e-5, v1, 73.1
  - run-e: lr 1e-4, cleaned v2, 72.9 (eval subset not stated)
  - run-a: lr 2e-4, v1, 71.4 (same on the 688 subset)
  - run-b: lr 5e-5, v2, 70.3
  - run-d: lr 3e-4, v2, 68.2
  - run-g: lr 5e-4, v1, 62.0 (training unstable)
- Caveat: run-c leads run-f by 1.1 points on about 688 examples with one seed each, so the gap is within noise. The transcript does not say whether run-f and run-g were scored on 688 or all 1000.
- Shared settings: LoRA rank 16, alpha 32, 3 epochs, batch size 8. Each run takes about 2 hours on a rented GPU.
- His conclusion: v1 data beats v2, and the lr sweet spot is about 1e-4 on v1.
- He wants to freeze and hash the eval set and block training on any overlap, and to track runs in a spreadsheet with dataset, lr, eval subset, and score columns.
