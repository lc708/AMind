# Adjacent bound-population membership repair

Root authorized this follow-up after independent cross-review found that matching report metadata did not ensure each result belonged to the selected split. Primary SUT copies remained frozen; no main task outputs/captures or frozen evaluation inputs were read or changed.

A schema-2 report now checks every result and every started/finished journal event against the bound selected case IDs and repetition range. Repetitions must be strict integers, so booleans cannot alias zero/one. This blocks other-split results, out-of-range results and foreign attempt costs under a matching-integrity label. It does not require a complete result population: valid partial failure reports retain their full planned denominator and original cost evidence. Legacy exports remain explicitly unverified.

## Actual CLI counterexamples and controls

`validate_cli.py` creates a fresh real CLI export with a training case, two validation cases and a final-test case. It runs before/after reporters in isolated derivative exports. The exact first-patch reporter source is reconstructed and SHA-verified against its already preserved validation receipt; it is not relabelled as the final implementation.

Five invalid scenarios were accepted by that first patch and are now controlled exit2: a unique training result, an out-of-range result repetition, a foreign journal attempt, an out-of-range journal repetition, and a boolean journal repetition. Healthy, legitimate-partial and legacy controls remain exit0. In the partial control, planned2/scored1 and total known spend $0.03 remain visible. No underlying model or API was called.

Seven additional reporting regressions make 24 reporting tests; together with 79 existing Eval tests, all 103 targeted tests passed. Independent engineering review reran 11 fresh public CLI cases, including its original two counterexamples, a foreign journal variant, partial/healthy/legacy controls and metadata drift checks; all behaved as intended.

## Evidence

- `results.json`: eight before/after CLI scenarios, source fingerprints and full summaries.
- `commands/*.json`: exact subprocess argv, return code and stdout/stderr.
- `validation.json`: test counts, logs, source hashes and independent review pointer.
- `report-tests.*.txt`, `existing-tests.*.txt`: full logs.
- `membership-only.diff`: minimal reporter change relative to the first patch.
- `final-fix.diff`: complete authorized report/docs/tests change relative to the original product bytes.
- `first-patch-source/`: hash-verified former reporter and local dependency used only for diagnostic comparison.
- `../repair/` and all 105 original diagnostic files remain unchanged as first-phase evidence.

These are post-diagnostic product correctness checks, separate from the frozen primary model comparison. Root owns release versioning, broad validation, documentation and installation.
