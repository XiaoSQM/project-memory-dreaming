# Memory Evaluation

Use English for evaluation notes and explanations. Translate relevant non-English project context faithfully; preserve test inputs, code, identifiers, and names as needed for the test.

Choose representative tasks, fixed inputs, acceptance criteria, and an execution environment. Save real cases in `cases.json` with fields such as `case_id`, `task`, `expected_behavior`, and `required_sources`. Base the cases on actual project work; do not invent project scores.

Run the same tasks before and after a change and save the real results in `results/`. Each JSONL row contains `case_id`, `first_pass` (boolean), `citation_correct` (boolean or null), `rework_count` (non-negative integer), and `duration_seconds` (non-negative number). Also keep the memory version or batch ID, model environment, and evidence path.

Run `python tools/agent_memory.py evaluate --results <results.jsonl>` to summarize first-pass rate, citation accuracy and coverage, rework, and mean duration. An unevaluated citation is neither correct nor incorrect; do not report improvement without measurements. Compare the same case IDs, environment, and acceptance criteria. A model or task change cannot be attributed to Dreaming.

If results materially regress, inspect the evidence, record the cause, and follow the reviewed batch rollback process. Do not fill unknown data with zero or reuse customer claims from the source video as this project's results.
