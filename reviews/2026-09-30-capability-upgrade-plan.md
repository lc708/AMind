# AMind capability-core upgrade

User requirement: strengthen the capability core against the pinned claude-api source. Host adaptation is not an acceptance criterion for superiority.

Baseline: amind-engineering 0.1.0, eval-improve 0.2.0; upstream 8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4. Baseline copies and the full 81-file upstream source are retained in the local audit cache.

Work packages:

1. Preserve upstream task-design, measurement, optimization and operational invariants in a source-to-capability map. Distinguish provider-specific mechanics from reusable capabilities; replace mechanics with destination contracts without dropping the capability.
2. Deliver a provider-neutral application/grader runner with bounded parallelism, timeout/retry accounting, resumable evidence, case/metric validation, file integrity, configuration identities and explicit budget semantics. Repair the existing collector's filename collision.
3. Make comparison enforce compatible experiments, separate allowed treatment changes from measurement drift, handle independent groups, multiple guardrails and quality/cost decisions. Retain exploratory legacy mode without promotion verdicts.
4. Deliver complete cost-search, prompt-audit, migration, context-diagnostic and agent-lifecycle workflows with supporting deterministic tools and maintained implementation recipes.
5. Produce a report that exposes all metrics, completeness, failures, spend/usage, traces and comparisons. Preserve the attributed upstream lite reporter for compatibility.
6. Validate behavior on adversarial offline fixtures, run upstream comparison probes and independent task checks when authorized. Track evidence by capability; do not infer behavioral superiority from word count, a file inventory or unit-test count.
7. Update both skills, source/provenance, installation and series docs; install verified copies with backups. Preserve the AMind knowledge corpus and unrelated user files.

Completion claims must say what is measured, what is supported by code inspection, and what remains unmeasured. No automatic publication, new API credential provisioning or model-spend authorization is implied by this plan.

Implementation status: the original upgrade passed 74 offline application checks and 23 knowledge regressions, verified the source inventory, completed the synthetic demo and installed both skills. The user subsequently authorized all 24 independent paired executions; execution and artifact review are complete. Ten pairs tie; two engineering pairs show narrow advantages on symmetric reviewer follow-up probes. All six evaluation pairs tie, so the preregistered overall-superiority criterion is not met. Nine engineering kernel gaps were repaired, 84 current application checks pass, and Engineering 0.2.1 / Eval Improve 0.3.0 are installed with verified hashes and a backup of the changed package. See [behavioral results](2026-09-30-behavioral-acceptance-results.zh-CN.md); the revised skill has local regression evidence, not a second independent-agent trial. Universal superiority remains unachieved.
