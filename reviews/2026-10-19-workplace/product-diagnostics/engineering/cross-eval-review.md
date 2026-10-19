# Independent read-only review: Eval report state binding

Only current product code/tests and fresh deterministic CLI fixtures were used.
No main target runs/captures or frozen workplace inputs were read or changed.
No product/test source changes or target-model/network calls were made.
Raw CLI invocations, outputs and reporter source hash are in `cross-eval-review.json`.

The requested `_state.json` fix passes independent checks. A fresh experiment has
one train item, two selected validation items and one test item, two variants,
quality=1 and policy=0. Both healthy variants retain planned/scored=2, all metrics
including the failed policy, and $0.04 cost with matching export hashes. Removing
one selected ID, removing the nonempty train population, omitting policy, making
reps boolean, or changing only the candidate manifest split all exit 2 with the
appropriate contract error. Legacy exports remain descriptive, unverified and
retain $0.04 per variant.

A separate adjacent population check is still missing. Result keys are checked
for type and uniqueness but not membership in the bound selected split or the
repetition range:

- Append a copy of result a under the unique key `(train-only,0)`, update its
  result_identity.case_id and results_sha256 only. The state/identity remain
  untouched. The public reporter exits 0, says hashes match export, and reports
  scored=3 against planned=2, counting the unselected train item in both metrics.
- Change row b.rep and its result_identity.rep to 7 with bound reps=1, updating
  only results_sha256. The reporter again exits 0 with matching hashes, counting
  this nonexistent repetition among the two selected observations.

This is a structural export-validation gap, not a claim that hashes authenticate
arbitrary edited grades. It can be closed by checking every v2 result key against
`planned_ids × range(reps)` before aggregation; partial legitimate exports should
remain permitted and preserve their full planned denominator. The `_state` fix
itself is accepted; the membership findings have been sent to root and the Eval
owner for their decision and repair. They are post-diagnostic evidence, separate
from all primary model task outcomes.

## Independent recheck after membership repair

The Eval owner added selected-population validation after the findings above.
The original two counterexamples now both exit 2 with `result outside bound
selected split/repetition population`. A matching start/finish pair reassigned to
an unselected train case also exits 2 as an attempt outside the bound population.

The same fresh multi-split fixture remains healthy for both variants; policy=0
is retained and planned/scored remain 2/2 with $0.04 each. A legitimate partial
result export remains reportable with planned=2/scored=1, policy=0 and the full
$0.04 spend captured by its two finished attempts. Legacy remains explicitly
unverified. The previous `_state` and manifest drift probes still exit 2.
All 11 independent public-CLI scenarios passed their intended outcomes. Original
pre-membership evidence remains in the JSON; new source hash and full calls are
appended under `after_membership_source_sha256` and `after_membership_scenarios`.
No Eval source/test files or primary-trial artifacts were changed by this review.
