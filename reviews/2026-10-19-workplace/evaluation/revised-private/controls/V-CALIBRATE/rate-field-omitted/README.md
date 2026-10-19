# Judgecheck: repair the support judge rollout review

Customer-success agents propose a new automatic judge for detecting genuine support-policy issues. The pilot dashboard looked excellent, but clean tickets disappeared, unresolved adjudications became negative labels, and one security worker was still unknown. The previous judge and new judge were also compared on an incomplete intersection of examples. Repair this existing standard-library pipeline so reviewers can distinguish genuine changes from missing evidence. Keep modules and CLI maintainable.

Run `python3 -m judgecheck --input examples/review.json`. It prints one JSON review packet. Run public tests with `python3 -m unittest discover -s tests -v`. No network, hosted model or AMind helper imports are needed.

## Input contract

The job declares `positive_event` (here label 1 means a genuine policy issue), `current`, optional `baseline` and `drift_reference`, optional `deployment_prevalence`, `required_workers`, `worker_reports`, and `limits:{max_fpr_increase,min_labeled_families}`. Every cohort has a complete exact `identity:{dataset_version,judge,grader_version,rubric}` and `records:[{id,rep?,family,split,human,decision}]`. IDs/rep pairs must be unique; rep defaults to 0. Human and decision are integer binary labels or null. Null decision is abstention, null human is unresolved adjudication. They stay visible and do not enter a confusion cell. Splits are train/validation/holdout; the same family cannot cross them. Family count, rather than number of repeated rows, is the declared independent evidence population.

Confusion statistics use only adjudicated, non-abstained examples. Keep separate denominators for adjudicated/human-positive/human-negative/evaluated/evaluated-positive/evaluated-negative/abstained/unknown-human. Expose judgment coverage over all current records. Missing positive/negative evidence makes its rate null and lists it in `unmeasured`; a missing class is not zero error. FPR, FNR, precision and recall need their correct class denominators. Supplied deployment prevalence gives a **scenario** precision from sensitivity/FPR, separate from sample precision, never an observed population statistic. Invalid/unavailable prevalence or rates produce unmeasured/null.

Paired judges require identical case/rep/human/family/split populations, same dataset and rubric. Judge/grader versions may change. Preserve total pairs and comparable pairs; abstentions make comparison partial. Report improved/regressed counts and agreement delta only over comparable adjudicated binary pairs. Missing pairs or incompatible identities invalidate the comparison; never silently use an intersection.

Drift holds the judge/grader/rubric fixed across cohorts; dataset versions may differ. Compare FPR increase with the declared margin (strictly greater means alert). Missing negative controls make drift unmeasured. Changed judges are an invalid drift comparison, not cohort drift. These counts are descriptive, not significance or causality estimates.

Worker identity matters: every required worker must explicitly succeed. Missing/failed/unknown workers remain `uncovered`; extra or duplicate workers cannot substitute for required ones. No required workers means unmeasured.

## JSON review packet

Keep the existing top-level `status,calibration,family_count,workers,paired,drift,deployment_precision,integrity,limits`. Calibration exposes `confusion,fpr,fnr,precision,recall,denominators,judgment_coverage,unmeasured`. Workers expose expected/completed/uncovered/status. Paired status is unmeasured/invalid/partial/complete with pairs/evaluated_pairs/improved/regressed/agreement_delta when meaningful. Drift exposes status and fpr_delta; statuses are unmeasured/invalid/alert/within_margin. Deployment precision is `{status:scenario|unmeasured,value:number|null}`. Integrity is `{status:verified|invalid,issues:[...]}`.

`ready_for_review` needs verified integrity, both measured classes, complete judgments, enough families, all required workers, complete paired comparison when supplied, and within-margin drift when supplied. Otherwise hold. Readiness is not deployment approval. Semantic holds print JSON and exit 0; malformed/unreadable input prints JSON error and exits 2.
