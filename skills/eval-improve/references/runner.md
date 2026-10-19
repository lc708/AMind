# Experiment runner and adapter contract

`run_eval.py` is a provider-neutral process runner. It executes an application adapter and a deterministic or command grader, writes evidence as work completes, and resumes completed observations. It has no model SDK or account dependency. The bundled demo uses synthetic local Python only.

## Start with the offline demo

Resolve `SKILL_ROOT` to this skill directory and use a fresh project result directory:

```bash
python3 "$SKILL_ROOT/scripts/run_eval.py" --card "$SKILL_ROOT/assets/offline-demo/experiment.json" --flow .eval-improve/demo-val --variant baseline --split val
python3 "$SKILL_ROOT/scripts/run_eval.py" --card "$SKILL_ROOT/assets/offline-demo/experiment.json" --flow .eval-improve/demo-val --variant baseline --split val --execute
python3 "$SKILL_ROOT/scripts/run_eval.py" --card "$SKILL_ROOT/assets/offline-demo/experiment.json" --flow .eval-improve/demo-val --variant v1 --split val --execute
python3 "$SKILL_ROOT/scripts/compare_runs.py" --flow .eval-improve/demo-val --candidate v1 --split val --metric quality --reps 1
python3 "$SKILL_ROOT/scripts/report_eval.py" .eval-improve/demo-val
```

The first command prints a plan without invoking either adapter. `--execute` performs the already-authorized run. `--resume` retains the same variant contract and skips existing successful `(case, rep)` observations. It does not silently increase budgets. `--retry-errors` explicitly retries incomplete failed cases and requires `runner.retry_safe=true`. For a new treatment use a new variant. For another split or changed evaluator use a separate flow.

## Experiment card, schema 2

Copy `assets/offline-demo/experiment.json` and replace its synthetic task/data/adapters. All paths are relative to the card directory unless absolute. The card names:

- `task`, `dataset_version`, `grader_version` and `schema_version:2`.
- `cases`: JSONL of `{id,input,tags?,group?}`. No answer/reference fields at top level. `group` is the unit of independent resampling; related examples share it. IDs may be Unicode, but duplicates and NFKC/casefold collisions are rejected. Trace filenames use hashes rather than user IDs.
- `references`: separate JSONL `{id,expected}` with exactly the same IDs. Do not place answer-bearing metadata in public `input`.
- `splits`: complete, disjoint `train`, `val`, `test` ID lists; a group cannot cross splits.
- `metrics`: `{id,kind,better,min?,max?,role?,min_improvement?,max_regression?}`. `kind:binary` enforces 0/1. `better` is `higher` or `lower`. The all-metrics decision requires exactly one `objective`, explicit `guardrail` margins, and optional `diagnostic` metrics.
- `runner`: `{command:[argv...],cwd?,files:[...],retry_safe?:true}`. No shell strings. List the **fixed adapter** and its dependencies in `files`; list mutable product source in the variant's target `files` instead. The adapter invokes the selected actual application using treatment config. Otherwise a product edit would correctly look like an unauthorized measurement change.
- `grader`: `{kind:exact|json_fields|artifact_checks|command,...}`. Built-ins require one metric and references. A command grader uses `command/cwd/files`, may require frozen baseline outputs with `requires_baseline:true`, and must emit all metrics. Its configuration and implementation belong to the fixed comparison identity.
- `variants`: baseline plus `v1`, `v2`, etc. Each has actual target `files`, `config` and optional `expected_model` or `expected_billing_identity` (exact `provider/interface/model/service_tier/region`, optional `context_band`). Actual file contents are hashed; served identities are checked before grading. A command grader can use the same pins. A model name alone does not pin the endpoint or deployment tier.
- `mutable_config`: exact dotted configuration paths permitted to vary. Other config fields must match baseline. No wildcards. Changes outside these axes require a new experiment definition, not relabelling existing results.
- `control_files`: lockfiles, dependency/runtime configuration, rubrics and other fixed resources. These are hashed and checked before and after each attempt. Unlisted dependencies and ambient environment are not captured automatically.
- `workspace.files`: explicit input fixture files to copy into a fresh per-attempt workspace. Relative paths only; no traversal. Fixtures are fixed evidence, not grader answers.
- `limits`: `max_attempts`, `concurrency` (1–32), `timeout_s`, `max_total_seconds`, `retries` (0–10), `max_output_bytes`. Optional `max_cost_usd` also requires `reservation_usd_per_attempt` covering application **and grader**. All attempts, including resumed/retried failures, count toward the budget.
- Optional `limits.max_failed_attempts` is a positive failure ceiling reconstructed from the persisted journal. Reconciled abandoned/cancelled attempts consume it. Retries, restart and cancellation cannot reset it. Concurrent work already in flight can still finish after the ceiling is reached; concurrency bounds that overshoot.
- Optional `coverage:{"required_stages":["workers","aggregate"],"expected_totals":{"workers":2,"aggregate":1}}` requires the adapter's `coverage` report. Freeze expected totals from the actual task population/workflow spec; do not derive them from a result that may omit workers. Each required stage has unique `id`, the declared positive integer `total`, `counts` with `succeeded==total` and no other nonzero counts, `coverage:1`, and `uncovered:[]`. Missing/failed/unknown coverage or a shortened denominator is unscorable. The engineering skill's `Workflow.report()` can supply this object; retain detailed item IDs/evidence to check population membership as well as cardinality. Without this contract, stage coverage is explicitly **unmeasured**.

The target and adapter may use any language/framework. Pin the runtime and its lockfiles and instrument the real entry point. A shell/API server shim that bypasses application tools is not equivalent to the application under evaluation.

## Application adapter protocol

The runner launches the argv directly, writes one JSON object to stdin, and expects one JSON object on stdout. Put logs on stderr, within the output cap. Prompts are never shell-interpolated. `{workspace}` in an argv argument expands to the case workspace; `AMIND_CASE_WORKSPACE` also identifies it. The adapter's cwd is fixed by the card, so the adapter must explicitly work in that fixture workspace when editing artifacts.

Input:

```json
{"input":{"ticket":"..."},"context":{"case_id":"a","rep":0,"variant":"v1","config":{"prompt_path":"prompts/v1.txt"},"workspace":"/absolute/fixture"}}
```

Output:

```json
{"output":{"answer":"..."},"status":"ok","model":"actual-served-model","usage":{"input_tokens":100,"cached_input_tokens":20,"output_tokens":30},"cost_usd":0.001,"transcript":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

`output` is required. `model` is required when an expected model is pinned. Usage/cost may be absent, but absence is unknown, never zero. Use `synthetic:true` for mock data. Preserve all relevant tool messages, refusal/incomplete states and artifacts in the trace; avoid secrets and unrelated data.

Return `{"error":{"kind":"rate_limit","retryable":true},"cost_usd":0.001,...}` for a classified failure. Exit nonzero when appropriate. A semantic wrong answer stays a successful transport result and is graded. Refusal may be a valid or invalid task outcome; define it in the rubric instead of classifying all refusals as infrastructure failures.

The runner retries only `retryable:true` failures within declared limits and only after `retry_safe` is asserted. Local process timeout is not proof that a remote side effect did not occur. Use remote idempotency/reconciliation or disable retries. First-attempt reliability and retry spend remain in `attempts.jsonl`/`errors.jsonl`.

## Graders

A command grader receives `{input,output,reference,baseline_output,workspace}` and emits `{grade:{metric:number,...},explanation?,model?,usage?,cost_usd?}`. It never receives the candidate label by default. Score all declared metrics and no others. Deterministic command graders should declare `cost_usd:0`; model judges must report actual/estimated cost or leave it unknown. Application cost is retained even if the judge fails. A transient judge retry within the same invocation reuses the successful application output/workspace instead of running the application again; every judge attempt is still billed/accounted. Across process restarts, reconcile the prior outcome and follow the explicit retry policy.

- `exact`: typed equality; optional `options.strip:true` for strings.
- `json_fields`: reference is `{ "nested.field": expected_value }`; missing and null differ. Only dictionary paths are supported. Use a custom grader for arrays, tolerances or semantic schemas.
- `artifact_checks`: reference has `files:{relative_path:exact_text}`, optional `absent:[...]` and `allowed_files:[...]`. Checks actual workspace state and refuses linked artifacts. Use project tests/rendering for code, database or visual semantics.

A grader with `requires_baseline:true` must define a valid baseline grading path when `baseline_output` is null on the baseline's first run. The runner freezes each baseline case's rep-0 output only after a complete run and verifies its hash before candidate grading. For pairwise judgments needing richer reference artifacts or randomized order, implement that in the fixed grader and calibrate it.

## Evidence, resume and reconciliation

Each variant stores `manifest.json`, `results.jsonl`, `attempts.jsonl`, `errors.jsonl` when needed, `traces/`, and `workspaces/`. Manifest identities bind data/references, split/group IDs, metrics, grading, adapter, fixed configuration, fixtures, control files, repetitions and kernel. Target hashes/configuration are separate treatment identity. Successful result rows are unique; cost lives on every finished attempt, including failures.

Resume checks target/measurement/limits, results and attempt journal hashes. Unknown interrupted attempts are not blindly retried. If a crash occurred between output/journal writes, use `reconcile_run.py --variant-dir ... --resolutions resolution.json` to inspect a plan. A resolution names `attempt_id`, `resolution` (`recorded_success` when a complete row exists, otherwise `abandoned`), externally verified `cost_usd` (or null), and `evidence`. Apply with `--apply` only after inspecting the external outcome. No grade is fabricated. A live/stale PID that may still exist prevents reconciliation. Preserve original evidence when manual repair is required.

Time budgets use the original start time across resumes, including downtime. A completed run can be inspected/resumed without new work. Expired/inadequate budgets require a newly reviewed run, not silently changing the old manifest. Reservations control scheduling, not a hard provider spending limit; unknown/excess attempt cost stops new scheduling. Already in-flight remote work may still bill.

Each new result carries a `result_identity` binding comparison hash, treatment hash, case and repetition. Strict comparison rejects transplanted results even if an exporter updates the file-byte hash. This detects accidental mixing, not malicious fabrication by a same-user process. Legacy schema-2 exports remain readable without retroactively claiming this per-result binding.

## Isolation and file integrity

The runner separates app input from references/judges and gives each attempt a clean fixture workspace. **It does not provide filesystem, network, credential or process isolation.** An adapter inherits the parent environment and can access other paths unless the host/container restricts it. Do not expose grader secrets, unrelated credentials or held-out files to an untrusted target. To isolate, mount only public inputs/target/fixtures, run the grader outside, constrain network/tool endpoints, and verify with a canary.

Artifact reads/writes reject planted symlinks, hardlinks and path traversal inside the resolved flow root. Hashes detect accidental drift in listed files; they are not signed evidence, protection against a malicious same-user process, or a guarantee against a directory-swap race. Freeze source/dependencies and use separate permissions when that boundary matters. Output is bounded; large traces/artifacts need explicit size/storage planning.

## Final test

```bash
python3 "$SKILL_ROOT/scripts/seal_selection.py" --flow .eval-improve/task-val --candidate v1 --output .eval-improve/selection.json --rationale "Registered validation gates passed; candidate frozen"
python3 "$SKILL_ROOT/scripts/run_eval.py" --card experiment.json --flow .eval-improve/task-test --variant baseline --split test --selection .eval-improve/selection.json --execute
python3 "$SKILL_ROOT/scripts/run_eval.py" --card experiment.json --flow .eval-improve/task-test --variant v1 --split test --selection .eval-improve/selection.json --execute
```

This freezes target and measurement identity before test execution. It does not enforce blindness outside the runner or prevent starting another experiment. Final test must remain genuinely untouched in the surrounding workflow.
