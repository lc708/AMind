# Audit an evaluation before trusting its score

Audit the measurement as an application with its own failure modes. Use the existing dataset, runner, rubric and recent results. Return concrete evidence: affected cases, file/line or trace, observed consequence, proposed correction and how to verify it. An audit request alone does not authorize rewriting the target.

## Trace the complete path

Follow a real case through loading, context assembly, application execution, output capture, grading, result serialization and aggregation. Check that grade, transcript, usage and model identity belong to the same attempt. A returned string from a model stub is not evidence that a production tool loop was exercised.

| Layer | Audit question | Falsification / probe |
|---|---|---|
| Population | Does sampling reflect real workload and rare costly failures? | Compare slice counts to traffic; report synthetic-only gaps |
| Independence | Are siblings, customers or documents split apart? | Group IDs; duplicate/near-duplicate review; group-wise split |
| Target fidelity | Is the real entry point used with real context wiring? | Deliberately break retrieval/tool wiring and require failure |
| State | Is each case reset; are replicas accidentally sharing memory? | Reorder cases; run alone vs batch; deterministic fixture reset |
| Leakage | Can target or optimizer read answers/test content? | Protected canary access test in the actual sandbox |
| Rubric validity | Does the metric measure the user's decision? | Near-miss wrong answer, unsupported citation, attractive but useless prose |
| Judge robustness | Is it vulnerable to answer instructions/style/order? | Prompt injection, A/B reversal, verbosity-matched counterexamples |
| Auditor incentives | Can finding more issues increase reward even when nothing is wrong? | Clean negatives, harmless anomalies, plausible invented failures and rubric-score exploitation |
| Detection errors | Is high agreement hiding a low-base-rate false-positive problem? | Report TP/TN/FP/FN, class denominators, FPR/FNR and deployment-prevalence scenarios |
| Stage coverage | Does aggregate success hide a missing worker or failed phase? | Declare required stages, item denominators and uncovered work; remove a child's output and require failure |
| Artifact grading | Is success established by files/actions? | Missing/extra file, no-op, wrong database row, misleading final message |
| Serving identity | Are model aliases/fallbacks silently changing? | Record actual served model; exercise substitution/incomplete paths |
| Failure policy | Are hard cases or failed attempts excluded invisibly? | Missing case, duplicate rep, timeout, judge crash and retry |
| Accounting | Are all application, tool, judge and failed calls counted? | Reconcile attempt ledger and external usage records |
| Comparison | Do dataset, grader, runtime and split identities match? | Deliberately change one fixed field; comparison must refuse |
| Uncertainty | Are repeated attempts treated as independent tasks? | Cluster related cases; average reps within cases; paired differences |
| Selection | Has “test” influenced earlier choices? | Read experiment history; relabel as validation and obtain new final evidence |
| Reporting | Can a high mean hide incomplete coverage or a veto failure? | All-metric report; guarded promotion; unknown cost remains unknown |

## Severity and repair

**Decision invalid:** answer leakage; wrong target path; mismatched scoring versions; selective removal of difficult cases; grader rewards material wrong answers; a changed protected harness accepted as comparable. Stop promotion, preserve artifacts, fix the measurement, and rerun/rescore affected variants.

**Decision fragile:** narrow slices, unstable judge, too few independent groups, repeated peeking, stale price card, unrealistic tool fixtures or untested side effects. Narrow the claim and collect evidence for the fragile dimension.

**Operational defect:** path collision, runaway retry, missing usage, duplicated result or lost trace. Repair the runner and use adversarial fixtures to reproduce the defect before/after. A passing utility test does not validate the product rubric.

## Required negative controls

A grader that cannot fail known-bad behavior is not ready. Include a constant answer, an empty answer, a fluent wrong answer, a correct but differently phrased answer, an injected instruction to the judge, a missing artifact, a forbidden mutation and a deliberately broken dependency where applicable. Do not tune an application to pass a broken grader.

For an issue-detection auditor, also include adjudicated clean tasks and harmless deviations: a high finding count is not accuracy. Define which event label 1 represents. Report false positives on clean tasks separately from false negatives on genuine issues. Curated positive-heavy samples do not establish deployment precision; use an explicit prevalence scenario and retain the class denominators. Re-adjudicate disagreements independently of the judge before changing the rubric. Missing negative controls, swap checks or repeat trials remain unmeasured. Use [calibration helpers](accounting-calibration.md) to compare the same cases under two judges or audit a fixed judge across drift cohorts.

Check grade range and typing; missing numeric observations; ID/rep uniqueness; denominator; planned versus completed cases; requested versus served model; retry and failure spend; linked paths and unexpected artifact access. Verify that lower-is-better metrics cannot be accidentally interpreted in the opposite direction.

## Statistics and reading results

Compare the paired **difference**, not overlap of two marginal confidence intervals. Average repeated attempts within each case; resample whole independent groups. The bundled comparison enforces these mechanics but relies on truthful grouping. Few groups, skewed tails, bounded metrics near a ceiling and adaptive selection limit bootstrap claims. No amount of bootstrap draws creates new independent evidence.

For multiple predeclared objectives/guardrails, use the all-metrics gate with familywise intervals or a justified project-specific procedure. This correction covers registered metrics, not an unlimited number of candidate searches. For hard invariants, any confirmed violation can veto regardless of the aggregate interval. Validate cost, latency and reliability separately; a score gain from failed calls being dropped is not a gain.

Use `compare_runs.py --allow-legacy` only for exploration of old artifacts. Its result cannot establish improvement or drive promotion. Re-export with verified provenance to enter the strict path; do not fabricate manifests after looking at desired scores.

## Deliver

State whether the evaluation can support its intended decision. Show the highest-impact invalidity first, the raw evidence that establishes it, and the smallest correction. Distinguish what was executed from what was inspected. Record remaining uncertainty and which new observation would resolve it.
