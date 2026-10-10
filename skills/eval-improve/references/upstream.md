# Provenance and adaptation

Source: Anthropic's `claude-api` skill in [anthropics/skills](https://github.com/anthropics/skills/tree/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/claude-api), inspected 2026-09-30.

Pinned commit: `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` (2026-09-29).

The workflows are adapted from `shared/evals/build-eval.md`, `eval-audit.md`, `eval-hillclimb.md`, `cost-hillclimb.md`, and the report schema/runner scaffold. Their published context is [Automating eval design and hillclimbing with Claude](https://claude.dev/blog/automating-eval-design-and-hillclimbing/) (2026-09-28).

`scripts/build-report.mjs` is an unchanged copy of upstream `shared/evals/report/build-report-lite.mjs`, SHA-256 `af79ca5fa5f06747dbcaa1d40017c8c8e81e0aa11cb8e32b848043893cdb03c7`. The Apache 2.0 license is retained in `LICENSE.txt`. The upstream tree contains no NOTICE file for this skill at the pinned revision.

This adaptation changes the following:

- Routes tasks through a standalone `eval-improve` skill and the current agent's tools.
- Preserves existing model providers and supplies a provider-neutral process runner with project-specific adapters; it does not install a Claude SDK or force a model choice.
- Uses project-local `.eval-improve/` output by default, with explicit paths to the installed reporter.
- Separates validation used for candidate selection from an untouched final test, and discloses unblinded or undersized studies.
- Carries existing authorization forward; adds no repeated approval for already authorized reversible work. Additional model spend still requires an established scope and budget.
- Adds `compare_runs.py` for deterministic, complete-pair case-bootstrap comparisons. This helper is locally authored and does not replace a statistical or evaluation-design audit.
- Documents the limits of the upstream lite report rather than claiming the full viewer's features.

This module is maintained in AMind's `skills/eval-improve` directory, retaining its existing invocation name. The companion `amind-engineering` skill covers prompt auditing, cost optimization, model/API migration, SDK upgrades, state migration and agent implementation using Codex/OpenAI contracts. The two modules cover the source skill's eight workflow intentions without claiming identical provider features.

Version 0.2.0 adds AMind series metadata, Codex response collection (`scripts/collect_codex.py`), and repository-maintained installation and offline tests. The collector plans by default, uses bounded fresh CLI runs when explicitly executed, records failures/native usage, and leaves outputs ungraded until a real grader processes them. Python helpers are locally authored. The lite reporter remains unchanged.

Updates should compare a pinned upstream revision, preserve local host/provider adaptations, validate executable helpers, and record actual behavioral testing separately from file/format checks.

## Validation at creation

The initial standalone version passed nine offline tests on 2026-09-30. The repository suite at `scripts/test_amind_app_skills.py` retains those comparison/report checks and adds synthetic CLI collection and installation checks. These do not constitute a live model evaluation or an independent behavioral trial of either skill. Run the current suite to verify the current version; no model invocation is required.

## Capability core 0.3.0

Adds a complete application/grader runner, bounded process deadlines/output/concurrency, classified retries with application-output reuse for judge retries, all-attempt cost, target and measurement identities, case/group contracts, frozen baseline outputs, resume and explicit crash reconciliation. The strict comparator verifies identities, averages repetitions within cases, resamples independent groups and supports registered objective/guardrail gates. Final tests require a selection certificate. Calibration, rate-card pricing and a full report complement the unchanged upstream lite viewer.

The independent cost-search workflow preserves upstream staged search, mechanism gates, unchanged-build controls, full-traffic routing measurement and joint confirmation. These are retained upstream strengths, not AMind inventions. Native additions and selected runner-contract improvements are tested offline in the repository. See the dated verification report and behavioral acceptance plan; no general live-model or autonomous-skill superiority is asserted.
