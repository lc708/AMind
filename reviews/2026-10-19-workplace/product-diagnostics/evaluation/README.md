# Current Eval CLI product diagnostic: unbound dashboard state hides a guardrail

This is an offline correctness diagnostic of the actual current `skills/eval-improve` public CLIs. It does not inspect any 2026-10-19 workplace target trial, call a target model, change a product file, or alter a frozen task/grader.

## Concrete finding

`report_eval.py` verifies the schema-2 manifest and result/journal hashes, but takes the report's metric list, planned case IDs and repetition fallback from the separately mutable `_state.json`. It never verifies those UI fields against `manifest.comparison_identity`.

A damaged export index can therefore silently omit a declared failing guardrail while the report still says `hashes match export`. An independent one-field population mutation also yields `planned_observations=1` and `scored_observations=3` without any duplicate result. No manifest, result or attempt bytes were rewritten, no result identity was changed, and no byte hash was refreshed.

This differs from the previously repaired duplicate-results and copied-variant defects. Every row here is unique, uses the correct directory/variant and carries a valid original treatment binding. The gap is the unbound source of report metadata. The strict comparison CLI already rejects the same exports with `requested population/metrics/reps differ from experiment identity`; this is a report-validation omission, not a successful bypass of the strict promotion decision.

## Actual end-to-end public workflow and controls

`reproduce.py` executed:

1. `run_eval.py` plan, without invoking the application.
2. Actual local runner/application dispatch. It killed both real process groups after the durable started event and before any result or finished event. No journal was edited to invent a crash.
3. `report_eval.py` on the real interrupted export; unknown cost remained unknown.
4. Resume without reconciliation, correctly rejected.
5. `reconcile_run.py` plan then apply with explicit externally observed local PID termination evidence and unknown cost.
6. Explicit retry-safe resume within the original limits. Baseline completed all three cases with four historical attempts, known subtotal $0.15 and one unknown-cost attempt.
7. Candidate execution, three complete cases and three known-cost attempts ($0.15).
8. Native export/report. Baseline quality/policy means are 0/1, candidate means 1/0. Both metrics are displayed in the undamaged report.
9. Strict all-metric comparison correctly returns `do_not_promote` because the policy guardrail regressed. Cost comparison correctly returns `incomplete` rather than treating the abandoned call as free.
10. Copied export with only `_state.json` changed: report succeeds with a shortened population and omitted guardrail; strict comparison rejects it.

`isolate_state_fields.py` then confirmed each `_state.json` change independently. These follow-on checks are diagnostic validation, not holdout evidence.

## Minimal public-entrypoint repro on the saved derivative export

Run from the worktree root:

```sh
python3 -B skills/eval-improve/scripts/report_eval.py reviews/2026-10-19-workplace/product-diagnostics/evaluation/state-metrics-only
python3 -B skills/eval-improve/scripts/compare_runs.py --flow reviews/2026-10-19-workplace/product-diagnostics/evaluation/state-metrics-only --candidate v1 --split val --reps 1 --all-metrics --bootstrap 200
```

The first exits 0, lists only quality and labels integrity matching. The second exits 2 for incompatible state. The pristine `recovery-flow` preserves the original manifest/results/attempts and complete two-metric report.

## Proposed minimal fix, held for root authorization after main trials finish

For schema-2 reports, validate `_state` split IDs, metrics and repetitions against the corresponding manifest comparison identity before aggregation. Prefer deriving planned population and the declared metric list from that bound identity. Reject inconsistent exports with a clear controlled error; do not silently hide mismatched metrics. Retain descriptive legacy reporting, visibly unverified, when no schema-2 identity exists.

Add independent regression variants for metric-only omission, case-only omission, repetition mismatch and an unchanged valid/legacy control. Keep these separate from the frozen workplace task scores. Product implementation has not started.

## Evidence

- `summary.json`: lifecycle controls, authentic clean reports, damaged report and strict comparison, product source hashes.
- `commands/*.json`: full argv, exit code, stdout/stderr for each public CLI.
- `commands/02-interruption.json`: actual process IDs and persisted started-only boundary.
- `recovery-flow/`: pristine native runner manifests, results, attempts, reconciliation, traces and reports.
- `state-index-transform.json`: exact two-field mutation and byte-for-byte checks for untouched evidence.
- `field-isolation.json`: separate metric-only and population-only variants.
- `fixture/`: deterministic local application, grader, public cases/references and fixed experiment card.

The report does not currently assert an automatic winner, and strict comparison remains protective. This finding supports repairing report completeness/integrity claims; it does not show production model failure, hidden trial contamination or adversarial authentication.
