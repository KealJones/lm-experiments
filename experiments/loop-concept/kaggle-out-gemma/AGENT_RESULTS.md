# From scratch with tools: results

Each model gets just the task, tools to list/grep/read the docs and run code, up to 15 turns, 3 attempts per task (sampled). Lenient grading: the answer must be the last line(s) of output.

# Gemma 4 E2B-it, Q8_0

## Plink

- **Tasks solved: 4/25**
- Answers passing: 4/75; failing to compile/parse: 71/75
- Average per attempt: 13.6 turns, grep 0.1, read 1.0, list_files 0.6, run 11.7
- Attempts that never looked at the docs: 32/75; never ran code: 0/75
- How attempts ended: answered 17, turn limit 58, context full 0, error 0
- Solved: arrsum, oddcount, running, sum100

# Gemma 4 E2B-it, Q8_0

## Zig 0.17

- **Tasks solved: 9/25**
- Answers passing: 16/75; failing to compile/parse: 48/75
- Average per attempt: 11.6 turns, grep 0.0, read 0.0, list_files 0.0, run 11.2
- Attempts that never looked at the docs: 73/75; never ran code: 0/75
- How attempts ended: answered 24, turn limit 51, context full 0, error 0
- Solved: arrmax, arrsum, countdown, evens, indexed, odds, pow2, running, times7

# Keal's tiny Gemma 4 (heal 3, 0.6B body), Q4_0 phone build

## Plink

- **Tasks solved: 0/25**
- Answers passing: 0/75; failing to compile/parse: 45/75
- Average per attempt: 1.3 turns, grep 0.0, read 0.0, list_files 0.2, run 0.0
- Attempts that never looked at the docs: 72/75; never ran code: 74/75
- How attempts ended: answered 75, turn limit 0, context full 0, error 0
- Solved: none

# Keal's tiny Gemma 4 (heal 3, 0.6B body), Q4_0 phone build

## Zig 0.17

- **Tasks solved: 0/25**
- Answers passing: 0/75; failing to compile/parse: 44/75
- Average per attempt: 1.3 turns, grep 0.0, read 0.0, list_files 0.2, run 0.0
- Attempts that never looked at the docs: 70/75; never ran code: 74/75
- How attempts ended: answered 74, turn limit 0, context full 0, error 1
- Solved: none

