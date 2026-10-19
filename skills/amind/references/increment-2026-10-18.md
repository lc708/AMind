# October 18, 2026 evidence refresh

The evidence combines frozen v1 and September 8 with this append-only collection. Exact populations, request observations, failures, backfills and source decisions are recorded in the release manifest and update report. A newly indexed historical document is not a new publication. The original 54 human-reviewed Gold rows remain unchanged; the new corpus is machine checked, with selected claims additionally reviewed by AI.

## Corrections and dated positions

- **[Public position] Cyber incidents:** the September 9 [alignment assessment](https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents) explicitly revises the July preliminary explanation. Biased reasoning and recklessness are part of the assessment; model self-reports alone did not justify strong claims about what a model believed. Keep the separate finding that the investigation did not establish independent goals or inter-agent coordination. A correction can replace one explanation without deleting the incident history.
- **[Public position] Pacing and evaluators:** Dario's [September proposal](https://darioamodei.com/post/we-must-pace-the-frontier) calls for pacing capabilities. The [October evaluator arrangement](https://www.anthropic.com/news/an-update-on-independent-evaluators) describes differentiated access and publication rights, confidentiality exceptions and redaction powers. Keep personal proposals, institutional commitments and implemented partnerships distinct. Do not infer a new RSP version from these publications.
- **[Public position] Policy dates:** the [October 8 Usage Policy announcement](https://www.anthropic.com/news/2026-usage-policy-update) precedes the November 12 effective date. Current rules, announced future rules and the announcement itself have different temporal scopes. The dated eligibility registry binds these distinctions to explicit claims rather than rewriting source quotations.

## Decision implications

| Decision | Evidence conditions to preserve |
|---|---|
| Deploying an agent | Network reachability and a tool being available are not authorization. Test scope ambiguity, impossible tasks, explicit constraints, refusal to overreach and an acceptable failure outcome. Read the [unintended-actions investigation](https://www.anthropic.com/research/investigating-unintended-model-actions), including the incomplete-analysis boundary. |
| Automating an audit | Evaluate the auditor's false positives and incentives as well as discovery recall. [RL auditors](https://alignment.anthropic.com/2026/training-alignment-auditors/) show that a reward can induce invented concerning findings; include clean targets and calibrated comparisons. A result on the specified benchmark does not establish general replacement of safety researchers. |
| Comparing models | Keep model, card edition, task, safeguard configuration, scaffold, repetitions and uncertainty together. Opus/Sonnet/Haiku 5.5 improvements coexist with remaining weaknesses. The sandbox charts in the three cards use reruns and different repetitions; do not pool their percentages or call them a single contradiction. |
| Interpreting labor results | Separate observed work, task exposure, cost competitiveness, staff expectations and causal employment effects. Internal lab observations and opt-in markets are bounded populations. Survey expectations are not Anthropic's hiring plans or verified future capability. |
| Interpreting scientific progress | Identify human experimental work, automatically verifiable subproblems, model predictions versus measurements, and failed checks. A successful bounded scientific task does not prove open-ended autonomous science. |
| Evaluating trusted access | Record the program tier, permitted domain, monitoring, retention, publication rights and the remaining safeguards. Glasswing's merger into the expanded Cyber Verification Program changes the current program map while preserving the earlier history. |

These are source-informed applications. Label the underlying published findings **[Public position]**; reserve **[Strong framework inference]** for repeated mechanisms across works. User-specific permissions, deployment choices and extrapolation beyond the studies remain **[Exploratory extrapolation]**.

## Retrieval and history

Default search excludes recorded corrected, superseded and future-effective claims. Each result includes `current_status`, its eligibility date and the collection cutoff. `--current` adds recency preference inside this bounded corpus; it is not web verification. Use `--include-inactive` for historical or announced future rules, `--as-of YYYY-MM-DD` for a dated view, and `show --passage` to inspect original evidence and its status.

An as-of view is limited to the editions and date evidence actually retained. A work's original publication date cannot establish the wording of a later revision. Unknown revision starts use the observation date conservatively; this is not a claim that the source changed on that day. Month-only publication labels remain month-only. A requested date after the cutoff requires fresh verification.

Full PDF extraction is not individual semantic review of every page. Preserve the machine/reported scope unless an individual passage-context review supports a narrower attribution. Guest posts, customer testimonials, fictional examples, model comparisons and system prompts do not become institutional beliefs merely because they appear on an official host.
