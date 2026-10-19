# Intake desk
A small multi-tenant back-office worker. It receives immutable jobs, inspects each
selected item, reviews successful inspections, and produces a summary receipt.
It runs without network access or a provider SDK. Python standard library only.

## Incident 73: a reopened job lost work and sent another receipt
Operations restored a worker after a process exit during delivery. Some receipts
were sent again; a later summary said all selected items were handled even though
one inspection failed. A second customer sharing the same job number also saw a
confusing recovery error. The saved requests in `traces/` are operational examples.
Repair the intake path across storage, worker and reporting. Preserve the public
CLI, add focused regressions, and document the fix and checks in `PATCH-NOTES.md`.
Public checks: `python -m unittest discover -s tests`.

## Public CLI contract
`python -m intake --db jobs.sqlite --request request.json --receipts receipts.jsonl`
reads one JSON request and prints one JSON report (exit 0), or `{error:...}` (exit 2).
Every command includes trusted tenant and job strings. `submit` includes immutable
spec `{items:[{id,payload}],max_attempts}`; IDs are unique and nonempty. Remaining
operations are work, report, cancel, resume, reconcile. Job identity, data, effects
and reconciliation are tenant-scoped. Resubmitting the same spec is a no-op; a
changed population or budget is a different job and must be rejected.

Worker stages are inspect(item), review(item, requires its successful inspection),
summary(aggregate). The report retains the entire submitted population. Coverage
requires success at both item stages; synthesis cannot erase gaps. Failed item
outcomes are known gaps, not new work to retry automatically. Unknown or pending
item dependencies prevent summary delivery. Each receipt includes context with
coverage and operation_key; keys remain stable across restarts and distinct across
tenants. Only new dispatches consume cumulative max_attempts, including crashes.
Cancel is durable; only explicit resume permits further dispatch under original
budgets. Reporting and resubmission cannot reset attempts or cancellation.

The local receiver appends a JSONL receipt on each call. Payload keys `inspect`
and `review` may be `fail`, otherwise that stage succeeds. For incident replay,
`crash_after_effect` equal to a stage exits the process with code 17 after writing
its receipt. An exit cannot prove the external delivery failed: retain that work
as running/unknown and never auto-replay it on restart. Reconcile takes stage,
item, state (succeeded or failed), result and nonempty external evidence. It may
resolve only an existing unknown operation, and must not rewrite settled work.
There is one local coordinator; distributed locking is outside this incident.
