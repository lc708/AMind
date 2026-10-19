# Improve through controlled experiments

Optimize an explicit application surface against a trustworthy measurement. Read [eval audit](eval-audit.md); if the evaluator is missing or invalid, build/repair it before searching. For a cost objective use [cost search](cost-search.md), which has additional adoption gates.

## Establish the baseline and search contract

Inspect implementation, failed cases and actual call path. Record target files/configuration, permitted changes, protected evaluator files, metric direction, minimum useful gain, guardrails and total search budget. Preserve the baseline and a runnable rollback. Freeze data/grader/runtime identities. Changing a grader to make the new answer pass is a new measurement, not an application improvement.

Split by independent task groups: train for diagnosis and prompt/candidate development; validation for selection; final test only after selection is frozen. Restrict optimizer access to held-out answers/content with real access controls. A separate role prompt, filesystem read-only flag or a directory named `test` does not enforce blindness.

Run the baseline with recorded model/settings, raw usage and enough repetitions to reveal relevant variability within budget. Replicas do not multiply the number of independent tasks. Establish no-op controls: rerun an unchanged configuration, rebuild generated memory/indexes without code changes if generation itself introduces variance, and measure grader consistency. Without controls, variance can look like a successful optimization.

## Each round

1. **Diagnose:** inspect concrete failures and traces, including serving/tool/judge failures. Classify prompt ambiguity, missing context, bad tools, orchestration, state corruption, capability limits, or an invalid test. Do not rewrite everything because one score is low.
2. **State a falsifiable hypothesis:** “Retrieval truncates the only cited exception; retaining the final paragraph should fix exception questions without changing common cases.” Predict both the target improvement and possible regressions. Record affected slices.
3. **Choose the smallest coherent treatment:** change one mechanism or an explicitly registered bundle. Version actual prompt/code/skill/config files. A variant label alone is insufficient. Keep the evaluator, data and unrelated settings fixed.
4. **Run the cheapest disconfirming probe:** syntax/contracts/fixtures, then diagnostic training cases, then the planned validation population. Do not select or report only the favorable cases. Count all attempts and errors.
5. **Compare:** strict paired, group-aware comparisons; all guardrails; coverage; application/judge/retry cost; latency and failure classes. Require the predicted mechanism to be visible in traces/usage, not only a favorable score.
6. **Keep, revert or investigate:** retain the simpler/cheaper baseline when a gain is unresolved; revert clear regressions. Inspect contradictory slices and repeat an unchanged control if noise is plausible. Leave an experiment record even for rejected changes.

Store each round's hypothesis, files/config hash, budget, run paths, observed effect, uncertainty, failure cases, mechanism evidence and decision. Freeze baseline comparator outputs for pairwise grading; never overwrite them with a later candidate's output. Keep the candidate's grader blind to the variant label.

Include a judge/auditor gaming probe when optimization targets finding count, self-reported completion or another easy proxy. A higher proxy can mean invented issues, omitted difficult workers or exploiting the rubric. Keep clean negatives and a fixed independently adjudicated calibration set; compare judge changes on paired cases and regrade both variants after a rubric change. Missing negative-control, stage-coverage or drift evidence stays unmeasured.

## Search efficiency

Use a small number of meaningful candidates rather than shotgun edits. Improvement may come from retrieval, tool contracts, deterministic validation, response budgets, state management or architecture; prompt changes are not the only lever. If a deterministic rule handles an invariant more reliably, move it into code and test both accept/reject paths.

Use bounded concurrency only for independent, isolated cases. For parallel proposal generation, use independent agents only when host policy and the user authorize that delegation; merge evidence, not unreviewed patches. This skill does not grant permission to spawn agents or create chats.

If learned memory, routers or retrieval indexes change, record the generated artifact, seed/source data and construction cost. Compare unchanged rebuild controls. A cached or built artifact obtained from held-out data invalidates the holdout even if its current file contains no literal answer.

Stop when the registered quality target is met, useful gains plateau, remaining budget cannot support a fair comparison, or an operational limit is reached. Predeclare what counts as a plateau and minimum useful change. Do not treat a budget exhaustion as successful optimization.

## Candidate selection and final evidence

`compare_runs.py --all-metrics` enforces registered objective/guardrail margins and corrects the registered metric family. Inspect hard invariants and operational gates as well. A validation win is a selection signal; it is not unbiased final proof after many adaptive trials.

Choose one candidate, record why, and use `seal_selection.py` to bind the chosen target hashes and measurement contract before the final run. `run_eval.py --split test` requires that selection certificate. Use a separate final flow for the same frozen baseline/candidate. Both must use the same certificate, cases, grader, runtime and repetitions. A new candidate or changed target needs a new selection process; do not keep tuning on test outcomes.

Final test verifies the selected change. If it fails or is inconclusive, report that and retain the baseline unless the user knowingly accepts a narrower tradeoff. Show absolute values and intervals; do not turn statistical inconclusiveness into proof of equivalence. The certificate detects accidental workflow drift within these artifacts; it cannot stop a person reading data or starting another flow.

## Handoff

Deliver working change and rollback; compact experiment history; trusted comparison/report paths; objective and each guardrail; cost/latency/error coverage; final test status; residual risks and unmeasured dimensions. State “improved on this evaluation” with population and conditions. Do not claim another skill/model is universally worse from a single application result.
