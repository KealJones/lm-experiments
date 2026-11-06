# Role: blind grader (noisy context)
Read /home/claude/eval/grading/bundle_noisy.md. It has six cases (N1-N6), an answer key, and replies from three respondents X, Y, Z.
For each respondent and each case give: pass (true/false per the key), score 0-10, note (one sentence).
Write ONLY valid JSON to /home/claude/eval/grading/scores_noisy.json shaped {"X": {"N1": {"pass": true, "score": 10, "note": "..."}, ...}, "Y": {...}, "Z": {...}}
Tool rule: use ONLY the Read and Write tools. Finish with: done
