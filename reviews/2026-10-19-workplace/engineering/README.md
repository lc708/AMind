# Engineering workplace task pack

Two local application incident tasks for old Engineering 0.2.1 and current 0.3.1.
`tasks.json` is the root harness metadata, not candidate input. Copy only each
`tasks/<id>/repo` into its own run workspace. Both starters have three healthy
public tests and saved operational captures. They need no installed SDK or network.

Each hidden grader executes the application as subprocesses and reads resulting
artifacts / reopened persistence. It never imports candidate modules into the
privileged grader. Each task has 14 probes clustered into six rubric domains.
Primary score is six conjunctive domain points; raw probe counts are diagnostic.
Required fatal guardrails are separate and cannot be averaged away.

`private/` contains fixed integration fixtures/graders, reference implementations,
empty and prompt-injection controls, and pre-target calibration outputs. Keep the
entire tree, root source checkout, installed/source skills, other run workspaces
and grading history inaccessible to the SUT. The grader must retain access.
Every application subprocess prepends the JSON argv array in
`AMIND_APP_COMMAND_PREFIX_JSON`, including reference/control validation runs.
Set `AMIND_GRADER_SCRATCH` to a writable scratch directory inside that run's
workspace when needed; default scratch is a sibling of the copied candidate repo.
The root harness owns OS isolation; the grader alone is not a sandbox.

Example (after configuring the application sandbox prefix):

```bash
python private/grade_gateway.py --repo /absolute/run/work/grade-repo --output /private/grading/grade.json
python private/grade_durable.py --repo /absolute/run/work/grade-repo --output /private/grading/grade.json
```

Reference, known-bad starter, empty and injection controls were executed before
any target-model trial. The references pass all domains and guardrails; empty and
injection implementations score zero. A prefix canary verifies all 16 gateway and
47 durable application calls pass through the configurable command prefix.
`freeze.json` binds all public code/docs/tests/traces, private rubric and grader
inputs, references and calibration. `verify_freeze.py` checks this boundary.
A pre-target scoring revision changed probe sums into domain points without
changing any application behavior, probe fixture or expected assertion; its
previous candidate freeze is retained under `pre-target-revisions/`.

The task pack and its tests are evaluation fixtures, not product edits or proof
of model/skill improvement. No target model has been called by this lane.
