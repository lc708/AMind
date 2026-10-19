# Authorized post-diagnostic report metadata repair

Root authorized implementation after confirming all 42 primary SUT workspace/source copies were already prepared and immutable. These live product changes do not change the primary evaluation treatment. No target outputs/captures, frozen task inputs, grader, experiment harness or source snapshot was accessed or changed in this repair.

## Change

For each schema-2 report variant, `report_contract` checks the separately stored dashboard state against that variant's bound `comparison_identity`:

- All train/validation/test case lists, not only the currently selected split.
- Every declared metric, so a failing guardrail cannot disappear from the display.
- State repetitions and the manifest's selected split/repetitions.

The report derives its selected population and metric list from that identity. Any metadata mismatch exits 2 before writing a new report. Legacy exports remain descriptive and explicitly unverified. Existing result-byte/treatment binding, interrupted spend and duplicate journal/result checks are retained.

Only these product files changed: `skills/eval-improve/scripts/report_eval.py`, `skills/eval-improve/references/artifacts.md`, and `scripts/test_amind_eval_reporting.py`. Root owns version changes, installation and main documentation.

## Validation

All 96 targeted tests passed: 17 reporting regressions plus 79 existing Eval kernel/calibration/application tests. The seven new regressions cover metric-only omission of a failing guardrail, selected and unselected population drift, state repetitions, manifest repetitions, a later variant with its own incompatible metric contract, and healthy multiple variants with separate train/validation/test case populations. The legacy control remains in the suite.

Actual public CLI checks on copied diagnostic exports also passed:

| Export | Before | After |
| --- | --- | --- |
| Only state metric list omits policy | exit0, guardrail omitted, hash-match claim | controlled exit2 |
| Only state selected population truncated | exit0, planned1/scored3, hash-match claim | controlled exit2 |
| Both fields drift | exit0 | controlled exit2 |
| State repetitions drift | previously untested | controlled exit2 |
| Healthy baseline/candidate, both metrics | exit0 | exit0, all metrics/population retained |
| Legacy baseline without schema-2 manifest | descriptive/unverified | descriptive/unverified |

The healthy baseline retains its original four historical attempts, $0.15 known subtotal, one unknown-cost attempt and null total. The complete candidate retains three known-cost attempts. These are offline synthetic accounting checks, not new model/price evidence. All follow-on cases are post-diagnostic validation.

## Evidence retained

- `before/`: exact pre-fix product/test bytes.
- `fix.diff`: complete authorized diff.
- `validation.json`: source hashes, CLI results and test summaries.
- `report-tests.*.txt` / `existing-tests.*.txt`: full targeted test logs.
- `after/*/command.json`: actual argv, exit code and stdout/stderr; healthy/legacy reports are also retained.
- Parent `summary.json`, `field-isolation.json`, `commands/`, `recovery-flow/`, and derivative exports remain pre-fix diagnostic evidence and were not overwritten.
