# Citation-evidence workplace retest

This directory is a preregistered targeted test, not a source refresh. The worker ran no target model and inspected no new target answer before freezing. The parent owns runtime isolation, 18 target captures and later model grading.

- `tasks.json`: two realistic requests, each run three times in each of three arms (18 total).
- `grading-contract.json`: five binary criteria per task, evidence-level distinctions, primary/secondary metrics and runtime/unknown handling.
- `native-exhibits.json`: seven exact native claim bindings and their complete passages/source metadata. Includes the policy announcement, old archive, future AUP and the RL article's date header/method/results. Claim existence alone is not treated as support.
- `arm-recipe.private.json`: root-only overlay instructions and source hashes. Before uses pre-clarification docs/registry/manifest; docs-only uses current docs with the same old registry/manifest; full uses current docs and qualified registry reason. SQLite, passages, query/lifecycle scripts and cutoff are identical.
- `curation-exhibits.private.json`: root-only old/full curation annotations. Only the predecessor policy reason changes; eligibility fields do not.
- `controls-blind-inputs.json`: eight anonymous positive/negative controls; no outcome labels or expected scores.
- `controls-expected.json`: private expected criterion vectors. Do not expose it, other private files, or this README to the grader.

Give a fresh grader only the fixed grading contract, anonymous controls and native exhibits. Check its control grades against the private key before it judges target packets. Controls include known-supported answers, laundering a real registry window into primary proof, over-refusal, over-generalization, empty and injected answers. Calibration is itself AI judgment unless otherwise validated; keep discrepancies visible rather than silently changing the task rubric.

After all planned captures are complete, the root can create a JSONL file with one row per planned run:

```json
{"run_id":"private-run-id","task_id":"CIT-P","status":"captured","answer":"raw final answer","skill_root":"/absolute/path/to/assigned/frozen/skill"}
```

Run `build_blind_packets.py --runs-jsonl /absolute/path/runs.jsonl --out /absolute/path/new-packet-directory`. The builder verifies protocol hashes, queries each actually cited claim through that run's public CLI with `show --passage --json`, includes complete native opening context for cited source units, anonymizes IDs and shuffles packet order. It also retains unknown/missing citations and runtime failures. It never runs a model. The output's `blind-packets.jsonl` is allowed to the grader; `unblinding.private.json` and `citation-lookups.private.jsonl` remain root-only. Relevant curation annotation text is retained as evidence; it is not an independent primary source and is not a fabricated record. Document opening context is supplementary evidence, not proof the target inspected it.

The protocol outcome is a small task/arm distribution, not a best-run comparison. A factual falsehood, a primary-support gap, reasonable uncertainty, over-refusal, formatting trouble and failed execution are separate categories. A statement supported by one experiment may remain Public position. No new live verification or whole-corpus semantic audit is claimed.
