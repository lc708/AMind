# Cost search with quality and mechanism gates

Reduce cost per **completed useful task**, including failures, retries, tools, judges and generated artifacts. A cheaper individual model call can produce a more expensive task if it loops, escalates or fails more often. This workflow preserves the upstream cost-search order, controls and joint-confirmation discipline, with explicit AMind artifacts and comparisons.

## Register adoption gates before round one

1. **Quality:** maximum acceptable loss for the primary task and each important slice; hard invariants remain vetoes. Use a paired non-inferiority analysis, not “the difference wasn't significant.”
2. **Cost:** minimum useful absolute/relative reduction in total task cost, with failed attempts and build/amortization costs included. Set the workload mix and amortization horizon in advance.
3. **Mechanism:** predicted reason for the saving must occur in measured traces/counters. Example: prefix hits rise, emitted reasoning tokens decrease, fewer tool calls occur, or cache-stable requests become cheaper. If the mechanism fails but the mean changes, investigate before adoption.
4. **Stability/operations:** error rate, repeated-run variance, hard slices and tail latency stay within their registered margins. A fragile average is not production readiness.

Use a separate cost-search decision card when quality is a non-inferiority constraint rather than the objective. `compare_runs.py` gives quality gain intervals and per-case all-attempt cost intervals; compare quality's lower bound to `-max_quality_loss`, and cost savings to the registered margin. Its generic `--all-metrics` mode is for the declared grade objective/guardrails, not an automatic cost-optimization policy. Record the joint decision and mechanism evidence explicitly.

## Measurement first

Collect application usage logs and the complete request path. For live APIs, compare normalized token estimates with authoritative account/project usage and cost reports over the same UTC window. Check pagination, project/model dimensions, batch/service tiers, rounding and posting delay. Keep admin credentials separate from inference credentials and out of agents. For subscription-based CLI use, record calls/tokens/time; do not fabricate a dollar charge per token.

Use a dated price card with source URL, exact model/tier/region and input, cached input, output and extra-charge rates. `price_usage.py` requires explicit cache counters, validates cached input as a subset of input and reasoning as a subset of output, and distinguishes reported, estimated, partial and unknown totals. Different provider counters must be normalized before pricing. Cached-write pricing, audio/image modalities, tools, storage and sandboxes require explicit extra counters/rates; do not force them into a text-token formula.

Keep warm/cold cache states separate. Interleave or randomize experiment order when server load or cache warmth can confound the result. Record first-token, completed-task and tail latency separately. A successful result's latency alone omits failures and retry/backoff delay; instrument end-to-end latency when it is an adoption gate.

## Search order

### A. Infrastructure improvements that preserve intended behavior

Measure caching first and keep it enabled consistently after adoption. Place stable instructions, tool schemas and examples before changing per-request content; remove volatile timestamps/IDs from stable prefixes when semantically safe. Inspect actual cache-hit counters and exact prefix changes, including middleware reserialization. A reordered prefix may change both cache and model behavior; re-evaluate quality.

Reduce duplicated context and tool output, introduce retrieval/progressive disclosure for rarely needed material, fix loops and pointless tool calls, then constrain unnecessary visible output. Keep information needed for rare failures and tool/error contracts. Use batch processing for latency-tolerant workloads only after checking lifecycle, output matching and queue limits.

### B. Prompt audit under a frozen model/configuration

Use AMind Engineering's provenance-aware prompt audit. Remove only a supported hypothesis; preserve working constraints, privacy/authorization rules and exact required output. Measure the effect on quality, reasoning/output tokens and calls. Shorter prompt text does not guarantee lower total cost: it can cause more reasoning or repair loops.

### C. Model × effort staircase

Start from the accepted baseline. Vary one model/effort axis at a time to locate a quality/cost frontier. Keep prompt, tools and task budgets fixed where the destination supports them; record unavoidable contract changes. Effort labels do not have equal meaning across models. Do not use an unsupported setting or silently substitute a model.

Use representative traffic, hard cases and repeated stability probes. Stop moving down/left when quality or a guardrail falls outside its band. The point before failure is a candidate, not proof of optimality. Explain untested regions of the search space.

### D. Prompt optimization on the selected model

Freeze the chosen model/effort and optimize prompt or context strategy there. A prompt tuned for the stronger model may behave differently on the cheaper one. Preserve evaluation identity and measure predicted changes in reasoning, output and tool use. Do not move the quality threshold after seeing a miss.

### E. Re-probe cheaper settings

A better prompt may make a previously failing model/effort viable. Test the next cheaper adjacent setting, including hard slices. Conversely, a prompt shortened for one setting may break another. Keep both positive and negative observations in the search log.

### F. Confirm the joint configuration

Individually favorable changes are not additive by assumption. Register the final combined prompt/model/effort/cache/tool configuration and rerun it as one candidate against the frozen baseline. Use validation for selection and a frozen final test for confirmation. Include construction and operational costs. No final confirmation means a promising candidate, not a completed optimization.

## Special cases

**Routing/escalation:** evaluate the full traffic mix including routing overhead, retries, escalations, false-cheap decisions and hard-case escapes. A benchmark of only the easy routed subset is invalid. Freeze router training data and keep test examples out of generated routes/memory.

**Generated indexes or memory:** compare an unchanged rebuild control. Record build source, generation model/config/seed, version/hash and amortized cost. A single lucky generated artifact must not be attributed to the prompt patch. Test freshness and tenant isolation.

**Long contexts:** inspect prefix reuse, irrelevant retrieval, tool-output growth, compaction transitions and loop length. Test continuation correctness after compaction, not only request acceptance. A cache bill reduction does not necessarily reduce rendered context length or reasoning cost.

**No cost data:** report known usage and unknown spend. Prepare a measurement adapter/price card; do not claim a percentage saving from token count alone. Budget reservations stop scheduling new attempts but cannot guarantee a provider invoice ceiling.

## Evidence table

For each candidate include quality interval and non-inferiority margin, important slices, total/unknown cost, absolute/relative saving, latency/error changes, predicted mechanism and measured counter, repeat/rebuild controls, and decision. Mark infeasible or untested settings. Keep the Pareto frontier without hiding candidates that improved cost but failed quality.
