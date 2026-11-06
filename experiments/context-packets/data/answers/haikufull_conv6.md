Run-c won on clean data: Llama 3.2 1B with LoRA, lr 1e-4, trained on v1, 74.2 on the clean eval.

Clean numbers, best to worst:
- run-c: lr 1e-4, v1, 74.2
- run-f: lr 5e-5, v1, 73.1
- run-e: lr 1e-4, cleaned v2, 72.9
- run-a: lr 2e-4, v1, 71.4
- run-b: lr 5e-5, v2, 70.3 (on the 688 clean subset)
- run-d: lr 3e-4, v2, 68.2 (on the 688 clean subset)
- run-g: lr 5e-4, v1, 62.0

The 78.9 (run-b) and 76.5 (run-d) numbers are the leaked ones and should stay out of the table.

Don't read too much into the win, though. Run-c, run-f and run-e are within about a point of each other, and on roughly 688 examples that's inside the noise. Run-c is the best so far, not a clear winner. Also, the leak check so far was exact-match only. If you run the normalized hash check on v1 too, you might find some near-duplicates, and that could move the v1 numbers a bit.
