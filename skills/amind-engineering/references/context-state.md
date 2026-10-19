# Diagnose and migrate conversation state

State failures often resemble model regression: lost instructions, duplicate history, orphaned tool results, opaque continuation items stripped by serializers, commentary treated as a final answer, or compacted context replayed incorrectly. Diagnose the actual serialized requests and responses before rewriting prompts.

## Choose one owner

| Owner | What the application sends | What it preserves |
|---|---|---|
| Client-managed input array | Required history plus new items | Full supported output item dictionaries, call/result association, phase and opaque items |
| Response chaining | `previous_response_id` plus new input | Correct parent ID, current request instructions/settings and retention expectations |
| Durable conversation/session | New input to the identified resource | Resource ownership, lifecycle, event/item cursors and authorization |

Do not unintentionally combine full replay with server history, mix conversation and response IDs, or treat an SDK session, hosted agent session and sandbox ID as interchangeable. Follow the selected API's current contract. Check whether instructions/settings persist or must be sent each turn; test changes explicitly instead of relying on assumptions.

The official [conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state) calls out preserving assistant `phase`. The [compaction guide](https://developers.openai.com/api/docs/guides/compaction) distinguishes client-array continuation from response-ID chaining and treats compaction items as opaque.

## Capture and normalize

Capture request/response payloads at the network/SDK serialization boundary with secrets removed. Preserve item order, IDs, roles, item type, tool arguments/results, phase, status and opaque bytes in restricted local evidence. Do not “clean up” the trace before diagnosis. Record wrapper/SDK/model versions and the earliest failing turn.

Normalize JSONL turns for the bundled tool:

```json
{"state_owner":"client","request":{"input":[{"role":"user","content":"..."}]},"response":{"id":"r1","status":"completed","output":[{"type":"message","role":"assistant","phase":"commentary","content":"..."}]}}
```

```bash
python3 "$SKILL_ROOT/scripts/context_audit.py" --trace normalized-turns.jsonl
python3 "$SKILL_ROOT/scripts/context_audit.py" --expected expected-request.json --trace actual-request.json
```

The audit reports JSON pointers and hashes instead of raw prompt contents. It detects replay drift, mixed owners, unknown chain references, duplicate server history, call/result problems, malformed function arguments, non-success statuses and changed compaction items. It is a normalized diagnostic, not a complete provider protocol validator.

For response-ID chaining, an assistant item that matches prior output except for a lost or changed `phase` produces `possible_phase_drift_replay`. This is a warning to inspect trusted event provenance, not proof of duplicate identity or permission to delete input. Fresh user messages with the same text are not treated as assistant replays.

For a legitimate history edit, record `intentional_changes:{"/1/content":"user-requested correction"}` in the trusted diagnostic input; this annotates the difference, not proof that the edit is safe. For a deliberate compaction transition set `compaction_boundary:true` and the saved item's `expected_compaction_hash`. For a trace starting mid-chain, declare known `external_response_ids`. Do not suppress unexplained findings as intentional changes.

## Root-cause map

| Symptom | Inspect first | Fix and regression |
|---|---|---|
| Commentary appears as final | Assistant `phase` lost or rewritten | Preserve supplied phase through storage/replay; multi-tool continuation case |
| Orphan tool output / API 400 | Wrong `call_id`, omitted call, reordered items, mixed owner | Correct envelope and ordering; multiple pending calls test |
| Context doubles each turn | Full history sent with server-owned state | Choose one owner; measure input growth over several turns |
| Earlier instruction vanishes | Wrapper omits current instructions, pruning or wrong parent | Trace effective request and current contract; explicit update case |
| Failure only after compaction | Opaque item omitted/mutated or wrong retained prefix | Replay actual compact output as specified; post-boundary factual/action test |
| Regression after model switch | Unsupported state from another model/resource | Check provider compatibility; start a valid destination history when necessary |
| Good text but missing tool outcome | Failed/cancelled/incomplete state treated as success | Inspect terminal status and external effect; do not infer success from prose |
| Cache hit collapse | Prefix order, schema serialization or volatile metadata changed | Compare exact prefix bytes; warm/cold counter and quality checks |

## Compaction and ablation procedure

For client-managed histories, use destination-native compact output exactly as returned, append new input, and follow documented pruning rules. For `previous_response_id` chaining, send new input and follow the server-owned state model; do not manually prune unseen server history. Never parse, rewrite, manufacture or transplant encrypted reasoning/compaction content.

To isolate a cause, reproduce on a disposable fixture, freeze all other settings, and change one suspected transformation: serializer, item omission, phase retention, tool-result envelope, or compaction boundary. Compare request diffs, API acceptance, actual task behavior, cost and latency. A request becoming accepted does not prove preserved reasoning or correctness. Stop a probe that would execute a real side effect; replace its tool with an equivalent fixture or use an authorized idempotent test.

Do not remove opaque state experimentally in a production session. If a live ablation is necessary, bound its calls/cost and use an isolated cloned workload. The tool never launches model calls or deletes blocks automatically. Preserve original traces and a replay script so the result is reproducible.

## Validate the migration

Exercise at least a plain continuation, one and multiple tool calls, malformed/failed tool output, commentary then final answer, long-context compaction, reconnect/resume, cancellation, and cross-tenant/resource rejection. Compare baseline and new state path with the same app-level task evaluation. Record which assertions are structural and which were measured against a live model.

## Prove that a probe actually measured its target

A successful HTTP request or zero detected defects is not a pass when the state item was absent, dropped before the tested check, produced by an incompatible model/account, stripped by a gateway or never subjected to the check. Record actual target exposure, check application, compatible scope and violation count. Keep missing/inapplicable checks as not measured; preserve the entire selected population denominator.

`cache_diagnostics.probe_coverage(observations,required_ids)` accepts provider-neutral adapter facts: `{id,target_present,check_applied,same_scope,violations,evidence}`. A zero count passes only when all three facts are explicitly true for every required observation. Missing records are not measured, and any uncovered observation makes an otherwise clean run inconclusive. Establish those facts using current destination fields and trusted capture metadata. Do not invent an OpenAI equivalent of Claude's organization/prefix-binding diagnostics or interpret API acceptance as preserved-reasoning proof.

For Multi-agent, preserve `agent` along with `phase`, opaque items and tool correspondence. State and compaction belong to each agent's context. The mode restrictions and projection rules in [response recipes](response-recipes.md) apply; the generic standalone compact example is not supported when Multi-agent is enabled. Test child-only finals, root finals, missing attribution, hosted/unknown items and a post-compaction continuation independently.
