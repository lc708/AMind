# Model/API migration and SDK upgrades

Migration must preserve the product's observable contract while changing explicit implementation variables. It is not global model-name replacement. Preserve the user's named destination and migration scope; do not silently migrate untouched providers or branches.

## Model or API migration

### Inventory and classify

Trace every call site, wrapper, model router, request builder, streaming consumer, parser, tool loop, continuation path, retry/fallback and background/batch path. Include lockfiles, deployment/runtime configuration, tests, examples and documentation. Use the prompt inventory to locate candidates, then inspect the effective request. Record file/line and classify each as **must change**, **behavioral re-evaluation**, **compatible as-is**, **out of scope**, or **unresolved**.

Make a contract table before editing:

| Surface | Check | Concrete migration test |
|---|---|---|
| Model identity / availability | Requested vs actual served identity; region/account/snapshot support | Reject/record unexpected fallback; preserve explicit user choice |
| Reasoning/effort | Supported fields, defaults, effort meanings, output budgets | Omitted and explicit settings; task cost and quality |
| Sampling | Destination support and interactions | Unsupported combination rejected before release |
| Output/schema | Text extraction, refusal, incomplete status, structured output shape | Valid/invalid schema, refusal and token-limit paths |
| Tools | Schema, strictness, names, call IDs, parallel calls, result envelopes | Zero/one/many calls, malformed args, authorization, duplicate side effects |
| State | Client replay vs server IDs vs durable conversation | Continuation after tool use, compaction and reconnect |
| Streaming | Event types, delta accumulation, terminal status and usage | Partial stream, disconnect, keepalive timeout, final event |
| Files/media | Purpose, MIME/size, ownership/lifetime and content representation | Wrong type, expired/unauthorized file, multimodal parsing |
| Background/batch | Submission, poll/events, cancellation and output matching | Out-of-order results, partial completion, expired job |
| SDK objects | Type unions, unknown fields, helper availability, sync/async APIs | Serialization round trip with full output items |
| Accounting/errors | Cached/reasoning subsets, retries, request IDs, rate limits | Failed-but-billed calls and nonretryable 4xx |

Check current official model and API documentation for **breaking removals** and **silent default changes**. New tokenizers, effort defaults, reasoning display, model aliases and billing tiers can change behavior without a 400 error. Do not copy a predecessor's settings because they have the same name. Avoid claiming an equal setting means equal compute.

### Apply the smallest destination-native change

Keep application changes and evaluator changes separate. When migrating API surfaces, translate the complete protocol: messages → input items, output extraction, tool result envelopes, streaming events, continuation ownership, and errors. A renamed method with the old response parser is an incomplete migration.

For Responses integrations, use [API recipes](response-recipes.md) and preserve output item types, tool call IDs, `phase` when supplied, and opaque continuation items. Do not transplant another provider's thinking blocks/signatures or invent field equivalence. If the destination has no equivalent feature, state the missing capability and implement a justified product-level alternative; do not erase the requirement silently.

When replacing prompt output choreography with structured output, update schema, parser, validation, refusal handling and retries together. When a forced tool mode is unsupported, explicit task instructions plus postcondition checks may be an alternative, but first verify the destination contract and evaluate the altered behavior.

Explain every meaningful change with source contract, user-visible effect and test. Preserve old behavior behind a narrow adapter or rollback path during validation. Avoid blanket exception handling that hides protocol breaks as empty text.

### Validate in increasing cost order

1. Compile/type-check/lint appropriate to affected code and run serialization/contract fixtures.
2. Replay old and new adapters on recorded request/response fixtures, including failure paths and full output-item round trips. Fixtures prove parser compatibility, not target model behavior.
3. Run the actual entry point in a bounded live smoke test when authorized, checking served identity and tool/state wiring.
4. Compare baseline and destination on the same calibrated dataset/grader, independent groups and repetitions. Quality, hard failures, latency, total cost and failure rate all matter.
5. Freeze the selected configuration, run the final check and prepare a reversible rollout/canary. Deployment is a separate authorized action.

## SDK or runtime upgrade

### Claude API version 2026-10-21

Apply these removals only to an explicitly selected Claude API version, not to OpenAI/provider-neutral requests. The [official migration guide](https://platform.claude.com/docs/en/api/migration-2026-10-21), checked October 30, 2026, moves Messages, token counting and each Message Batch request from `2023-06-01` to `2026-10-21`. Sending `temperature`, `top_p` or `top_k` now errors even at default values. Direct `document` blocks in assistant messages and nonempty `citations` on user text blocks also error; nested assistant tool-result documents and document/search-result citation settings remain distinct. The local [request diagnostic](method-diagnostics.md#audit-explicit-claude-api-removals) reports these selected patterns without rewriting requests.

Upgrade the API header and affected SDK call sites together. Inspect role-specific message types, removed tool-runner client compaction, renamed Admin/Analytics response fields, API-key `scope` and authentication for the actual language and deployment. Older Bedrock models may require the earlier API/SDK route; a date alone does not make every old integration invalid. Keep authentication and SDK-type changes separate from model-quality evaluation, preserve the user's model and test effective payloads plus continuation/stream behavior before release.

### MCP TypeScript SDK versions

Inspect the project's installed major version and imports before generating server code. The [October 28 mcp-builder update](https://github.com/anthropics/skills/commit/ca45fc496a3436251f191354091d557da31c15b5) adds an SDK v2 server guide and version selection; it changes a different skill from the pinned claude-api source map. New v2 projects use their documented packages and examples. Existing `@modelcontextprotocol/sdk` v1 projects can continue maintenance unless migration is requested; do not mix v1/v2 imports or silently repin them. Use the [official SDK](https://github.com/modelcontextprotocol/typescript-sdk) for the selected major's transport, auth, tools, resources and prompts, and exercise a built server over its actual transport. File coverage in the 96-file claude-api map does not claim MCP v2 implementation coverage.

### Upgrade an existing SDK or runtime

Find installed versions from lockfiles/package metadata and exact import paths. Use official release notes, migration guides and source signatures for the installed→target range. Do not assume the current online quickstart matches a pinned old SDK.

Create a call-site ledger including sync/async clients, resource methods, streaming helpers, typed parameter/result unions, error classes, pagination, upload wrappers, custom HTTP transports, retries/timeouts, base URLs and close/disposal semantics. Pay special attention to removed helpers and default retry behavior; nested SDK/application retries multiply calls.

Update dependency constraints and lockfile using the project's package manager. Make targeted call-site changes and remove compatibility shims only after tests cover their original purpose. In typed languages, compile all affected targets rather than editing until one example looks plausible. In dynamic languages, exercise named parameters and response serialization with fixtures.

The language contract in [language adapters](language-adapters.md) gives concrete integration points for Python, TypeScript, Java, Go, Ruby, C#/.NET, PHP and HTTP/CLI. Use the current official SDK when available; PHP community clients require their own verified documentation. Do not invent uniform SDK method names across languages.

## Acceptance and handoff

Deliver the ledger of changed/unchanged/unresolved surfaces, actual diff and lockfile, validation results, measured behavioral tradeoffs, rollout/rollback command and remaining incompatibilities. A build passing is structural success. A live smoke passing confirms connectivity. Only a suitable comparative evaluation supports a quality claim.
