# Provenance and current documentation

Adaptation date: **2026-09-30**. The workflow source is Anthropic's [`claude-api` skill](https://github.com/anthropics/skills/tree/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/claude-api), pinned at `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` (2026-09-29). The source skill's SHA-256 is `9aac10d9ffb8778c5b7c0b9ec612b3915e83065feb92763c8231469e9fbc29c9`. Its Apache-2.0 license is retained. This is an AMind adaptation, not an upstream distribution or an official endorsement.

## Capability-core upgrade

Version 0.2.0 adds executable prompt/state/lifecycle diagnostics, an injectable tool loop with a durable effect ledger, response/stream/batch contract helpers, deeper migration and operations workflows, and native API/language recipes. The companion Eval Improve 0.3.0 adds a complete application/grader runner and strict experiment evidence. [The complete source map](capability-map.md) and `upstream-capabilities.json` index the pinned 81-file tree and its section locators. An inventory is not a behavioral-equivalence proof.

## Functional migration

| Source entry | AMind implementation | Scope |
|---|---|---|
| `build-eval` | `eval-improve build` | Cases, grader calibration, actual app adapter, coverage and reporting |
| `hillclimb` | `eval-improve improve` | Validation-driven selection, complete paired comparisons, final test |
| `prompt-audit` | `amind-engineering prompt-audit` | Provenance-aware prompt/tool/skill audit and proposed diff |
| `cost-optimize` | `amind-engineering cost-optimize` | OpenAI/Codex accounting, context/cache/loop/output/model tradeoffs |
| `migrate` | `amind-engineering migrate` | Destination-specific model/API contracts, prompts and regression checks |
| `upgrade` | `amind-engineering upgrade` | Actual SDK/CLI release history and language-specific upgrade checks |
| `preserved-thinking-migration` | `amind-engineering context-migrate` | Replaces the workflow goal with OpenAI/Codex state/compaction contracts; no protocol equivalence |
| `managed-agents-onboard` | `amind-engineering agent-build` | Replaces the workflow goal with local Codex, Responses, Agents SDK or Agents API implementation |

Shared implementation guidance covers streaming, structured output, tools, MCP, files, caching, budgets and error handling. Claude-specific model tables, API fields, beta headers, SDK examples, managed-service controls and forced model defaults are deliberately replaced with current destination documentation. The eight workflow intentions are covered; this is not a claim of identical provider features or model performance.

Workflow structure is adapted from the upstream `SKILL.md`, `shared/prompt-audit.md`, `shared/cost-optimization.md`, `shared/model-migration.md`, `shared/preserved-thinking-migration.md`, `python/claude-api/sdk-upgrade.md` and evaluation references. The locally rewritten files make these material changes: capability-core methods and executable checks; destination-specific contracts; inference of already-authorized scope; explicit run limits; accounting separation; validation/final-test separation; and disclosure of unmeasured quality.

## Official destination sources

Resolve API details against current pages before implementation. These sources were inspected for the initial migration; their content can change.

- [Codex skills](https://learn.chatgpt.com/docs/build-skills): skill packaging and invocation.
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): `codex exec`, JSONL events, ephemeral runs and output files. Local CLI checked at version `0.159.0`; the collector depends on its documented flags/events.
- [Agent architecture guide](https://developers.openai.com/api/docs/guides/agents): Responses, Agents SDK and Agents API boundaries.
- [Official SDKs](https://developers.openai.com/api/docs/libraries): language-specific clients and authoritative repositories.
- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) and [compaction](https://developers.openai.com/api/docs/guides/compaction): history and continuation contracts.
- [Cost optimization](https://developers.openai.com/api/docs/guides/cost-optimization) and [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): current accounting and supported mechanisms.
- [Agent quality/cost optimization cookbook](https://developers.openai.com/cookbook/examples/agent_optimization/optimizing_agents_for_cost_and_quality): repeatable measurement and bounded optimization.

The [prompt optimizer documentation](https://developers.openai.com/api/docs/guides/prompt-optimizer), inspected on 2026-09-30, announces dataset-backed Evals/prompt optimizer becoming read-only on 2026-10-31 and shutting down on 2026-11-30. This suite uses local evaluation artifacts and does not introduce a dependency on that retiring service. Recheck lifecycle notices before suggesting any hosted evaluation service.

Future updates should pin source revisions, inspect actual destination contracts, preserve local improvements and licenses, and report code checks separately from live behavioral evaluation. Engineering updates do not advance the original `amind` evidence-corpus date.

Additional native implementation sources checked 2026-09-30: [function calling](https://developers.openai.com/api/docs/guides/function-calling), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [streaming](https://developers.openai.com/api/docs/guides/streaming-responses), [batch](https://developers.openai.com/api/docs/guides/batch), [Agents API quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart), [sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions), [function actions](https://developers.openai.com/api/docs/guides/agents-api/tools/functions), [sandbox lifecycle](https://developers.openai.com/api/docs/guides/agents-api/environments/lifecycle), and [webhooks](https://developers.openai.com/api/docs/guides/webhooks). Examples are documentation-grounded; live provider compatibility and language runtime checks must be recorded separately.
