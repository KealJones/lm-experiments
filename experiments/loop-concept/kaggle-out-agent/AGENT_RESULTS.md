# From scratch with tools: results

Plain Qwen/Qwen3-0.6B, just the task, tools to list/grep/read the docs and run code, up to 15 turns, 3 attempts per task (sampled). Lenient grading: the answer must be the last line(s) of output.

## Plink

- **Tasks solved: 0/25** (before: cold 0/25, with a snippet 1/25)
- Answers passing: 0/75; failing to compile/parse: 74/75
- Average per attempt: 7.3 turns, grep 0.0, read 0.0, list_files 0.0, run 6.4
- Attempts that never looked at the docs: 75/75; never ran code: 18/75
- How attempts ended: answered 48, turn limit 27, context full 0
- Solved: none

## Zig 0.17

- **Tasks solved: 0/25** (before: cold 0/25, with a snippet 0/25)
- Answers passing: 0/75; failing to compile/parse: 75/75
- Average per attempt: 3.6 turns, grep 0.0, read 0.0, list_files 0.0, run 2.7
- Attempts that never looked at the docs: 75/75; never ran code: 51/75
- How attempts ended: answered 63, turn limit 12, context full 0
- Solved: none

