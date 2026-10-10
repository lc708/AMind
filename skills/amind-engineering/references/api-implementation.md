# Implement the model and platform boundary

Choose the product's existing language, entry point and runtime. This reference is the route into concrete API knowledge; the capability core remains task design, tool/state contracts, operational recovery and measured improvement.

| Work | Read |
|---|---|
| Text, structured output, streaming and function loops | [Response recipes](response-recipes.md) |
| Python, TypeScript, Java, Go, Ruby, .NET, PHP, HTTP/CLI | [Language adapters](language-adapters.md) |
| Files/media, retrieval, MCP, batch, caching, usage and errors | [Platform operations](platform-operations.md) |
| Hosted sessions, environments, events, webhooks, memory and schedules | [Agent lifecycle](agent-lifecycle.md) |
| Existing-model/API/SDK changes | [Migration](migration.md) |
| Conversation replay and compaction problems | [Context state](context-state.md) |

## Implementation contract

Before writing live client code, inspect installed SDK/version, existing credentials mechanism, region/base URL, named model and supported capabilities. Preserve the user's model. Verify the current primary documentation for model-dependent fields, beta features and platform availability. Do not hard-code a “latest” model or assume direct API, cloud reseller and local CLI surfaces are interchangeable.

Keep a narrow adapter around provider calls. Input includes explicit instructions, typed user/task input, required tools, state ownership and budgets. Output preserves full response items, actual served identity, status, usage, error/request IDs and artifacts before producing the product's simpler result. Centralize error classification, deadline and retry semantics; avoid nested unbounded retries.

Separate concerns that are often conflated:

- Structured output constrains shape; business validation checks meaning; authorization checks whether an action is allowed.
- A function schema is a proposed interface; application code executes it and enforces permissions.
- Streaming emits partial progress; a valid terminal state and outcome check establish completion.
- A response/session ID points to provider-owned state; it is not a tenant authorization check.
- Token estimation helps budget; actual usage and the invoice establish billed cost.
- A sandbox constrains execution only to the extent its actual mounts, credentials and network policy enforce it.

The bundled `tool_loop.py` takes an injected model-call function and application handlers; it does not choose a provider or create a credential. Documentation examples are implementation recipes, not evidence that live API calls were executed. Build and test fixtures first, then run authorized bounded live checks.

## A practical vertical slice

Start with one user task, one actual entry point and one concrete result. Implement a request/response adapter; preserve status/usage; validate output; add only the required tools; store correct state; inspect produced artifacts. Exercise success, refusal/incomplete output, transport failure and a tool failure. Only then expand into retrieval, memory, batches or multiple agents.

Generate a diagnostic record per attempt containing correlation ID, model/config version, input/source hashes, tool calls/results, state IDs, status, usage, cost basis and latency. Redact secrets and unrelated private data. Feed this to the app's evaluator without bypassing the product's orchestration.

Acceptance is evidence-based: compilation and fixture tests for protocol compatibility; a live smoke for access and integration; a calibrated evaluation for task quality; an operational test for recovery/side effects. Do not collapse those into “works.”
