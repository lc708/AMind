# Architecture migration and bounded review diagnostics

The bundled `scripts/method_diagnostics.py` reads a JSON capture and returns a report without making requests or changing the application. Its five modes check adapter-normalized evidence. Capture references, authorization origins, source hashes and production-path populations must come from trusted application instrumentation or reviewed run artifacts; a model's self-report cannot establish those facts. The helper does not run an evaluator, verify signatures, authenticate a user or authorize an external action.

```bash
python3 "$SKILL_ROOT/scripts/method_diagnostics.py" architecture architecture-capture.json
python3 "$SKILL_ROOT/scripts/method_diagnostics.py" review review-capture.json
python3 "$SKILL_ROOT/scripts/method_diagnostics.py" oversight judgment-capture.json
python3 "$SKILL_ROOT/scripts/method_diagnostics.py" handoff handoff-capture.json
python3 "$SKILL_ROOT/scripts/method_diagnostics.py" claude-api request-capture.json
```

All modes write JSON to stdout. Invalid input exits with code 2; a valid diagnostic report can contain `regressed`, `round_limit`, `failed` or `inconclusive`, so callers must inspect its status rather than treating process success as a passing application check. For multi-round live experiments use the existing [evaluation runner](../../eval-improve/references/runner.md); these descriptive reports do not replace its frozen splits, retries, cost accounting or grouped comparisons.

## Choose a migration experiment for each component

Start with the smallest adequate architecture and freeze an end-to-end task set before changing it. Inventory each production call chain, including nested calls and rules that must not fail. Record the prompt, tool, state and permission owner. Preserve the configured model so architecture changes and model changes remain separable.

The `architecture` capture contains a `components` array. Each component has a unique `id`, `role` (`router`, `planner`, `domain`, `verifier`, `data` or `other`), an `evidence` reference, and explicit boolean observations:

- `independent_verification`, `separate_permissions`, `parallel_work` and `context_pressure_observed` describe reasons to retain a separate context.
- `talks_to_user` distinguishes a required direct conversation from a callable specialist.
- `coupling_observed` records production evidence of repeated context dependence; `shares_context_with` lists other declared component IDs.
- `deterministic` identifies a bounded operation that needs a tool rather than its own model loop.

With all observations recorded, the helper proposes `keep`, `as-tool`, `merge` or `fold`. Missing observations produce `investigate`. Retained verification, isolation, parallel or context benefits take precedence over folding. These suggestions are experiments to assess, not automatic edits or proof that the simpler variant is better.

An optional `comparison` checks complete paired task evidence. Its required fields are `dataset_id`, `grader_id`, different `baseline_id`/`candidate_id`, frozen `required_case_ids` and `required_path_ids`. Both `baseline` and `candidate` contain an `evidence` reference, `covered_path_ids` and `cases`. Every case has `case_id`, boolean `success`, nonnegative integer `constraint_violations`, and `cost_usd`/`latency_ms` as nonnegative numbers or explicit unknown values. Use unique IDs for each registered case/repetition; do not duplicate a case to inflate the denominator.

```json
{
  "comparison": {
    "dataset_id": "support-val-v2", "grader_id": "support-rubric-v3",
    "baseline_id": "specialists-v1", "candidate_id": "folded-v1",
    "required_case_ids": ["shipping-1"], "required_path_ids": ["order-shipping"],
    "baseline": {
      "evidence": "baseline-captures.jsonl", "covered_path_ids": ["order-shipping"],
      "cases": [{"case_id": "shipping-1", "success": true, "constraint_violations": 0, "cost_usd": 0.2, "latency_ms": 500}]
    },
    "candidate": {
      "evidence": "candidate-captures.jsonl", "covered_path_ids": ["order-shipping"],
      "cases": [{"case_id": "shipping-1", "success": false, "constraint_violations": 1, "cost_usd": 0.1, "latency_ms": 300}]
    }
  }
}
```

This example is synthetic and reports a regression even though cost and latency fall. Results expose improved and regressed case IDs, increased violations, missing paths and missing cases. An unchanged average cannot conceal tasks that flipped. Unknown fees remain unknown, and missing populations prevent complete cost/latency deltas. `observed` means the declared pairs and paths were covered; it is not a significance test, rollout approval or demonstrated general superiority. Inspect multiple repetitions, independent groups and untouched final tests with Eval Improve before selecting a change.

This workflow adapts the migration method in [When to fold subagents into your main agent loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop), October 22, 2026. The [upstream kit](https://github.com/anthropics/single-agent-loop-kit) is a reference with limited validation and no maintenance promise, not a replacement for AMind's durable tool and workflow journals.

## Bound review and preserve unresolved findings

The `review` capture declares positive integer `max_rounds`, `required_check_ids` and `rounds`. Each round records the exact `patch_sha256`, `changed_paths`, `checked_paths`, `checks` and `findings`. A check has `id`, `status` (`passed`, `failed`, `unknown`), matching `patch_sha256` and `evidence` reference. Checks from another patch are rejected.

Every finding has a stable `key`, `path`, `contract`, boolean `blocking`, `status` (`open`, `resolved`, `dismissed`) and an `evidence` reference. The same key must continue to identify the same path and contract. Repeated reports are counted once. An old finding absent from a later round stays open; resolving or dismissing it requires an explicit evidence-bearing record. Adapters own semantic equivalence: changing a key to disguise the same issue does not make it new evidence.

The helper reports `converged` only after a round with no new findings, no open blocking findings, all required checks passed on that patch, and all changed paths inspected. Otherwise it reports follow-up work or `round_limit`. Reaching the round budget never approves the change. An unresolved issue goes to the owner with the current evidence; do not restart a new ledger to hide the exhausted budget. Nonblocking findings stay visible even when review converges.

Track human review time and waiting time alongside reverts and incidents. Recheck the changed surfaces and affected contracts after a fix, with a broader review when the patch changes scope. This is an adaptation of the bounded, outcome-calibrated review described in [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/), October 15, 2026; a team's observed results do not establish equal results for another product.

## Measure judgment formation separately from approval

The `oversight` capture declares frozen `required_case_ids` and `observations`. Each decision contains `case_id`, `reviewer_id`, `agent_preference`, `final_choice`, `preference_assignment` (`randomized`, `natural`, `unknown`), boolean `balanced_alternatives`, boolean `prior_recorded_before_advice`, optional `prior_choice`, and `evidence`. A pre-advice record requires its actual choice. Missing evidence remains uncovered.

The report separates decisions from distinct reviewers and exposes preference-following counts, pre-advice disagreements, switches toward the agent, randomized assignments and balanced alternatives. It always leaves `judgment_independence` as `not_established`. A high or low following rate is not an error rate, a causal effect or proof of independent judgment. Obtain genuinely pre-advice choices, counterbalance defensible alternatives, preserve the assignment record and analyze repeated decisions within people and shared model contexts appropriately.

The motivating [expert-judgment study](https://www.anthropic.com/research/agents-judgment-calls), October 27, 2026, used one task, model and domain and deliberately strengthened agent preferences. It does not justify a universal effect-size assumption. Preserve ordinary correctness, task completion and cost outcomes alongside judgment-formation probes.

## Audit summary and shared-state handoffs

The `handoff` capture includes trusted `approval` and `dispatch` records, each with `action_sha256`, `resource_version` and `evidence`. `approval.authority_origin` must be `trusted_control_plane`. Bind the action hash to the normalized action, destinations and arguments; bind `resource_version` to the relevant file/resource version observed by the permission check. A changed action or resource requires fresh authorization or reconciliation in the application. Checking a file once cannot make a later asynchronous execution atomic.

Declare `required_handoff_ids` before collecting `handoffs`. Each handoff has `id`, `kind` (`compaction`, `agent_handoff`, `shared_file`, `tool_result`), booleans `monitor_applied` and `claims_authorization`, `authority_origin` (`trusted_control_plane`, `untrusted_content`, `none`, `unknown`), and `evidence`. Shared-file observations additionally carry `expected_sha256` and `observed_sha256`. Preserve provenance through summaries and encode transcript roles structurally; never promote a summary's claim about user intent into authorization.

The helper flags untrusted authorization claims, changed approved actions/resources and changed shared-file hashes. Missing handoffs, monitor coverage or approval/dispatch evidence remain inconclusive. It does not inspect payload semantics or verify signatures. Instrument the actual dispatch path and enforce approval, content framing, permissions and idempotency outside the model.

[Red-Teaming Auto Mode](https://alignment.anthropic.com/2026/red-teaming-auto-mode/), October 22, 2026, motivates these probes. Its results concern September monitor snapshots; it reports that robust prevention of multi-context attacks remains open. These local checks do not certify equivalent monitor robustness or sandbox isolation.

## Audit explicit Claude API removals

The `claude-api` capture contains `provider`, `api_version` and a Messages `request`. The helper checks only `provider:"anthropic"` with `api_version:"2026-10-21"`; other versions/providers return `out_of_scope`. It reports removed sampling parameters, direct document blocks in assistant messages, and nonempty citations on user text blocks, including nested search-result content. It preserves nested assistant tool-result documents and document citation settings. The request is never rewritten.

Use it separately on each Message Batch request. Complete [version migration](migration.md#claude-api-version-2026-10-21) still needs SDK types, compaction, authentication, response field changes and real endpoint verification. A `checked` report certifies only that these selected removal patterns were absent.
