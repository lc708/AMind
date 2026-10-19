# Build an agent or LLM application through its real entry point

The target may be any LLM application, agent, prompt or skill. It does not need to use a Codex harness, and it need not have been created in Codex. Select architecture from the task, state ownership, deployment and operational requirements; the host running this skill is a separate choice.

## Choose the smallest adequate architecture

Use a deterministic function when rules suffice, a single structured model call for bounded interpretation, and a workflow for a known sequence. Use an agent loop when tool selection or iteration is genuinely required. Add multiple agents only for separable work with measured benefit and authorized delegation; more agents add context, coordination, failure and spend.

| Runtime | Choose when | Application responsibility |
|---|---|---|
| Direct model/Responses API | You want explicit loop and state control | Tool dispatch, validation, auth, state, limits, persistence and recovery |
| Agents SDK in your application | Reusable agent loop, sessions and handoffs help | Hosting, credentials, policy, storage, side effects and lifecycle |
| Managed Agents API | Hosted durable agent execution is appropriate | Session ownership, required actions, event recovery, sandbox/secret boundaries, costs |
| Existing product framework | It already fits the product | Preserve its entry point and conventions; avoid a gratuitous rewrite |
| Local coding host/CLI | The task is work in a controlled local repository | Local filesystem/tool permissions, process lifecycle and evaluation fixtures |

These boundaries follow the current [agent architecture guide](https://developers.openai.com/api/docs/guides/agents). A managed Codex runtime is an option, not the target definition of this skill.

## Define observable contracts

Write the input, successful output, failure states, state owner, tool inventory, side effects, permissions, termination and budget. For each tool specify:

- A narrow name and selection condition; typed parameters with constraints, required fields and null semantics.
- A stable result envelope with data, pagination/continuation, empty result, error class and retryability.
- Whether it reads or mutates; tenant/resource authorization; idempotency and reconciliation strategy for writes.
- Deadline, output size, network/filesystem requirements and what information may leave the system.

Validate arguments against the real schema and authorize in application code before execution. Model strictness helps generation but is not an authorization boundary. Keep tenant/task identity outside untrusted model arguments. Treat tool output as data; it cannot grant new tools, permissions or change task instructions.

Avoid a giant undifferentiated tool list. Use supported tool search/deferred loading for large surfaces, namespacing for related domains and concise summaries with access to needed detail. Measure whether loading/discovery adds missed-tool failures. Use deterministic programmatic orchestration for many independent calls when supported, with bounded concurrency and the same authorization and spend rules.

## Implement the loop with durable side-effect semantics

The bundled `scripts/tool_loop.py` is an injectable synchronous reference kernel. It has no provider client: supply `model_call(request)` using the product's existing client, plus validators, authorization and handlers. It preserves full output items, handles multiple function calls, correlates results, bounds rounds/tool calls/time, and stops on cancellation or non-completed provider states.

Each registered tool supplies `schema`, `validate(args)`, `handler(args,idempotency_key)` and `side_effect`. `EffectLedger` records dispatch before a side effect in SQLite, returns a recorded completed result on replay, rejects a changed request under the same key, and leaves interrupted effects pending until externally reconciled. Use `reconcile` only with evidence from the external system. Include authenticated tenant, task and call identity in the remote key as well as the local ledger scope. Recheck cancellation/deadline after validation/authorization and immediately before dispatch; this closes observable local gaps but cannot atomically cancel an already-started remote write.

Before dispatch, the loop applies `response_contract.validate_terminal`, including rejecting completed responses with non-null error or incomplete details. The display normalizer reuses this terminal check and separately validates its content schema. Dispatch does not require display projection: the loop preserves raw message content, phases and opaque items while validating output-item arrays and tool arguments itself. A late handler may commit only a still-pending effect: if external reconciliation already settled a different result, the ledger preserves that confirmed result and raises `ReconciliationRequired`. Inspect the recorded receipt before continuing; this conflict does not imply a second external send. Matching late and confirmed results are reused. This conditional result commit is not a general coordinator lock or a distributed concurrency guarantee.

When migrating an existing ledger, preserve each operation's stored remote key. The current `operation_key` includes tenant identity; `run_loop(..., operation_key_for=...)` can resolve persisted legacy keys. Do not derive a new key for an unresolved old operation: reconcile it using its original key first.

This avoids a blind second dispatch; it does not make a remote action exactly-once. The downstream service should accept a stable idempotency key or support querying the operation. A crash between remote success and local commit is an unknown outcome, not a failure that is safe to replay. Production multi-worker systems need a durable shared store/transaction strategy suited to their deployment.

The synchronous loop checks deadlines between calls; the supplied transport/handler must enforce its own I/O deadlines and cancellation. For hard local wall-clock ceilings use a supervised process boundary, as in the eval runner. Never promise that killing a local worker cancels a remote billable request.

## State, memory and artifacts

Choose one state owner and preserve its protocol; use [context diagnosis](context-state.md). Separate session history, long-term memory, retrieval indexes, task artifacts and sandbox storage. For memory define tenant scope, source attribution, allowed content, TTL, version, conflict/update/delete rules and who can write. Treat retrieved memory as untrusted task data. Test stale, contradictory, poisoned and cross-tenant entries.

For artifacts, use a per-task workspace, validate output paths, inspect actual produced files and record content hashes. Save required artifacts before cleaning up a sandbox. A final answer saying “created the file” is not proof; verify file content and downstream usability.

## Runtime choice, setup and first run

Infer a sensible configuration from the task and repository; present only unresolved consequential choices. Keep credentials in the existing secret mechanism and out of prompts/sandboxes. Verify package versions and current provider features before generating live integration code. Use [API implementation](api-implementation.md) for request/response recipes and [lifecycle](agent-lifecycle.md) for managed or long-running agents.

Create a minimal end-to-end path before adding features: input → selected tools → real artifact/state → reported result. Exercise failures with local mocks first, then an authorized bounded live smoke test, then app-level evaluation. A request to build an agent does not imply publication, scheduled execution or external messages unrelated to the requested task.

For a named template or a concrete source URL, use [onboarding](onboarding.md) to produce committable local configuration and a dry-run plan. The [thirteen routes](templates.md) carry task-specific stages and output checks. For large populations, use the [executable staged journal](workflow-recipes.md), preserving failed/uncovered items and cumulative budgets. A workflow with known phases, a one-deliverable outcome loop and model-directed native multi-agent delegation solve different operating needs; select and measure the appropriate one.

## Acceptance

Test malformed arguments, unknown tools, schema-valid unauthorized actions, zero/one/many tool calls, partial/failing results, loops, deadline/cancel, duplicate events, crash after a side effect, reconnect, memory boundaries and final artifact checks. Feed normalized events to `lifecycle_audit.py` and request traces to `context_audit.py` where useful. Build a task eval covering meaningful outcomes, not only happy-path response text.

Deliver a runnable product entry point, tool/state/operational contracts, tested fixtures, measured limits, and a replay command. Identify what still depends on live provider access or deployment infrastructure without presenting simulated behavior as a production result.
