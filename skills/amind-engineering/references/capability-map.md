# Pinned source → capability map

Source: Anthropic `claude-api` at `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` (2026-09-29T02:20:03Z). All 81 distributed files are indexed below; the machine-readable map retains file hashes and Markdown section locators. This is a coverage/review map, not proof that a file count or every native service is equivalent.

## Core capability and evidence

| Capability | AMind resource / evidence |
|---|---|
| Eval construction, calibration and audit | Companion `eval-improve`: build-eval/eval-audit; deterministic and command graders; human/judge calibration, artifact and leakage checks |
| Eval execution | Companion runner: bounded processes/concurrency/deadlines, graded outputs, retries and all-attempt cost, normalized IDs, target/control identities, resume/reconciliation |
| Hillclimb and cost search | Companion hillclimb/cost-search: independent-group pairing, registered guardrails, mechanism and unchanged-build controls, joint confirmation and frozen final selection |
| Reporting | All-metric/coverage/cost/error/trace report plus unchanged attributed lite reporter; no automatic winner |
| Prompt work | Provenance-aware audit and executable location inventory; hypotheses require behavior checks |
| Model/API/SDK migration | Contract ledger, native recipes, eight language surfaces, response/stream/batch normalizers with fixtures |
| State migration/diagnosis | Hash/pointer diff, owner/phase/call/compaction checks; provider-native isolated ablation procedure |
| Agents and operations | Injectable tool loop, durable side-effect ledger, lifecycle audit, hosted/native operational recipes and memory/schedule/recovery contracts |

Local executable checks live in repository `scripts/test_amind_capability_kernel.py` and `scripts/test_amind_app_skills.py`. They use synthetic processes/payloads and do not establish live API compatibility, eight-language compilation, model task quality or autonomous skill behavior. Read the dated repository verification report for executed evidence. Native model/service availability remains tied to current provider contracts.

## Complete upstream file index

| Upstream file | Retained/replaced capability | AMind references |
|---|---|---|
| `LICENSE.txt` | source | [sources.md](sources.md), [LICENSE.txt](../LICENSE.txt), [NOTICE.txt](../NOTICE.txt) |
| `SKILL.md` | entry | [SKILL.md](../SKILL.md), [api-implementation.md](api-implementation.md), [sources.md](sources.md) |
| `csharp/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `csharp/claude-api/batches.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `csharp/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `csharp/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `csharp/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `curl/examples.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `curl/managed-agents.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `go/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `go/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `go/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `go/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `go/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `java/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `java/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `java/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `java/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `java/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `php/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `php/claude-api/batches.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `php/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `php/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `php/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `php/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `python/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `python/claude-api/batches.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `python/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `python/claude-api/sdk-upgrade.md` | migration | [migration.md](migration.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [response_contract.py](../scripts/response_contract.py) |
| `python/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `python/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `python/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `ruby/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `ruby/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `ruby/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `ruby/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/admin-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/agent-design.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/anthropic-cli.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/claude-platform-on-aws.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/cost-optimization.md` | cost | [cost-optimization.md](cost-optimization.md), [platform-operations.md](platform-operations.md) |
| `shared/error-codes.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/evals/build-eval.md` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/cost-hillclimb.md` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/eval-audit.md` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/eval-hillclimb.md` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/report/SCHEMA.md` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/report/build-report-lite.mjs` | eval | [capability-map.md](capability-map.md) |
| `shared/evals/report/runner-scaffold.mjs` | eval | [capability-map.md](capability-map.md) |
| `shared/live-sources.md` | source | [sources.md](sources.md), [LICENSE.txt](../LICENSE.txt), [NOTICE.txt](../NOTICE.txt) |
| `shared/managed-agents-api-reference.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-client-patterns.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-core.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-environments.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-events.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-memory.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-multiagent.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-onboarding.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-outcomes.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-overview.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-scheduled-deployments.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-self-hosted-sandboxes.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-tools.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/managed-agents-webhooks.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |
| `shared/model-migration.md` | migration | [migration.md](migration.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/models.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/platform-availability.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/preserved-thinking-migration.md` | context | [context-state.md](context-state.md), [context_audit.py](../scripts/context_audit.py) |
| `shared/preserved-thinking-migration/causes.md` | context | [context-state.md](context-state.md), [context_audit.py](../scripts/context_audit.py) |
| `shared/preserved-thinking-migration/drop_block_probe.py` | context | [context-state.md](context-state.md), [context_audit.py](../scripts/context_audit.py) |
| `shared/preserved-thinking-migration/prefix_diff.py` | context | [context-state.md](context-state.md), [context_audit.py](../scripts/context_audit.py) |
| `shared/prompt-audit.md` | prompt | [prompt-audit.md](prompt-audit.md), [prompt_inventory.py](../scripts/prompt_inventory.py) |
| `shared/prompt-caching.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/token-counting.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `shared/tool-use-concepts.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/claude-api/README.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/claude-api/batches.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/claude-api/files-api.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/claude-api/streaming.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/claude-api/tool-use.md` | api | [api-implementation.md](api-implementation.md), [response-recipes.md](response-recipes.md), [language-adapters.md](language-adapters.md), [platform-operations.md](platform-operations.md), [response_contract.py](../scripts/response_contract.py) |
| `typescript/managed-agents/README.md` | agent | [agent-build.md](agent-build.md), [agent-lifecycle.md](agent-lifecycle.md), [tool_loop.py](../scripts/tool_loop.py), [lifecycle_audit.py](../scripts/lifecycle_audit.py) |

## Review status vocabulary

“Implemented with offline checks” means the listed helper has deterministic fixtures for its contract; it does not mean every source paragraph has an independent behavioral test. “Live recipes” means current official documentation informed the examples but no live provider run is claimed. “Companion” requires `eval-improve`, installed with the series installer.

For an update, diff the pinned inventory and section locators, review changed semantics, update the affected native contract and failure fixture, then rerun relevant checks. Do not mark a newly added upstream file as covered merely because an old reference has a matching title. The JSON includes a scope note to keep provider-specific replacements separate from reusable algorithmic capabilities.
