# Long-running and managed agent operations

An agent definition, session, turn, environment, external operation and artifact are different resources. Give each explicit ownership and lifecycle. This reference covers the operational responsibilities behind the upstream managed-agent family: onboarding, core resources, events, tools, memory, multi-agent work, outcomes, schedules, webhooks and self-hosted compute.

## Lifecycle contract

Use a persisted application state machine such as queued → provisioning → running → waiting_for_tool/user → completed/failed/cancelled, with cancellation-requested as a separate fact. Map provider events onto that application model; do not assume provider event names or idle states mean success. Persist IDs, ownership, configuration versions, event cursor, deadlines and artifacts needed to recover.

For OpenAI's current Agents API, create a session with `client.beta.agents.sessions.create(...)`, agent model/instructions, environment and input. Streams emit session/turn events. `agent.session.turn.completed` identifies a completed turn, but tool outcomes still require inspection; `agent.session.idle` alone is not success. Save the session ID, retrieve state/items after disconnect, and follow the documented input/cancellation operations. See the [quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart) and [session guide](https://developers.openai.com/api/docs/guides/agents-api/sessions).

### Minimal creation recipe (documentation example)

```python
# Uses the application's already-configured client and chosen model.
with client.beta.agents.sessions.create(
    agent={"model": chosen_model, "instructions": task_instructions},
    environment={"type": "openai_hosted"},
    input=task_input,
    stream=True,
) as events:
    for event in events:
        persist_event(event.to_dict())  # Durable ID-based ingestion before user-facing updates.
```

Choose `environment.type:"none"` for an appropriate tool-only agent, or configure a supported self-hosted environment when needed. The current raw HTTP API uses `OpenAI-Beta: agents=v1`; SDKs add it. Verify the installed SDK before using this beta namespace. An inference key, an application control-plane key and an environment executor credential have different roles; keep control-plane keys out of agent sandboxes.

## Events, reconnect and webhooks

Store each event once using its provider event ID scoped to its resource/tenant. Treat repeated identical delivery as a replay; a repeated ID with different content is an integrity incident. Do not turn every streamed text delta into a durable completed message. Persist full terminal items and usage after the terminal event.

Open the event subscription before submitting follow-up input when required to avoid missing early events. After disconnect, retrieve saved state/items and pending actions, reconcile your cursor, and resume observation before deciding whether to resubmit. Network failure does not establish that the task failed to start. Close the stream in normal/error/cancellation paths, but distinguish closing observation from cancelling work.

Webhook receivers must authenticate signatures over the **raw body**, enforce timestamp/replay rules using the current SDK, enqueue a deduplicated event durably, and respond promptly. Expensive work belongs in a worker. Verify tenant/resource ownership when retrieving the referenced object. Test duplicate/out-of-order deliveries and callback retries. Never execute an unsigned event or interpret its text as agent instructions. See [webhooks](https://developers.openai.com/api/docs/guides/webhooks) and the selected runtime's session webhook guide.

## Required actions and function tools

A function requested by a managed agent is executed by the application handler; attaching a sandbox does not automatically implement it. On the current Agents API, inspect `session.required_actions` when `agent.session.requires_action` arrives or retrieve the session after reconnect. Validate and authorize each call, durably deduplicate it, execute within a deadline, and return the result associated with the exact turn/call IDs. Reconcile pending calls before retrying. See [function actions](https://developers.openai.com/api/docs/guides/agents-api/tools/functions) for the exact result submission method.

Keep action-request processing separate from progress text. Do not mistake a suggested tool call in assistant prose for an executable request. Read-only tools can often retry; mutating tools need remote idempotency/reconciliation. Cancellation prevents new dispatch but cannot undo an already completed external effect.

## Environments and self-hosted sandboxes

Use one coordinator for the session→compute mapping. Persist provider compute ID, environment ID, startup request and lifecycle state so duplicate webhooks cannot create duplicate machines. Separate environment health from agent progress. In the current Agents API self-hosted lifecycle, an `environment_connection` required action requests connection; connected/disconnected events report state and do not themselves request new compute.

Provision only the filesystem mounts, network endpoints and short-lived credentials required for the task. Keep evaluation answers and control-plane keys outside. Persist files through provider storage or explicit checkpoints; reusing an environment ID does not restore a replacement machine's disk. A mid-turn disconnect may fail a tool even if the turn later completes, so inspect results. The API does not guarantee replay of pending input after a process crash; check its outcome before resubmission. See [sandbox lifecycle](https://developers.openai.com/api/docs/guides/agents-api/environments/lifecycle).

On completion/cancel/failure, save required artifacts, reconcile external actions, revoke ephemeral credentials, close connections and dispose of compute according to retention policy. Session deletion and compute deletion may be separate operations. Record partial cleanup and retry it idempotently. Do not delete user resources merely because an example ends with a cleanup call.

## Memory, multi-agent work and outcomes

Memory is a typed product resource: tenant, source, freshness, permissions, scope and version. Read/write policy must distinguish transient conversation facts from durable instructions. Require evidence for durable updates and handle contradiction, expiry and deletion. Evaluate without exposing test answers through memory generation. Include unchanged rebuild controls for learned memories/indexes.

For multiple agents, define task decomposition, context allowed to each child, budget allocation, output schema, tool permissions, cancellation propagation, result ownership and reconciliation. Avoid shared mutable files without coordination. A parent must validate child artifacts and resolve disagreement; child confidence is not evidence. Only delegate when the host/user authorizes it. Do not map a product's multi-agent capability onto unauthorized creation of chats in the development host.

For a known item population, the [staged workflow journal](workflow-recipes.md) provides executable phase/resume/coverage contracts. For native Responses Multi-agent, [response recipes](response-recipes.md) adds root/child attribution, actual function-call budgets, injection acknowledgement recovery and mode-specific compaction limits. Hosted run events and local stage rows must not be conflated: only a destination adapter can establish their correspondence. A successful final summary cannot erase failed, missing or unverified child work from the population denominator.

Define outcomes independently of agent text: expected file, verified database change, user acceptance, task completion rubric and failure class. Report partial success and unknown effects explicitly. Keep an outcome schema stable across runtime migrations so the app eval remains comparable.

## Scheduled deployments

Treat schedules as separate persistent automation resources with owner, timezone, cadence, task version, budget, concurrency/overlap rule, retry policy, expiry and pause/delete controls. Decide whether a missed run is skipped or caught up; deduplicate the logical schedule occurrence. Avoid overlapping mutating runs. Keep secrets outside scheduled prompts. Test timezones/DST and a failed/retried occurrence with fixtures.

If the selected provider lacks a matching schedule resource, use the application's existing scheduler/queue while preserving these contracts. Do not invent a hosted endpoint. Creating or enabling a schedule requires the user's request for recurring work; a local build does not imply it.

## Offline journal audit

```bash
python3 "$SKILL_ROOT/scripts/lifecycle_audit.py" normalized-events.jsonl
```

Each event has `id`, `task_id`, `tenant_id`, `kind`. Supported kinds include task start/completion/failure/cancel, cancellation request, effect start/success/failure/reconciliation, memory read, child start and webhook receipt. Effect events carry `idempotency_key`; memory reads carry `memory_tenant_id`, optional `expires_at/at`; child starts carry `child_budget`; webhook receipts carry a trusted `signature_verified` fact.

The audit flags conflicting replay, events after terminal states, duplicate/unknown effects, cancellation races, tenant/TTL mismatches, unbounded child work and unverified webhooks. It cannot itself verify signatures or remote outcomes; instrumentation must establish those facts. Use the durable effect ledger in `tool_loop.py` as a reference for local dispatch/reconciliation and implement the product's storage/transaction model explicitly.
