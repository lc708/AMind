# Execute and recover phased work

`scripts/workflow_contract.py` is an executable provider-neutral local journal. It is not a hosted dynamic-workflow service, model evaluator, sandbox or scheduler. Supply handlers around the real application's entry point; no provider client is bundled. Use item phases for inspection and review and an aggregate phase for synthesis. Specify the entire intended item population before work starts.

## Local vertical slice

Generate a template using [onboarding](onboarding.md). Then:

```bash
python3 "$SKILL_ROOT/scripts/workflow_contract.py" --spec "$PROJECT/agents/example/workflow.json" --db "$PROJECT/agents/example/demo.sqlite"
python3 "$SKILL_ROOT/scripts/workflow_contract.py" --spec "$PROJECT/agents/example/workflow.json" --db "$PROJECT/agents/example/demo.sqlite" --execute-demo
```

The first command validates/prints the plan without creating a database. The second executes deterministic local handlers and persists their real stage transitions. Repeating it reuses succeeded rows. The demo tests orchestration, not model task quality. Replace the draft tenant and run identifiers with authenticated ownership and a new immutable run identity before real work.

## Adapter contract

Import `Workflow(spec, db_path)` and call `run(handlers, authorize, cancelled, retry_failed=False, resume_cancelled=False)`. Handlers map each stage ID to a function receiving the item, dependency outcomes, complete coverage report, stable operation key and remaining time. They return `{status:"succeeded"|"failed",output:...}` only after validating their actual artifact/outcome. A semantic failure should be explicit `failed`; an exception or malformed result leaves the outcome unknown because an external write may already have happened.

The specification freezes `tenant_id`, `run_id`, items, ordered stages, dependencies, required flags and `limits.max_attempts/timeout_s`. Every dependency names an earlier stage; every item has one row in each item stage. Aggregate stages consume all dependency rows, including explicit failed and not-covered outcomes. Required-stage coverage is the intersection of items that succeeded through every required item phase. A successful synthesis cannot turn missing items into completed coverage. No quality score is inferred from an adapter's transport status.

Attempts are committed before handler execution and count across process restarts. The deadline uses the original start time, including downtime. Authorize before dispatch and recheck cancellation/deadline after authorization. Observed cancellation is persisted and blocks new dispatch after a restart; an explicit `resume_cancelled=True` resumes under the original budgets. Reports keep the cancellation fact separate from actual stage outcomes and identify budget/deadline stop reasons. Each handler/transport must enforce its own I/O deadline and remote cancellation; the coordinator only checks between calls. More agents and hosted work can continue to bill after a local stop. Set provider-side session limits when supported and record their scope separately.

## Recovery and coverage

Persist the journal outside disposable compute. The SQLite journal admits one active coordinator using an OS advisory file lock (Unix reference implementation; use a suitable distributed lease for production workers). Database connections and the coordinator lock use the same resolved journal path, so a file symlink alias cannot create a separate coordinator lock. It commits `running` before dispatch. A process crash leaves a row running/unknown; resume never executes that row again. Use the stored operation key to query the external outcome, then call `reconcile(stage,item,"succeeded"|"failed",result,evidence)` with the actual receipt. Do not infer failure from missing local output or invent an external receipt. Reconciliation acquires the same coordinator lock and refuses to overwrite a running handler's operation.

Completed rows are reused. An explicit failed retry requires `retry_failed=True`, the stage's `retry_safe=True`, remaining original budgets and no downstream execution that consumed the old outcome. Otherwise create a new run so stale synthesis cannot survive an upstream change. Failed dependencies produce `not_covered` child items; unknown dependencies wait for reconciliation. Aggregate handlers can summarize known failures, but cannot start while a dependency remains pending/unknown.

Reports retain `status`, per-stage counts/coverage/uncovered IDs, total required-population coverage, attempts and remaining budgets. Store the report, selected input hashes, exact model/runtime/adapter versions, actual usage and output artifacts together. Include adapter/configuration identities in the frozen specification; this journal cannot infer arbitrary injected callable identities or prove their quality. For evaluator integration, pin each required stage's expected total from the frozen workflow/task population; an adapter's self-reported 1/1 cannot replace a selected population of two. Inspect every failure and unsupported item rather than reporting only the successful subset. For reviewed work, review every selected item when that is the accepted quality contract; reviewing only initially flagged items cannot establish the missed-item rate.

## Native multi-agent or hosted execution

Choose the actual destination's [Responses Multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent), Agents SDK or [Agents API sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions) inside an adapter, using current documentation and installed SDK types. Claude's `workflow_run.*`, model defaults, limits and configuration fields have no presumed equivalents. Distinguish event observation from result acceptance, parent cancellation from child/remote cancellation, and phase completion from full population coverage. A staged local run does not create any persistent chat or hosted job implicitly.
