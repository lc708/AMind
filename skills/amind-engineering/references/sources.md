# Provenance and current documentation

Initial adaptation: **2026-09-30**; Engineering **0.3.0** refresh: **2026-10-18**. The current workflow source is Anthropic's [`claude-api` skill](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/claude-api), pinned at `dbd4588f9e1033efb41dad4bef2f7947c8993d44` (2026-10-09T18:45:49Z). Its `SKILL.md` SHA-256 is `40537cca17c4aa86e4ce83ced39efcbfb1204905e3cf4c4ff98f2eab011e4b7f`. The Apache-2.0 license is retained. This is an AMind adaptation, not an upstream distribution or endorsement.

The original pin `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` (2026-09-29) and `SKILL.md` hash `9aac10d9ffb8778c5b7c0b9ec612b3915e83065feb92763c8231469e9fbc29c9` remain in the [81-file historical inventory](upstream-capabilities-2026-09-29.json). The [current 96-file map](capability-map.md) adds three upstream commits: October 5 source/template onboarding; October 9 model/state fixes; October 9 dynamic workflows, quickstarts and networking corrections. September acceptance results retain their original versions and scores.

## October capability refresh

Version 0.3.0 implements root/child-safe response and SSE projections, hosted/unknown item preservation, explicit Multi-agent incompatibilities and an offline injection acknowledgement tracker. It adds a real SQLite staged workflow journal with recovery/coverage/budgets, thirteen task templates and a local configuration planner/writer, plus native cache-diagnostic interpretation and provider-neutral probe-coverage checks. These are executable local adapters/contracts, not a copied hosted Claude platform. Native API access, model quality and independent behavior superiority require separate evidence.

## Capability-core upgrade

The September 0.2.0/0.2.1 core added prompt/state/lifecycle diagnostics, an injectable tool loop with a durable effect ledger, response/stream/batch contract helpers and native API/language recipes. Eval Improve's September 0.3.0 core added the complete application/grader runner and experiment evidence. Their 81-file pin and acceptance limitations remain historical facts; an inventory is not behavioral-equivalence proof.

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
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): `codex exec`, JSONL events, ephemeral runs and output files. September CLI check was `0.159.0`; on 2026-10-18 local `0.163.0 --help` still exposes the collector's flags. This is a help/interface check, not a live JSONL/cancellation compatibility run.
- [Agent architecture guide](https://developers.openai.com/api/docs/guides/agents): Responses, Agents SDK and Agents API boundaries.
- [Official SDKs](https://developers.openai.com/api/docs/libraries): language-specific clients and authoritative repositories.
- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) and [compaction](https://developers.openai.com/api/docs/guides/compaction): history and continuation contracts.
- [Cost optimization](https://developers.openai.com/api/docs/guides/cost-optimization) and [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): current accounting and supported mechanisms.
- [Agent quality/cost optimization cookbook](https://developers.openai.com/cookbook/examples/agent_optimization/optimizing_agents_for_cost_and_quality): repeatable measurement and bounded optimization.

The [prompt optimizer documentation](https://developers.openai.com/api/docs/guides/prompt-optimizer), inspected on 2026-09-30, announces dataset-backed Evals/prompt optimizer becoming read-only on 2026-10-31 and shutting down on 2026-11-30. This suite uses local evaluation artifacts and does not introduce a dependency on that retiring service. Recheck lifecycle notices before suggesting any hosted evaluation service.

Future updates should pin source revisions, inspect actual destination contracts, preserve local improvements and licenses, and report code checks separately from live behavioral evaluation. Engineering updates do not advance the original `amind` evidence-corpus date.

Additional native implementation sources checked 2026-09-30: [function calling](https://developers.openai.com/api/docs/guides/function-calling), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [streaming](https://developers.openai.com/api/docs/guides/streaming-responses), [batch](https://developers.openai.com/api/docs/guides/batch), [Agents API quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart), [sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions), [function actions](https://developers.openai.com/api/docs/guides/agents-api/tools/functions), [sandbox lifecycle](https://developers.openai.com/api/docs/guides/agents-api/environments/lifecycle), and [webhooks](https://developers.openai.com/api/docs/guides/webhooks). Examples are documentation-grounded; live provider compatibility and language runtime checks must be recorded separately.

Current official sources read 2026-10-18 include [Responses Multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent), [cache diagnostics](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics), [conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [compaction](https://developers.openai.com/api/docs/guides/compaction), [Agents sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions), [Decisions](https://developers.openai.com/api/docs/guides/decisions), the [API changelog](https://developers.openai.com/api/docs/changelog) and [deprecations](https://developers.openai.com/api/docs/deprecations). Decisions is a distinct optional typed-answer endpoint with endpoint-specific pricing; it is not an automatic replacement for a calibrated grader. Ultrafast is a service-tier experiment, not a reason to change the user's model silently.

The current retirement page retains Evals read-only October 31/shutdown November 30, 2026, and also retires reusable prompt objects/`v1/prompts` and Agent Builder on November 30. Do not start new dependencies on them; local prompts/runner artifacts remain supported by this suite. October 1/14 model deprecation notices are migration inputs, not evidence that those models have already shut down. Inspect `shutdown_date` where supplied by the Models API, exact snapshot/account access and current official notices before changing a configured model.
