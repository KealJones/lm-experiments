The real winner is run-c: learning rate 1e-4, trained on v1 data, scoring 74.2 on the clean eval set.

The leaky one was run-b. It hit 78.9 at lr 5e-5 on v2, but 312 of the eval examples had leaked into the v2 training data, and once you score it on the 688 clean examples it drops to 70.3. Run-d had the same problem: 76.5 leaked, 68.2 clean.

Run-a and run-c were rescored on the 688 clean examples and barely moved, so the comparison holds. Run-c also beats the cleaned v2 run (run-e, 72.9 at the same lr), so the extra data didn't help once the leak was removed.

Don't oversell the gap, though. 74.2 vs 73.1 (run-f, lr 5e-5) vs 72.9 is a small spread on 688 examples, so noise could be doing some of the work. If you want to be sure, rerun run-c and run-f with a few seeds before you build on run-c as the base. Everything else was held fixed across runs: LoRA rank 16, alpha 32, 3 epochs, batch size 8.
