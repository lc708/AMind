# AMind Engineering frozen comparison — 2026-10-18

18 public application contracts were registered before execution. Protocol SHA-256: `f5a0e2e5c0bed01f534b655dc65c44dd62223cb0dc815837a0056798ee47e817`. The old and new packages were not modified; post-run hashes match every captured package file. No provider, target model, network or subagent was called in this lane.

| Evidence group | Frozen old 0.2.1 | Frozen new 0.3.0 | Repaired current new |
|---|---:|---:|---:|
| Common public-entry behavior (13) | 8 passed / 5 failed | 12 passed / 1 failed | 13 passed / 0 failed |
| Old-correct controls within those 13 | 8/8 | 8/8 | 8/8 |
| Additional packaged executable capability (5) | 5 unsupported | 5 passed | 5 passed |

The five unsupported old cases are staged dependency/coverage, cumulative staged budget, staged public CLI, cache diagnostics and probe measurability. They are coverage additions and are excluded from the common-entry comparison. Old documentation already discusses caching and known-sequence workflows; absent packaged executable support does not mean an agent using the old skill cannot implement them.

## Behavior shared and changed

The eight unchanged correct controls exercise commentary/final separation, contradictory completed bodies, batch order/missing IDs, durable completed-effect reuse, cancellation during authorization, unknown-effect recovery with explicit reconciliation, preservation of hosted/unknown items without dispatch and interrupted streams. The equivalent public module functions are actually executed in both versions; no assertion depends on a new helper name existing.

On the same normalizer/stream entry points, E07/E08/E09/E18 change from old failure to new pass: child-only final, mixed root/child final, streamed item-index projection and conflicting terminal attribution. These establish application behavior on the supplied attributed payloads. They do not establish whole-skill or model superiority, or imply that old documentation promised native multi-agent parity.

## Discovered defect and repair

E10 fails in both frozen versions: one `response.output_item.added` carries outer `agent=/root` but nested `item.agent=/root/helper`; the next unattributed delta is displayed as root text. The frozen-new result records `display_deltas=secret`. Existing regression coverage handled ownership changes across events and terminal responses, not two conflicting owner assertions inside one event.

The minimal current-only repair in `skills/amind-engineering/scripts/response_contract.py` compares both owner assertions and rejects a mismatch before recording the owner or projecting text. A regression adds both conflict directions. Frozen files remain untouched. The original registered suite then passes 18/18 on current repaired code. Four post-discovery validation variants (two conflicts, two equal-owner no-ops) pass 4/4 on repaired code, versus 2/4 on frozen-new and 1/4 on frozen-old. These four are labelled validation, not held out. The current engineering regression suite passes 35/35.

## Reproduction and evidence

```bash
python3 -B reviews/2026-10-18-comparison/engineering/run_compare.py --skill-root .codex-tmp/contrast-2026-10-18/old/skills/amind-engineering --label frozen-old-0.2.1 --output reviews/2026-10-18-comparison/engineering/frozen-old.json
python3 -B reviews/2026-10-18-comparison/engineering/run_compare.py --skill-root .codex-tmp/contrast-2026-10-18/new/skills/amind-engineering --label frozen-new-0.3.0 --output reviews/2026-10-18-comparison/engineering/frozen-new.json
python3 -B reviews/2026-10-18-comparison/engineering/run_compare.py --skill-root skills/amind-engineering --label repaired-new-0.3.0 --output reviews/2026-10-18-comparison/engineering/repaired-new.json
python3 -B reviews/2026-10-18-comparison/engineering/validate_repair.py --root . --output reviews/2026-10-18-comparison/engineering/repair-validation.json
python3 -B scripts/test_amind_behavior_regressions.py --json reviews/2026-10-18-comparison/engineering/regression-results.json
```

`protocol.json` records all expectations; `frozen-old.json`, `frozen-new.json` and `repaired-new.json` contain full invocation, public input, raw results/exceptions, actual CLI argv/stdout/stderr and package file hashes. `verification.json` confirms protocol and frozen-package integrity. Regression stdout/stderr and per-test results are retained. `summary.json` gives machine-readable paired rows. `agent-tasks.json` supplies three public-input, exact-JSON tasks and external criteria for the root lane to run independently against assigned skills.

## Limits

This lane proves deterministic offline local behavior for these captured cases. It does not measure target-agent behavior, broad application quality, SDK/live-service compatibility, cache-hit rate, invoice cost, model latency or model quality. Temporary files, SQLite journals and adapters are real local execution; provider responses and effects are injected fixtures. The root lane owns any later isolated target-model comparison and its budget.
