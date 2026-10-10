# Collect fresh Codex responses

`scripts/collect_codex.py` is a standard-library Python adapter for **read-only, fresh-session Codex CLI tasks**. It plans by default. Adding `--execute` launches real Codex runs using the existing login/configuration and can consume subscription capacity or API spend. Use it only within an already established run/spend scope. `--max-runs` and `--timeout` bound invocation count/time, not dollars or tokens.

It is not suitable for write-based coding benchmarks, interactive desktop tools, ongoing conversations, or an application's own API entry point. Build an adapter for the actual target in those cases. CLI and desktop tool availability may differ; record the runtime and verify the skill/tools under test are accessible to that CLI.

## Prepare the task and inputs

Use the [artifact contract](artifacts.md) for `_state.json`. Give each case a stable path-safe `id` and a `prompt`; `tags` is optional. Supply **only the selected split** in the input JSONL. Other fields, including expected answers, are rejected:

```json
{"id":"case_2","prompt":"Review the supplied fixture and return the requested classification.","tags":["classification"]}
```

Place task fixtures/instructions in a controlled workspace. Keep grader inputs and held-out data inaccessible to the evaluated process. The read-only sandbox protects against ordinary workspace writes; it does **not** hide readable answers, isolate accessible MCP/network tools, or sanitize existing hooks/configuration. When actual separation cannot be enforced, label the run unblinded/exploratory. Do not use configuration-bypass flags as an isolation shortcut.

Plan a run (no Codex process or output directory is created):

```bash
python3 "$SKILL_ROOT/scripts/collect_codex.py" \
  --flow "$FLOW" --cases "$FLOW/val-inputs.jsonl" \
  --workspace "$TARGET_WORKSPACE" --variant baseline --split val \
  --target-version "$TARGET_SNAPSHOT" --reps 2 --max-runs 8 --timeout 300
```

`TARGET_SNAPSHOT` must identify the actual target, including relevant uncommitted changes, skill versions, fixture/configuration state and external dependencies; the script records the label but cannot prove it is accurate. Input/state/collector hashes are recorded automatically. Preserve those snapshots for reproducibility.

Inspect the printed plan. Within the authorized scope, repeat with `--execute`. Optional `--model` and `--profile` are explicit overrides; otherwise the user's configured settings are inherited. The tool never copies credentials or invents the effective model identity. Inspect retained native events/configuration when the exact resolved model is needed.

Each case/repetition uses `codex exec --json --ephemeral --sandbox read-only`, prompt on stdin and a final-message output file. Version and raw events are recorded. No retries or implicit resume occur; existing variants are refused. Use a fresh flow for a later held-out phase, retaining the frozen baseline/candidate configurations and links to the earlier selection evidence.

## Grade independently

Outputs are append-only `captures.jsonl`, `errors.jsonl`, `traces/`, `raw/`, `run-plan.json` and `run-summary.json`. Successful captures have `status: ungraded` and `grade: {}`. Timeouts, CLI failures, malformed events, missing completion or missing final output remain explicit failures. Native usage remains in metadata; missing usage is not zero. An interrupted process retains partial evidence and never counts as a complete successful run.

Run the project's independently calibrated grader over a copy of the captures, then write `results.jsonl` using the artifact contract. Set `status: ok` **only after** an actual successful grade. Keep original captures, failure rows and known failed-attempt usage. Validate coverage and dataset/grader versions before the paired comparison. A report with no numeric grades is not an evaluation result.

The collector's exit code 0 means all requested outputs were captured without detected runtime failure; it does not mean the task passed, output was correct or improvement occurred. Exit 2 indicates invalid configuration/incomplete collection; exit 130 indicates interruption. Tools or remote operations already dispatched may outlive a local timeout: use isolated side-effect fixtures and runtime-specific cancellation where needed.

The flags and JSONL lifecycle were checked against Codex CLI `0.159.0` and [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) on 2026-09-30. Revalidate when the CLI contract changes. Local helper tests use a synthetic executable, not real model calls.
