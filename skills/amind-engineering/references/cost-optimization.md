# Optimize cost per useful completed task

Cost work begins with measured workload and a quality floor. Preserve the current model/provider unless changing it is an explicit treatment. Read the companion `eval-improve` reference `references/cost-search.md` for the complete search and adoption procedure; that workflow is the experimental core, not an optional appendix.

## Profile the whole path

Trace user request → input/context construction → model calls → tools/retrieval → retries/escalation → useful outcome. Count failed and abandoned attempts. Separate application inference, judge inference, tool execution, storage, sandbox and index/memory construction. Report absolute per-task cost and latency with success rate, then relative savings.

Prefer actual application logs and account/project usage records. Use admin APIs only with separately scoped access, UTC windows, pagination and dimensions matching the application. Provider invoices may lag events; reconcile windows and known exclusions. Subscription-based Codex usage has its own accounting; do not turn CLI token counts into invented API charges.

Normalize the provider's usage semantics. With OpenAI-style counters, cached input is a subset of total input and reasoning is a subset of total output. Adding either twice inflates cost. Other providers may expose cache writes separately; preserve that difference. Keep multimodal and built-in-tool charges explicit. Missing usage/rates are unknown, not zero. The eval skill's `price_usage.py` applies a dated explicit rate card without hard-coded prices.

## Choose the mechanism from the workload

| Observed workload | First mechanism to investigate | Required evidence |
|---|---|---|
| Large repeated prefix | Stable prompt/tool/example prefix and supported caching | Actual cache-hit counters, warm/cold split, same quality |
| Huge rarely used context | Retrieval/progressive disclosure and narrower tool output | Needed facts still available on rare/hard cases |
| Many repeated calls | Loop termination, tool selection and deterministic checks | Fewer calls per completed task, unchanged completion rate |
| Long visible output | User-relevant concision / supported output controls | Completeness and downstream parsing retained |
| Latency-tolerant bulk work | Supported batch endpoint | Lifecycle/error matching and real tier price verified |
| Excess reasoning for simple tasks | Supported effort/task budget, then model alternatives | Quality band, hard slices, actual reasoning/output usage |
| Mixed easy/hard traffic | Routing/escalation under full-traffic eval | Router overhead, false-cheap failures and escalation costs |
| Rebuilt learned artifacts | Stable build/reuse policy and amortization | Unchanged rebuild controls, freshness and build cost |

Caching is a measured infrastructure optimization, not a prompt instruction saying “cache this.” Exact prefix changes, tool schemas, message ordering and volatile metadata can change hits. A cache saving does not necessarily reduce context size. Cache sharing must not violate tenant/privacy boundaries.

Progressive disclosure can reduce irrelevant input while preserving access to necessary material. Evaluate failures caused by retrieval misses and unloaded tool descriptions. A smaller prompt that causes more reasoning/tool calls may cost more overall.

## Execute and decide

Register quality non-inferiority margins, minimum meaningful cost saving, stability/latency limits and the predicted mechanism before searching. Establish unchanged-run controls. Work through caching/context/loop/output improvements, prompt audit, model×effort staircase, prompt tuning on the selected model, a cheaper-setting re-probe, and joint confirmation of the final combination.

Change one mechanism at a time unless an inseparable bundle is declared. Freeze measurement, target snapshots and price-card version. Use independent groups and paired differences; include failures and unknown spend. A nonsignificant quality drop is not evidence of non-inferiority. Require the expected mechanism to appear in counters/traces and rerun the combined configuration before adoption.

Deliver a cost breakdown, tested frontier, rejected candidates and reasons, quality/guardrail intervals, measured mechanism, final-test status and rollback. If only estimates or synthetic tests exist, state that instead of claiming a live saving.
