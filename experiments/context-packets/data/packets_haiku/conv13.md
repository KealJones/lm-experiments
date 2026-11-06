GIST: The user is fine-tuning Llama 3.2 1B with LoRA (rank 16, alpha 32, 3 epochs, batch 8) on slang and casual-speech conversations they scraped, and they are comparing runs on a 1000-example eval set they built themselves. The chat also covers espresso dialing and toddler sleep, which do not bear on this message.

REFERENCES RESOLVED: "that" most likely points to the last number in the conversation, the answer 4 from the user's "2+2" question. Other candidates are the eval scores below, so if the intended number is different, the answer should say which number was used.

RELEVANT FACTS:
- Untuned Llama 3.2 1B scored about 58 on the eval set.
- Eval set: 1000 examples, held out before v1 was built. v1 is about 12k conversations and is clean. v2 is about 36k and is leaky.
- Leak: 312 of the 1000 eval examples appear exactly in v2. The dedup script only checked within training data. A 688-example clean subset is used for scoring.
- Latest clean scores (688 subset, latest version of each number):
  - run-a: 71.4, lr 2e-4, v1
  - run-c: 74.2, lr 1e-4, v1 (best clean run so far)
  - run-f: 73.1, lr 5e-5, v1
  - run-e: 72.9, lr 1e-4, cleaned v2
  - run-b: 70.3, lr 5e-5, v2. This supersedes the leaky 78.9.
  - run-d: 68.2, lr 3e-4, v2. This supersedes the leaky 76.5.
  - run-g: 62.0, lr 5e-4, v1 (training breaks down)
- The user's notes mark 78.9 and 76.5 as "leaked, do not use."
- Planned next steps: a hash-based leak check for the eval set, with normalization before hashing. The dedup script should fail loudly on any match. The results table should include columns for run name, data version, lr, eval set, score, LoRA rank, epochs, and notes.
- The user has been asked to keep results in a spreadsheet with a data-version column.
