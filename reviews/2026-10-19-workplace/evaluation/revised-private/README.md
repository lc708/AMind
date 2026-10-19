# Disclosed semantic-contract grader revision

This lane was created after observing all twelve main Eval outcomes. It is a
measurement repair, not a product treatment, new independent task, or holdout.
Original frozen graders, captures and scores remain intact.

The original fourteen probes, five domain scores, and original guardrail
mappings are retained. Two expected values accept semantic alternatives:

- Duplicate results must still invalidate integrity and hold the release. For
  the duplicate fixture, retaining one copy per key (two scored keys) or removing
  every copy of the duplicated key (one scored key) is accepted. Counting all
  three rows, omitting invalidation, or reporting ready still fails.
- Absent negative controls must explicitly yield `fpr: null`, hold, and list the
  missing rate as either `fpr` or `false_positive_rate`. A label alone is
  insufficient. Missing fields are distinguished from explicit nulls.

All stage, cost, identity, paired-population, drift and class-denominator checks
remain unchanged. Calibration includes the original starter, empty and injection
controls, a fluent but nonfunctional control, full references, both permitted
semantic alternatives, and deliberately incorrect duplicate, stage, absent-class,
omitted-field and pair-intersection variants. A genuine measured FPR of zero is
checked separately against known negative examples.

Every application runs in a fresh portable `grade-revised-repo`, via
`AMIND_APP_COMMAND_PREFIX_JSON`, under the frozen grading policy with network
denied. The previous `grade-repo` is additionally hidden; private graders,
references, original task repos, skills, outputs and other trial workspaces stay
unreadable. No candidate module is imported by the privileged grader.

`revision-freeze.json` hashes this lane before calibration and captured-delivery
rescoring. `calibration/summary.json` must pass before `../grade_revised.py`
admits captured deliveries. Revised per-run outputs go to `app-grades-revised/`,
and the derived twelve-run summary is `main-plan-evaluation-scores-revised.json`.
The original engineering scores are not rerun or rewritten.
