"""Independent engineering repair review; only local synthetic public API calls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SCRIPTS = ROOT / 'skills/amind-engineering/scripts'
RESULTS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(name, **result):
    RESULTS.append({'case': name, **result})


def main():
    # A host may already have unrelated or old top-level modules cached.
    poisoned = []
    fake = types.ModuleType('response_contract')
    fake.normalize = lambda body: poisoned.append(copy.deepcopy(body))
    sys.modules['response_contract'] = fake
    sys.modules['amind_loop_response_contract'] = fake
    poison_dir = HERE / 'poison-import'; poison_dir.mkdir(exist_ok=True)
    (poison_dir / 'response_contract.py').write_text('def normalize(body): return {"incorrect_cached_contract": True}\n')
    sys.path.insert(0, str(poison_dir))
    loop = load('independent_cross_loop', SCRIPTS / 'tool_loop.py')
    normalizer_path = Path(loop._response_contract.normalize.__code__.co_filename).resolve()
    assert normalizer_path == (SCRIPTS / 'response_contract.py').resolve()
    calls, effects, authorization = [], [], []
    call = {'type': 'function_call', 'name': 'deliver', 'call_id': 'task-r9', 'arguments': '{}'}
    ledger = loop.EffectLedger(str(HERE / 'import-control.sqlite'))
    try:
        tool = {'schema': {'name': 'deliver'}, 'validate': lambda args: effects.append('validate'),
                'handler': lambda args, key: effects.append('dispatch'), 'side_effect': True}
        def invalid_adapter(request):
            calls.append(request)
            return {'status': 'completed', 'output': [call], 'error': {}}
        try:
            loop.run_loop(invalid_adapter, [], {'deliver': tool}, 'tenant', 'job', ledger,
                          lambda *args: authorization.append('authorized'))
            raise AssertionError('Contradictory completed response accepted')
        except ValueError as exc:
            rejection = str(exc)
        assert not effects and not authorization and len(calls) == 1 and not poisoned
        record('normalizer_ignores_poisoned_import_cache', passed=True, actual_source=str(normalizer_path),
               poisoned_cache_calls=len(poisoned), application_calls=len(calls), effects=effects, error=rejection)
        output = [{'type': 'reasoning', 'encrypted_content': 'opaque-r9'},
                  {'type': 'future_hosted_item', 'opaque': {'blob': [0, False, 'preserve']}}, call]
        final = {'status': 'completed', 'output': [{'type': 'message', 'phase': 'final_answer',
                 'content': [{'type': 'output_text', 'text': 'Delivered'}]}], 'error': None, 'incomplete_details': None}
        iterator = iter([{'status': 'completed', 'output': output, 'error': None, 'incomplete_details': None}, final])
        requests, actual = [], []
        def adapter(request):
            requests.append(copy.deepcopy(request)); return next(iterator)
        tool['validate'] = lambda args: None
        tool['handler'] = lambda args, key: actual.append(key) or {'receipt': 'r9'}
        result = loop.run_loop(adapter, [], {'deliver': tool}, 'tenant', 'healthy', ledger, lambda *args: None)
        assert len(actual) == 1 and requests[1]['input'][:len(output)] == output and result['response'] == final
        record('healthy_completed_preserves_raw_continuation', passed=True, dispatched=len(actual), raw_output_preserved=True)
    finally:
        ledger.close()
    workflow = load('independent_cross_workflow', SCRIPTS / 'workflow_contract.py')
    spec = {'tenant_id': 'tenant', 'run_id': 'shipping-r9', 'items': [{'id': 'invoice'}],
            'stages': [{'id': 'deliver'}], 'limits': {'max_attempts': 4, 'timeout_s': 120}}
    physical = HERE / 'physical'; physical.mkdir(exist_ok=True)
    directory_alias = HERE / 'alias-directory'; directory_alias.symlink_to(physical, target_is_directory=True)
    db = physical / 'shipping.sqlite'
    file_alias = physical / 'live.sqlite'; file_alias.symlink_to(db.name)
    engine = workflow.Workflow(spec, directory_alias / 'live.sqlite')
    receipts, blocked = [], []
    def handler(context):
        receipts.append(context['operation_key'])
        other = workflow.Workflow(spec, db)
        try:
            assert other.path == engine.path == db.resolve()
            try:
                other.reconcile('deliver', 'invoice', 'succeeded', {'receipt': 'r9'}, 'Local fixture receipt verified')
                raise AssertionError('Alias bypassed the active coordinator')
            except RuntimeError as exc:
                blocked.append(str(exc))
        finally:
            other.close()
        return {'status': 'succeeded', 'output': {'receipt': 'r9'}}
    try:
        completed = engine.run({'deliver': handler}, lambda ctx: None)
        assert completed['status'] == 'completed' and len(receipts) == 1
    finally:
        engine.close()
    reopened = workflow.Workflow(spec, file_alias)
    try:
        again = reopened.run({'deliver': lambda ctx: (_ for _ in ()).throw(AssertionError('completed task replayed'))}, lambda ctx: None)
        assert again['attempts'] == 1 and reopened.rows()[0]['result'] == {'receipt': 'r9'}
    finally:
        reopened.close()
    record('directory_and_file_alias_share_db_lock', passed=True, canonical_db=str(db.resolve()),
           rejected_reconcile=blocked, external_receipts=len(receipts), replay_attempts=again['attempts'])
    # Reconcile while a handler is returning, then ensure confirmed state wins.
    for matching in (False, True):
        path = HERE / ('effect-match.sqlite' if matching else 'effect-conflict.sqlite')
        ledger = loop.EffectLedger(str(path)); touched = []
        confirmed = {'receipt': 'receiver-r9', 'delivered': True}
        def late_handler(key):
            touched.append(key)
            control = loop.EffectLedger(str(path))
            try:
                control.reconcile('tenant', key, confirmed, 'Confirmed local receiver-r9 receipt checked')
            finally:
                control.close()
            return {'delivered': True, 'receipt': 'receiver-r9'} if matching else {'delivered': False, 'receipt': 'receiver-r9'}
        conflict = None
        try:
            try:
                result = ledger.perform('tenant', 'send-r9', {'invoice': 'r9'}, late_handler)
                assert matching and result == confirmed
            except loop.ReconciliationRequired as exc:
                conflict = str(exc); assert not matching
            cached = ledger.perform('tenant', 'send-r9', {'invoice': 'r9'}, lambda key: (_ for _ in ()).throw(AssertionError('second dispatch')))
            assert cached == confirmed and len(touched) == 1
        finally:
            ledger.close()
        record('late_matching_receipt' if matching else 'late_conflict_retains_confirmed_receipt', passed=True,
               dispatches=len(touched), cached=cached, conflict=conflict)
    # Actual process crash releases canonical coordinator lock but never makes a running result retryable.
    crash_db = physical / 'crashed.sqlite'
    crash_alias = physical / 'crashed-active.sqlite'; crash_alias.symlink_to(crash_db.name)
    child = """import importlib.util,json,os,sys
s=importlib.util.spec_from_file_location('crash_workflow',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
spec=json.loads(sys.argv[2]);engine=m.Workflow(spec,sys.argv[3])
def handler(ctx):
 with open(sys.argv[4],'w') as f:json.dump({'receipt':'crash-r9'},f);f.flush();os.fsync(f.fileno())
 os._exit(23)
engine.run({'deliver':handler},lambda ctx:None)
"""
    receipt_file = HERE / 'crash-receipt.json'
    process = subprocess.run([sys.executable, '-B', '-c', child, str(SCRIPTS / 'workflow_contract.py'),
                              json.dumps(spec), str(directory_alias / 'crashed-active.sqlite'), str(receipt_file)],
                             capture_output=True, text=True, timeout=10)
    assert process.returncode == 23
    recovered = workflow.Workflow(spec, crash_db)
    try:
        handlers = {'deliver': lambda ctx: (_ for _ in ()).throw(AssertionError('unknown operation replayed'))}
        unknown = recovered.run(handlers, lambda ctx: None)
        assert unknown['status'] == 'unknown' and unknown['attempts'] == 1
        recovered.reconcile('deliver', 'invoice', 'succeeded', json.loads(receipt_file.read_text()), 'Actual fsynced local receipt from terminated process verified')
        completed = recovered.run(handlers, lambda ctx: None)
        assert completed['status'] == 'completed' and completed['attempts'] == 1
    finally:
        recovered.close()
    record('actual_workflow_process_crash_recovers_through_alias', passed=True, exit_code=process.returncode,
           before_reconciliation=unknown['status'], after_reconciliation=completed['status'], attempts=completed['attempts'])
    summary = {'all_passed': all(r['passed'] for r in RESULTS), 'findings': [], 'cases': RESULTS,
               'scope': 'Independent read-only product review with offline public APIs; no product changes or target runs/captures/models accessed.',
               'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in ('tool_loop.py', 'workflow_contract.py', 'response_contract.py')}}
    (HERE / 'review.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
