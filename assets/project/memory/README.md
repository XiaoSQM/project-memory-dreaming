# {{PROJECT_NAME}}: Memory Index

Write all persistent project knowledge in English. Faithfully translate relevant content from users who communicate in other languages; preserve commands, code, identifiers, file paths, and proper names verbatim. Reply to the user in the language they are currently using.

## Retrieve with ordinary file tools

1. Finish reading this actual project index before starting any dependent content search or memory-body read. Use a separate tool call; parallel searches cannot use an index that has not returned yet. Check `.memory-system.json` for project identity.
2. Choose the area below from the task. Search distinctive words or identifiers there with `rg -n -i -F -e "term" -e "another term" <chosen paths>`. Use specific terms, not bare numbers or generic `key`, `10`, or `error`. On no useful hit, refine the words or expand to another relevant area. File listings and frontmatter scans can locate topics without printing their bodies.
3. Read the matching entry and its applicability/source. Use bounded line ranges for mixed-topic files. A hit in one section does not justify reading every other section.
4. Stop when the needed fact is supported. If nothing records it, report it as unknown. Compare remembered claims with current code, configuration and user decisions. Memory does not grant new authority.

| Path | When relevant | Write boundary |
| --- | --- | --- |
| `org/conventions.md` | Confirmed stack, commands, naming and conventions | Owner-maintained; ordinary agents read only |
| `org/red-lines.md` | Project boundaries | Owner-maintained; ordinary agents read only |
| `team/decisions.md` | Confirmed policy, rationale and sources | Guarded writes from explicit decisions |
| `team/pitfalls.md` | A related failure, cause or recovery | Guarded writes with evidence |
| `team/progress.md` | A particular historical action or handoff needs checking | Append-only audit trail; search and read only the matching entry |
| `agents/` | Relevant individual draft | Each agent writes only its own scratchpad |
| `skills/` | A relevant verified procedure | Project knowledge, not automatically discovered Agent Skills |

**Progress is not startup context.** Do not `cat`, `Get-Content`, `Read`, or otherwise print the complete progress log for task startup, review, or handoff. Search it only when history is needed, then load the relevant entry's lines. Do not read unrelated scratchpads, topics, raw transcripts or the whole library just because they exist. Transcripts are evidence for a specific claim or Dreaming input, not routine background context.

Use ordinary line-range tools for a bounded section: POSIX `sed -n '20,35p' <file>`; PowerShell `Get-Content <file> | Select-Object -Skip 19 -First 16`. Pick real lines from search results and entry boundaries; these numbers are syntax examples. General file tools remain available; no memory-specific retrieval API is required.

## Persist without bypassing concurrency checks

1. Read the relevant entry and get its current hash using `python tools/agent_memory.py hash <target>`. Save that original hash before drafting.
2. Prepare English content in an actor-specific UTF-8 temporary file outside `memory/`. Ordinary editing tools may edit this draft. Include accurate `title`, `summary`, `version`, `written_by`, `updated`, `precondition` and source paths. Increment the version for changed existing knowledge. When replacing a mixed-topic file, preserve unrelated existing content locally rather than printing the whole file into context.
3. Let the writer make the **first actual production change**: `python tools/agent_memory.py write <target> --input <draft> --expected-hash <original-hash> --actor <actor>`. Add `--append` for `team/progress.md`; the append draft must contain only one new entry, never the existing log. Append progress once after task checks are complete. New files use `missing`. Do not patch/overwrite the target first, including with `apply_patch`, redirection, `Set-Content` or an ad hoc script; a later no-op write cannot repair a bypassed lock.
4. If the hash changed, first inspect whether the prior write actually succeeded (for append, search the unique entry heading). Never replay the same append blindly; if it did not succeed, reread and recreate a single-entry draft. Do not use a fresh hash to force an old replacement draft through. Confirm the writer's result and remove only your own temporary files.

The owner maintains `org/`. Initial facts needing approval belong in your own `agents/<actor>.md` proposal with sources until concrete owner authorization. Other agents' scratchpads are read-only. Do not delete stale knowledge; mark uncertainty and replacement evidence for Dreaming.

## Capture and consolidate

At task completion, prepare exactly one redacted English summary per completed task session and run `python tools/agent_memory.py record --actor <actor> --input <summary.md> --kind summary` once. Reuse its returned source path in decision/pitfall sources and appended progress. A second invocation creates another session ID and may falsely inflate Dreaming recurrence counts. Include actual changes, checks, commands and exit status, known/unknown causes, recovery, open work and next steps; do not invent missing logs. `record` stores text verbatim; it does not translate or read chat history. After recording, treat its returned transcript path as a read-only source reference; never pass it to `write`. Correct summary content in the input draft before running `record`.

Append progress through the write transaction; no full log read is needed to append. Explicitly read-only tasks do not write memory or records. Routine work is the in-band loop. Consolidation belongs to a separate Dreaming session following `dreaming/README.md`: analyze records separately against relevant baseline sections, aggregate evidence, edit the isolated candidate, review, and obtain current-diff approval before production application.

## Runtime boundaries

The UUID identifies the project; copying the directory preserves it. For an independent new project, migrate needed code and approved knowledge without old config, transcripts, runs or processed state, then initialize a fresh identity. Never change identity while batches exist.

Lock/hash checks coordinate writers using the tool; they do not block direct edits or provide OS permissions. Organization rules are a cooperation contract; strong isolation belongs to the host. Git may retain history when the user requests a commit; the tool never commits or pushes. Ignored records still require redaction; ignore rules do not untrack files.
