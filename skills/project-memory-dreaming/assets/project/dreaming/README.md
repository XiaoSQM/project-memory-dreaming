# Dreaming: Independent Session Consolidation

Write candidate memory, proposals, review reports, and evaluation notes in English. Translate relevant non-English session content faithfully; preserve commands, code, identifiers, file paths, and names verbatim. For evidence, quote the English text exactly as stored in the transcript and label translated quotes when relevant. Continue discussing the review with the user in the language they use.

Initialization sets up the workflow but does not enable a scheduled task. Run it manually first; after it is stable, the user may specify a schedule and execution environment for a host scheduler.

1. In a separate Agent session, run `python tools/agent_memory.py prepare` to create a batch ID and `dreaming/runs/<run>/`.
2. Read `manifest.json` and the baseline memory index. Analyze each transcript separately against only its relevant baseline sections, then consolidate. Use one independent analysis task per transcript with bounded parallelism when available and authorized; otherwise work serially and preserve one result per transcript. Use ordinary file/read/shell/grep tools, precise keywords and bounded entry reads; do not load full progress or unrelated baseline bodies. A filesystem copy is not an instruction to print its contents. Keep per-record findings in the batch's `analyses/`, then aggregate into `proposals.json`.
3. Edit only writable memory in the batch's `candidate/` and fill in `proposals.json`. Suggest organizational convention changes in proposals only. The working session continues to use production `memory/`.
4. Run `python tools/agent_memory.py review <run>` and inspect `REVIEW.md`, diffs, source evidence, independent work-session counts, and uncertainties. A repeated `record` call can create multiple session IDs for one task; compare summary content and sources before counting separate sessions.
5. Apply only after the user explicitly approves the current batch and its diff: `python tools/agent_memory.py apply <run> --approved-by <reviewer>`. The reviewer name is an audit field, not proof of approval. If a hash changed, review again and obtain fresh approval.
6. Compare fixed tasks before/after while holding inputs, model, tools and protocol constant and switching only memory versions. Record actual first-pass outcomes, citations, correction rounds and time. A reviewed candidate may be tested in an authorized disposable project copy before production publication; it retains the same logical project identity. Report "not evaluated" without measurements. For rollback, first get approval, then run `python tools/agent_memory.py rollback <run> --approved-by <reviewer>`.

## Analysis output

`proposals.json` is an array with `id`, `type` (add/update/deprecate/promote_to_rule), `target` (project-relative path), `proposal`, `reason`, `confidence` (high/medium/low), and `evidence` (array). Each evidence item contains `source` (a transcript path from the manifest) and a verbatim `quote` from that stored English transcript. Also record `precondition`, `uncertainties`, and cross-session counts. Mark deprecated entries instead of deleting files.

`promote_to_rule` requires at least two independent sessions supporting the same pattern; multiple lines from one session do not count as multiple occurrences. Similar issues from different projects do not count as recurrence in this project. Every candidate change requires a proposal with evidence for that target; a proposal does not have to be applied to the candidate immediately.

## Scheduler prompt

"Run Dreaming for this project: read `memory/README.md` and this file; select only unprocessed records this project is authorized to access; prepare an isolated batch; analyze tool calls and user feedback; write English, evidence-backed candidates and a review report; report the batch ID, diffs, open questions, and evaluation status; then wait for human approval. Do not apply, commit, or upload records."

For personal projects, once per week is a suggested starting point; adjust for activity and cost. Stop when there are no new records. Keep batches small instead of loading the whole memory into every analyst's context.
