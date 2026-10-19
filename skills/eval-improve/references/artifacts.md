# Evidence and comparison contract

The default flow is `.eval-improve/<experiment>-<split>/` with `baseline/`, `v1/`, etc. Existing project evaluators may export compatible artifacts; verify their provenance rather than generating a manifest merely to satisfy a parser. The complete runner/card contract is in [runner.md](runner.md).

## State and observations

`_state.json` declares `metrics`, `reps`, `train_ids`, `val_ids`, `test_ids`. A metric has `id`, `kind`, direction and optional decision role/margin. Each successful row in `variant/results.jsonl` has string `prompt_id`, zero-based integer `rep`, `status:ok`, numeric `grade`, and its own output/model/usage/trace metadata. All planned repetitions must be present exactly once. Transport/judge failures belong in the append-only attempt/error ledgers, not fake successful zeros.

Variant manifests use schema 2. `comparison_identity` binds the data, references, metrics, grader/runner code and configuration, split IDs, independence groups, repetitions, fixtures/control files and kernel. `comparison_hash` must equal its canonical SHA-256. Treatment identity records actual target files and configuration separately so legitimate application edits can be compared while measurement edits cannot. Result and journal byte hashes detect changes since export. A complete status is necessary, not sufficient, for adoption.

New runner exports set `result_identity_required:true`; each row binds comparison hash, treatment hash, case and repetition. A result from another endpoint/model configuration or treatment must not be transplanted by merely rewriting file hashes. `billing_identity` and `judge_billing_identity` retain exact served scope when instrumented. `coverage.status:unmeasured` means no required-stage contract was instrumented; it does not mean all children passed. The report exposes these distinctions and remaining failure budget.

## Strict comparison

```bash
python3 "$SKILL_ROOT/scripts/compare_runs.py" --flow "$FLOW" --candidate v1 --split val --metric quality --reps 2
python3 "$SKILL_ROOT/scripts/compare_runs.py" --flow "$FLOW" --candidate v1 --split val --all-metrics --reps 2
```

Before computing, the tool checks both manifest hashes, result/journal bytes, completion status, identical measurement identities and final selection certificate when present. It checks requested split, metrics and repetitions, rejects undeclared metrics/direction changes, duplicate rows, unexpected observations, missing reps, nonfinite scores and unscored cases. A changed dataset/grader/configuration requires rerunning/rescoring both sides in a new compatible export.

The estimand is the case-weighted mean difference, with repetitions averaged within each case. Bootstrap draws resample whole declared independent groups, preserving related cases within a draw. The output records seed, draws, alpha, group count and interval. Fewer than two groups yields no confidence claim; a small number of groups can still produce unreliable or degenerate intervals. Group declaration is a substantive assumption, not something hashes verify.

`cost_usd` uses **all finished attempts per case/rep**, including failed calls and judge spend, when an attempt ledger exists. Any unknown attempt cost makes that case's cost unscorable. `latency_s` includes this invocation's application/grading work and local retry/backoff time; it excludes scheduling/queue time and earlier invocations before a resume. Instrument full user-perceived latency separately.

`--all-metrics` requires one predeclared objective (`min_improvement`) and explicit guardrails (`max_regression`), with optional diagnostics. It uses Bonferroni-adjusted intervals across the decision metrics. This does not correct adaptive candidate search or repeated peeking. Hard invariant failures, cost/latency budgets and mechanism checks must also pass. A validation `gates_passed` means selection eligibility, not final proof or deployment authorization.

`--allow-legacy` reads older artifacts without identity verification and reports `exploratory_unverified`, never a positive improvement verdict. It cannot be combined with automatic all-metric promotion. Missing observations remain incomplete.

## Reports

`report_eval.py FLOW` creates `report-full.html` and `report-data.json` with every declared metric, planned/scored coverage, attempt failures, known and unknown cost, latency quantiles, synthetic labels, integrity status, per-case outputs, grader explanations and escaped traces. It is local and needs no external JS/CDN. It does not declare a winner. Scored means exclude unscored attempts and must be read alongside coverage. Started attempts without a finished outcome remain counted as interrupted attempts with unknown cost; even when there are no finished calls, the report cannot label their total spend zero. Reports check required per-result measurement/treatment/case bindings as well as byte hashes, and mark mismatched ownership unverified. A schema-2 manifest must name its actual variant directory. Duplicate case/repetition rows, repeated attempt IDs, and finished attempts without a matching preceding case/repetition start are rejected before aggregation; byte rehashing cannot make these populations valid.

For every schema-2 variant, the report checks `_state.json` metrics, all split populations and repetitions against that variant's bound `comparison_identity`, including the manifest's selected split/repetitions. Drift is a controlled error, rather than a shortened denominator or a silently omitted guardrail. Report metrics and the selected population come from the bound identity. Every result and journal start/finish must name a case in that selected split and a strict integer repetition in range; other split cases, out-of-range repetitions and boolean repetitions are rejected. Missing results remain a valid partial report with the full planned denominator. Legacy exports without that identity remain descriptive and explicitly unverified.

`build-report.mjs FLOW` retains the attributed upstream lite viewer for older workflows and trajectory files. It emphasizes the primary metric and legacy trace naming; use the full reporter for the new runner's hashed trace paths and all-metric evidence. The lite viewer is not a second decision engine.

## Exporting an existing evaluator

Preserve actual per-attempt data rather than reconstructing usage from averages. Record adapter/runtime/lockfile hashes and model configuration before execution; mark historical gaps as unverified. Explain legitimate treatment differences and keep the grader fixed. Include artifacts or trusted references to them, with access controls appropriate to their content. Replay a small exported sample through both the project aggregate and AMind comparison to check denominators and score semantics.

Neither an HTML report nor a self-consistent manifest proves answer isolation, honest instrumentation or generalization. Keep evidence claims tied to what the run actually measured.
