# Post-diagnostic Engineering scoring correction

The frozen D14 probe required `not_covered` for a review blocked by a failed
inspection. The public README defines the required behavior without assigning
that state name. All three old submissions used `skipped` while correctly
retaining the failed item, avoiding review dispatch and reporting half coverage.
The original scores and all frozen files are preserved.

Only D14's probe function changed. It accepts `skipped` and `not_covered`, and
checks the actual incomplete report, immutable population gap, four receiver
receipts, attempt count, operation identities and summary receipt coverage.
All other Durable probes are unchanged. The Gateway grader is byte-identical;
G06's rejection of contradictory attribution follows the public error contract.
The common runner only adds optional observation evidence to case records.

`control-validation.json` records eleven controls: both references pass all
fourteen probes; both starters, empty outputs and injection outputs score zero;
a reference using `skipped` still passes; a reference that dispatches review
after failed inspection fails D14; a reference falsely reporting full coverage
also fails D14. These are post-diagnostic controls, not new target tasks.

`rescore.py` copied every one of the twelve captured Engineering repositories
to `grade-revised-eng-repo` in its existing temporary workspace. Every application
subprocess used a copy of its original network-denied portable grading policy.
Reference/control applications also ran behind the same policy generator.
No candidate module was imported into the privileged grader.

Results are in `../../app-grades-revised-eng/` and
`../../main-plan-engineering-scores-revised.json`. Durable ties at 6/6 in every
repetition. Gateway remains old 6,5,6 and current 6,6,6. The one Gateway failure
accepts conflicting attribution instead of returning exit 2; that particular
probe does not establish a browser text leak.

The one-shot runner refuses existing destinations to preserve evidence:

```sh
python3 -B reviews/2026-10-19-workplace/engineering/revised-private/rescore.py
```

Individual graders accept `--repo /absolute/portable/repo`. Set
`AMIND_APP_COMMAND_PREFIX_JSON` to the sandbox command prefix and
`AMIND_GRADER_SCRATCH` to an allowed temporary workspace. The recorded run used
the original policies byte for byte. `original-evidence-after.json` confirms all
175 frozen measurement files and 889 original capture/grade files remained
unchanged. No target model calls were made. This correction was made after
inspecting the target results and must be reported alongside the original scores.
