"""Held-out local failure contracts discovered during skill acceptance.

No model or external service calls. --skill-root can address a frozen old package.
These tests verify kernels, not whole-skill model behavior.
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
loop = load_module('loop_probe', ROOT / 'skills/amind-engineering/scripts/tool_loop.py')
response = load_module('response_probe', ROOT / 'skills/amind-engineering/scripts/response_contract.py')
context = load_module('context_probe', ROOT / 'skills/amind-engineering/scripts/context_audit.py')
workflow = load_module('workflow_probe', ROOT / 'skills/amind-engineering/scripts/workflow_contract.py')
cache = load_module('cache_probe', ROOT / 'skills/amind-engineering/scripts/cache_diagnostics.py')
onboarding = load_module('onboarding_probe', ROOT / 'skills/amind-engineering/scripts/onboarding_contract.py')


class HeldoutContracts(unittest.TestCase):
    def test_bundled_templates_generate_executable_stage_specs_and_reject_path_arguments(self):
        self.assertEqual(len(onboarding.templates()),13)
        for name in onboarding.templates():
            with self.subTest(name=name):
                result=onboarding.plan(name=name)
                spec=json.loads(result['files']['workflow.json'])
                self.assertEqual(workflow.validate(spec),spec)
                config=json.loads(result['files']['agent-config.json'])
                self.assertEqual(config['tools'],[]); self.assertIsNone(config['schedule'])
        with self.assertRaises(ValueError): onboarding.plan(name='../contract-tracker')
        with self.assertRaises(ValueError): onboarding.plan(name='contract-tracker',items=[])

    def test_onboarding_cli_dryrun_writes_nothing_and_explicit_write_preserves_existing(self):
        script=Path(onboarding.__file__)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'draft'; argv=[sys.executable,'-B',str(script),'--template','contract-tracker','--output',str(output)]
            result=subprocess.run(argv,capture_output=True,text=True,check=True)
            self.assertFalse(output.exists()); self.assertFalse(json.loads(result.stdout)['execution'])
            subprocess.run(argv+['--write'],capture_output=True,text=True,check=True)
            original=(output/'agent-config.json').read_bytes()
            result=subprocess.run(argv+['--write'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0); self.assertEqual((output/'agent-config.json').read_bytes(),original)

    def test_url_onboarding_reconstructs_design_and_rejects_commands_credentials(self):
        source={'url':'https://example.org/design','goal':'Compare selected records','evidence':'Selected sections read 2026-10-18'}
        result=onboarding.plan(source=source)
        config=json.loads(result['files']['agent-config.json'])
        self.assertEqual(config['source']['kind'],'extracted_url_design'); self.assertEqual(config['credential_bindings'],[])
        for field in ('script','api_key','instructions','agent_id'):
            with self.subTest(field=field),self.assertRaises(ValueError): onboarding.plan(source={**source,field:'do not copy'})

    def test_workflow_public_cli_plans_without_journal_then_executes_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft=Path(tmp)/'draft'; onboarding.write_plan(onboarding.plan(name='structured-extractor'),draft)
            journal=draft/'demo.sqlite'
            argv=[sys.executable,'-B',str(Path(workflow.__file__)),'--spec',str(draft/'workflow.json'),'--db',str(journal)]
            planned=subprocess.run(argv,capture_output=True,text=True,check=True)
            self.assertFalse(journal.exists()); self.assertFalse(json.loads(planned.stdout)['execution'])
            first=json.loads(subprocess.run(argv+['--execute-demo'],capture_output=True,text=True,check=True).stdout)
            second=json.loads(subprocess.run(argv+['--execute-demo'],capture_output=True,text=True,check=True).stdout)
            self.assertEqual(first['status'],'completed'); self.assertEqual(first['attempts'],3)
            self.assertEqual(second['attempts'],3); self.assertEqual(second['coverage'],1)

    def test_multiagent_child_final_cannot_complete_or_pollute_root_answer(self):
        child={'type':'message','phase':'final_answer','agent':{'agent_name':'/root/child'},'content':[{'type':'output_text','text':'private draft'}]}
        result=response.normalize({'status':'completed','output':[child]})
        self.assertFalse(result['answer_complete']); self.assertEqual(result['final_text'],'')
        root=dict(child,agent={'agent_name':'/root'},content=[{'type':'output_text','text':'approved final'}])
        result=response.normalize({'status':'completed','output':[child,root]})
        self.assertEqual(result['final_text'],'approved final'); self.assertTrue(result['answer_complete'])
        self.assertEqual(result['agent_text']['/root/child'],'private draft')

    def test_multiagent_stream_uses_item_attribution_and_keeps_unknown_bytes(self):
        unknown={'type':'future_hosted_item','opaque':'preserve exactly'}
        events=[{'type':'response.output_item.added','output_index':0,'item':{'agent':{'agent_name':'/root/c'}}},
                {'type':'response.output_text.delta','output_index':0,'delta':'child'},
                {'type':'response.output_text.delta','output_index':1,'agent':{'agent_name':'/root'},'delta':'root'},
                {'type':'response.completed','response':{'status':'completed','output':[unknown]}}]
        result=response.terminal_stream(events)
        self.assertEqual(result['display_deltas'],'root'); self.assertEqual(result['agent_deltas']['/root/c'],'child')
        self.assertEqual(result['unknown_items'],[unknown]); self.assertEqual(result['raw_events'],events)

    def test_multiagent_unattributed_final_is_preserved_but_not_projected(self):
        item={'type':'message','phase':'final_answer','content':[{'type':'output_text','text':'unknown owner'}]}
        result=response.normalize({'status':'completed','output':[item]},mode='multi_agent')
        self.assertEqual(result['output_items'],[item]); self.assertFalse(result['answer_complete'])
        self.assertEqual(result['final_text'],'')
        item['agent']={'agent_name':'/root'}; del item['phase']
        self.assertFalse(response.normalize({'status':'completed','output':[item]},mode='multi_agent')['answer_complete'])

    def test_multiagent_stream_rejects_terminal_agent_attribution_conflict(self):
        events=[{'type':'response.output_item.added','output_index':0,'item':{'agent':{'agent_name':'/root'}}},
                {'type':'response.output_text.delta','output_index':0,'delta':'child-only'},
                {'type':'response.completed','response':{'status':'completed','output':[{
                    'type':'message','phase':'final_answer','agent':{'agent_name':'/root/child'},
                    'content':[{'type':'output_text','text':'child-only'}]}]}}]
        with self.assertRaisesRegex(ValueError,'terminal output changed'): response.terminal_stream(events)

    def test_multiagent_stream_rejects_conflicting_event_and_nested_item_owners(self):
        # Validation variants after a comparison discovered same-event ambiguity.
        # Conflicting assertions must not choose the visible owner by precedence.
        for outer,inner in (('/root','/root/private'),('/root/private','/root')):
            events=[{'type':'response.output_item.added','output_index':2,
                     'agent':{'agent_name':outer},
                     'item':{'type':'message','agent':{'agent_name':inner}}},
                    {'type':'response.output_text.delta','output_index':2,'delta':'unreviewed result'}]
            with self.subTest(outer=outer,inner=inner), self.assertRaisesRegex(ValueError,'event and item'):
                response.terminal_stream(events)

    def test_multiagent_incompatible_modes_rejected_before_request(self):
        for extra in ({'max_tool_calls':3},{'reasoning':{'summary':'auto'}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError): response.validate_mode({'multi_agent':{'enabled':True},**extra})
        with self.assertRaises(ValueError): response.validate_mode({'multi_agent':{'enabled':True}},compact_endpoint=True)
        self.assertTrue(response.validate_mode({'multi_agent':{'enabled':True}})['automatic_compaction'])
        with self.assertRaises(ValueError): response.normalize({'output':[{'type':'agent_message'}]},mode='single')

    def test_hosted_items_never_dispatched_as_developer_tools(self):
        hosted=[{'type':'multi_agent_call','call_id':'h','action':'spawn_agent'},
                {'type':'multi_agent_call_output','call_id':'h','output':'opaque'},
                {'type':'agent_message','content':[{'type':'encrypted_content','encrypted_content':'opaque'}]}]
        with tempfile.TemporaryDirectory() as tmp:
            ledger=loop.EffectLedger(str(Path(tmp)/'effects.db'))
            try:
                result=loop.run_loop(lambda request:{'status':'completed','output':hosted},[],{},'t','job',ledger,lambda *args:self.fail('unexpected authorization'))
                self.assertEqual(result['history'],hosted); self.assertEqual(result['tool_calls'],0)
            finally: ledger.close()

    def test_injection_completion_race_persists_unknown_and_continues_exact_output(self):
        tracker=response.InjectionTracker('r',2)
        call={'type':'function_call','call_id':'c'}; payload=tracker.prepare(call,'result')
        tracker.finish_response(); self.assertFalse(tracker.outcome()['done'])
        restored=response.InjectionTracker('r',2,tracker.snapshot())
        with self.assertRaises(ValueError): restored.prepare(call,'result')
        restored.acknowledge(['c'],{'type':'response.inject.failed','response_id':'r','error':{'code':'response_already_completed'},'input':payload['input']})
        self.assertTrue(restored.outcome()['done']); self.assertEqual(restored.outcome()['continuation_input'],payload['input'])

    def test_injection_budget_cancel_and_unknown_ack_are_bounded(self):
        tracker=response.InjectionTracker('r',1)
        with self.assertRaises(ValueError): tracker.prepare({'type':'multi_agent_call','call_id':'h'},'bad')
        tracker.prepare({'type':'function_call','call_id':'c'},'ok')
        with self.assertRaises(RuntimeError): tracker.prepare({'type':'function_call','call_id':'d'},'ok')
        with self.assertRaises(ValueError): tracker.acknowledge(['d'],{'type':'response.inject.created','response_id':'r'})
        tracker.acknowledge(['c'],{'type':'response.inject.created','response_id':'r'})
        with self.assertRaises(RuntimeError): tracker.prepare({'type':'function_call','call_id':'d'},'ok')
        tracker.cancel()
        with self.assertRaises(RuntimeError): tracker.prepare({'type':'function_call','call_id':'d'},'ok')

    def test_zero_defect_probe_without_exposure_or_same_scope_is_inconclusive(self):
        result=cache.probe_coverage([{'id':'a','target_present':False,'check_applied':True,'same_scope':True,'violations':0}],['a','b'])
        self.assertEqual(result['status'],'inconclusive'); self.assertEqual(result['coverage'],0)
        result=cache.probe_coverage([{'id':'a','target_present':True,'check_applied':True,'same_scope':True,'violations':0}],['a'])
        self.assertEqual(result['status'],'passed')

    def test_cache_diagnostics_are_not_billing_or_context_loading(self):
        captured={'prompt_cache_diagnostics':{'type':'cache_hit'},'usage':{'input_tokens_details':{'cached_tokens':0}},
                  'request_prompt_cache_options':{'comparison_response_id':'r1'}}
        result=cache.analyze(captured,'r1')
        self.assertEqual(result['reported_cached_tokens'],0); self.assertIsNone(result['billing_cost_usd'])
        self.assertEqual(cache.analyze(captured,'other')['status'],'inconclusive')
        self.assertEqual(cache.analyze({})['status'],'not_measured')

    def workflow_spec(self):
        return {'tenant_id':'t','run_id':'run','items':[{'id':'a'},{'id':'b'}],
                'stages':[{'id':'read','retry_safe':True},{'id':'review','depends_on':['read']},
                          {'id':'combine','scope':'aggregate','depends_on':['review']}],
                'limits':{'max_attempts':12,'timeout_s':120}}

    def test_workflow_runs_real_stages_preserves_uncovered_and_resumes_without_calls(self):
        calls=[]
        def execute(ctx):
            calls.append((ctx['stage'],ctx['item_id']))
            return {'status':'failed' if ctx['stage']=='read' and ctx['item_id']=='b' else 'succeeded','output':ctx['item_id']}
        combined=[]
        def combine(ctx):
            combined.append(ctx)
            return {'status':'succeeded','output':'synthesis with explicit gaps'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.db'; spec=self.workflow_spec(); engine=workflow.Workflow(spec,path)
            try:
                report=engine.run({'read':execute,'review':execute,'combine':combine},lambda ctx:None)
                self.assertEqual(report['coverage'],.5); self.assertEqual(report['uncovered_ids'],['b'])
                self.assertEqual(report['status'],'incomplete'); self.assertEqual(combined[0]['coverage']['uncovered_ids'],['b'])
                self.assertEqual(report['attempts'],4)
            finally: engine.close()
            engine=workflow.Workflow(spec,path)
            try:
                before=len(calls); report=engine.run({'read':execute,'review':execute,'combine':combine},lambda ctx:None)
                self.assertEqual(len(calls),before); self.assertEqual(len(combined),1)
            finally: engine.close()

    def test_workflow_item_dependencies_are_scoped_while_aggregate_retains_full_population(self):
        seen=[]
        def execute(ctx):
            seen.append((ctx['stage'],ctx['item_id'],[r['id'] for r in ctx['dependencies']]))
            return {'status':'succeeded','output':ctx['item_id']}
        with tempfile.TemporaryDirectory() as tmp:
            engine=workflow.Workflow(self.workflow_spec(),Path(tmp)/'journal.db')
            try: engine.run({key:execute for key in ('read','review','combine')},lambda ctx:None)
            finally: engine.close()
        self.assertIn(('review','a',['a']),seen); self.assertIn(('review','b',['b']),seen)
        self.assertIn(('combine','__aggregate__',['a','b']),seen)

    def test_workflow_crash_never_replays_unknown_or_loses_budget(self):
        side_effects=[]; spec=self.workflow_spec()
        def crash(ctx): side_effects.append(ctx['operation_key']); raise TimeoutError('remote may have written')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.db'; engine=workflow.Workflow(spec,path)
            try:
                with self.assertRaises(TimeoutError): engine.run({'read':crash,'review':crash,'combine':crash},lambda ctx:None)
            finally: engine.close()
            engine=workflow.Workflow(spec,path)
            try:
                def ok(ctx): return {'status':'succeeded','output':'verified'}
                report=engine.run({'read':ok,'review':ok,'combine':ok},lambda ctx:None)
                self.assertEqual(len(side_effects),1); self.assertEqual(report['status'],'unknown')
                self.assertEqual(report['attempts'],3)
                with self.assertRaises(ValueError): engine.reconcile('read','a','succeeded','verified','')
                engine.reconcile('read','a','succeeded','verified','remote receipt verified')
                report=engine.run({'read':ok,'review':ok,'combine':ok},lambda ctx:None)
                self.assertEqual(report['status'],'completed'); self.assertEqual(report['coverage'],1)
                self.assertEqual(report['attempts'],5)
            finally: engine.close()

    def test_workflow_cancel_during_authorization_prevents_work(self):
        flag=[False]; calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            engine=workflow.Workflow(self.workflow_spec(),Path(tmp)/'journal.db')
            try:
                def authorize(ctx): flag[0]=True
                report=engine.run({k:lambda ctx:calls.append(ctx) for k in ('read','review','combine')},authorize,cancelled=lambda:flag[0])
                self.assertEqual(report['attempts'],0); self.assertEqual(calls,[])
            finally: engine.close()

    def test_workflow_each_stage_failure_or_unknown_stays_out_of_coverage(self):
        for failure_stage in ('read','review'):
            for unknown in (False,True):
                with self.subTest(stage=failure_stage,unknown=unknown), tempfile.TemporaryDirectory() as tmp:
                    engine=workflow.Workflow(self.workflow_spec(),Path(tmp)/'journal.db')
                    def execute(ctx):
                        if ctx['stage']==failure_stage and ctx['item_id']=='a':
                            if unknown: raise TimeoutError('unknown outcome')
                            return {'status':'failed','output':'verified failure'}
                        return {'status':'succeeded','output':'ok'}
                    try:
                        handlers={k:execute for k in ('read','review','combine')}
                        if unknown:
                            with self.assertRaises(TimeoutError): engine.run(handlers,lambda ctx:None)
                        else: engine.run(handlers,lambda ctx:None)
                        self.assertIn('a',engine.report()['uncovered_ids'])
                        self.assertNotEqual(engine.report()['status'],'completed')
                    finally: engine.close()

    def test_workflow_retry_refuses_to_reuse_stale_downstream_synthesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=workflow.Workflow(self.workflow_spec(),Path(tmp)/'journal.db')
            def execute(ctx): return {'status':'failed' if ctx['stage']=='read' and ctx['item_id']=='a' else 'succeeded','output':'checked'}
            try:
                handlers={k:execute for k in ('read','review','combine')}
                engine.run(handlers,lambda ctx:None)
                with self.assertRaisesRegex(ValueError,'stale synthesis'): engine.run(handlers,lambda ctx:None,retry_failed=True)
            finally: engine.close()

    def test_workflow_cancel_at_later_phase_keeps_prior_results_and_population(self):
        flag=[False]
        with tempfile.TemporaryDirectory() as tmp:
            engine=workflow.Workflow(self.workflow_spec(),Path(tmp)/'journal.db')
            try:
                def authorize(ctx):
                    if ctx['stage']=='review': flag[0]=True
                def ok(ctx): return {'status':'succeeded','output':'ok'}
                report=engine.run({k:ok for k in ('read','review','combine')},authorize,cancelled=lambda:flag[0])
                self.assertEqual(report['attempts'],2); self.assertEqual(report['uncovered_ids'],['a','b'])
                self.assertEqual(report['stages'][0]['coverage'],1); self.assertEqual(report['stages'][1]['coverage'],0)
            finally: engine.close()

    def test_workflow_cancel_is_durable_and_explicit_resume_keeps_original_budget(self):
        spec=self.workflow_spec()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.db'; engine=workflow.Workflow(spec,path)
            handlers={key:lambda ctx:{'status':'succeeded','output':'ok'} for key in ('read','review','combine')}
            try:
                report=engine.run(handlers,lambda ctx:None,cancelled=lambda:True)
                self.assertEqual(report['status'],'cancelled'); self.assertEqual(report['attempts'],0)
            finally: engine.close()
            engine=workflow.Workflow(spec,path)
            try:
                report=engine.run(handlers,lambda ctx:None)
                self.assertEqual(report['status'],'cancelled'); self.assertEqual(report['attempts'],0)
                report=engine.run(handlers,lambda ctx:None,resume_cancelled=True)
                self.assertEqual(report['status'],'completed'); self.assertEqual(report['attempts'],5)
                self.assertEqual(report['remaining_attempts'],7)
            finally: engine.close()

    def test_workflow_reconciliation_cannot_overwrite_an_active_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.db'; engine=workflow.Workflow(self.workflow_spec(),path)
            def execute(ctx):
                other=workflow.Workflow(self.workflow_spec(),path)
                try:
                    with self.assertRaisesRegex(RuntimeError,'active coordinator'):
                        other.reconcile(ctx['stage'],ctx['item_id'],'succeeded','forged while active','unverified race')
                finally: other.close()
                return {'status':'succeeded','output':'actual handler receipt'}
            try:
                report=engine.run({key:execute for key in ('read','review','combine')},lambda ctx:None)
                self.assertEqual(report['status'],'completed')
                self.assertTrue(all(row['result']=='actual handler receipt' for row in engine.rows()))
            finally: engine.close()

    def test_workflow_identity_and_cumulative_attempt_deadline_guards(self):
        spec=self.workflow_spec(); spec['limits']['max_attempts']=1; now=[10]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.db'; engine=workflow.Workflow(spec,path,clock=lambda:now[0])
            try:
                handlers={k:lambda ctx:{'status':'succeeded','output':'ok'} for k in ('read','review','combine')}
                self.assertEqual(engine.run(handlers,lambda ctx:None)['attempts'],1)
            finally: engine.close()
            now[0]=200; engine=workflow.Workflow(spec,path,clock=lambda:now[0])
            try:
                report=engine.run(handlers,lambda ctx:None); self.assertEqual(report['attempts'],1); self.assertEqual(report['remaining_seconds'],0)
            finally: engine.close()
            altered=dict(spec,tenant_id='other')
            with self.assertRaises(ValueError): workflow.Workflow(altered,path)

    def test_workflow_file_symlink_uses_the_same_active_coordinator_lock(self):
        spec={'tenant_id':'north','run_id':'delivery-79','items':[{'id':'invoice'}],
              'stages':[{'id':'deliver'}],'limits':{'max_attempts':3,'timeout_s':60}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'delivery.sqlite'; alias=Path(tmp)/'active.sqlite'
            engine=workflow.Workflow(spec,path); alias.symlink_to(path)
            receipt={'receipt_id':'receiver-79','delivered':True}
            calls=[]
            def deliver(ctx):
                calls.append(ctx['operation_key'])
                (Path(tmp)/'receipt.json').write_text(json.dumps(receipt))
                other=workflow.Workflow(spec,alias)
                try:
                    with self.assertRaisesRegex(RuntimeError,'active coordinator'):
                        other.reconcile('deliver','invoice','succeeded',receipt,'Receiver-79 receipt verified')
                finally: other.close()
                return {'status':'succeeded','output':receipt}
            try:
                self.assertEqual(engine.run({'deliver':deliver},lambda ctx:None)['status'],'completed')
            finally: engine.close()
            reopened=workflow.Workflow(spec,alias)
            try:
                report=reopened.run({'deliver':deliver},lambda ctx:None)
                self.assertEqual(report['attempts'],1); self.assertEqual(len(calls),1)
                self.assertEqual(reopened.rows()[0]['result'],receipt)
            finally: reopened.close()

    def test_chain_audit_warns_on_phase_lost_replay_but_not_fresh_user_text(self):
        original = {'type': 'message', 'role': 'assistant', 'phase': 'commentary',
                    'content': 'Working'}
        first = {'state_owner': 'response_chain', 'request': {'input': []},
                 'response': {'id': 'r1', 'output': [original]}}
        replay = {key: value for key, value in original.items() if key != 'phase'}
        second = {'state_owner': 'response_chain', 'request': {
            'previous_response_id': 'r1', 'input': [replay]}}
        result = context.audit([first, second])
        findings = [item for item in result['findings']
                    if item['code'] == 'possible_phase_drift_replay']
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['severity'], 'warning')
        self.assertNotIn('Working', json.dumps(result))
        second['request']['input'] = [dict(replay, role='user')]
        self.assertEqual(context.audit([first, second])['findings'], [])

    def test_completed_with_incomplete_details_is_rejected_on_both_paths(self):
        body = {'status': 'completed', 'output': [],
                'incomplete_details': {'reason': 'max_output_tokens'}}
        with self.subTest(surface='response'):
            with self.assertRaises(ValueError):
                response.normalize(body)
        with self.subTest(surface='batch'):
            result = response.match_batch(['x'], [{'custom_id': 'x', 'response': {
                'status_code': 200, 'body': body}}])
            self.assertIn('x', result['errors'])

    def test_batch_completed_body_with_error_is_not_success(self):
        raw = {'custom_id': 'x', 'response': {'status_code': 200, 'body': {
            'status': 'completed', 'error': {'code': 'upstream_failure'},
            'usage': {'output_tokens': 17}}}}
        result = response.match_batch(['x'], [raw])
        self.assertIn('x', result['errors'])
        self.assertEqual(result['ordered'][0], raw)

    def test_contradictory_completed_error_is_not_accepted(self):
        with self.assertRaises(ValueError):
            response.normalize({'status': 'completed', 'output': [], 'error': {'code': 'failed'}})

    def test_interrupted_stream_preserves_raw_usage_evidence(self):
        events = [{'type': 'response.in_progress', 'response': {'usage': {'output_tokens': 17}}},
                  {'type': 'response.output_text.delta', 'delta': 'partial'}]
        result = response.terminal_stream(events)
        self.assertFalse(result['scorable_transport'])
        self.assertEqual(result.get('raw_events'), events)
        self.assertIsNone(result['usage'], 'partial usage evidence must not be advertised as a final bill')

    def test_legacy_remote_key_is_reused_for_pending_operation(self):
        effects = []
        request = {'task': 'job', 'name': 'charge', 'args': {}}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                def lost_receipt(key):
                    effects.append(key)
                    raise TimeoutError('remote succeeded, receipt lost')
                with self.assertRaises(TimeoutError):
                    ledger.perform('tenant', 'persisted-old-key', request, lost_receipt)
                tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None,
                        'handler': lambda arguments, key: effects.append(key), 'side_effect': True}
                with self.assertRaises(loop.ReconciliationRequired):
                    loop.run_loop(lambda unused: {'status': 'completed', 'output': [
                        {'type': 'function_call', 'call_id': 'c', 'name': 'charge', 'arguments': '{}'}]},
                        [], {'charge': tool}, 'tenant', 'job', ledger, lambda *x: None,
                        operation_key_for=lambda *scope: 'persisted-old-key')
                self.assertEqual(effects, ['persisted-old-key'])
            finally:
                ledger.close()

    def test_remote_key_scopes_tenant_even_when_task_and_call_ids_match(self):
        keys = []
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                for tenant in ('tenant-a', 'tenant-b'):
                    turns = iter([
                        {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'same-call', 'name': 'charge', 'arguments': '{"amount": 20}'}]},
                        {'status': 'completed', 'output': []},
                    ])
                    def handler(arguments, key):
                        keys.append(key)
                        return {'operation_id': key}
                    tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None, 'handler': handler, 'side_effect': True}
                    loop.run_loop(lambda request: next(turns), [], {'charge': tool}, tenant, 'same-task', ledger, lambda *x: None)
            finally:
                ledger.close()
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2, 'remote dedup keys must not alias across authenticated tenants')

    def test_cancellation_during_authorization_prevents_dispatch(self):
        cancelled = [False]
        effects = []
        def authorize(*unused):
            cancelled[0] = True
        def handler(arguments, key):
            effects.append(key)
            return 'charged'
        tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None, 'handler': handler, 'side_effect': True}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                    loop.run_loop(lambda request: {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'c', 'name': 'charge', 'arguments': '{}'}]}, [], {'charge': tool}, 't', 'job', ledger, authorize, cancelled=lambda: cancelled[0])
            finally:
                ledger.close()
        self.assertEqual(effects, [], 'no new effect after cancellation observed during authorization')

    def test_tool_loop_rejects_contradictory_completion_before_tool_authorization(self):
        call={'type':'function_call','call_id':'send-79','name':'send_invoice','arguments':'{"invoice":"79"}'}
        for contradiction in ({'error':{'code':'adapter_failure'}},{'incomplete_details':{'reason':'max_output_tokens'}},
                              {'error':{}},{'incomplete_details':{}}):
            with self.subTest(contradiction=contradiction), tempfile.TemporaryDirectory() as tmp:
                ledger=loop.EffectLedger(str(Path(tmp)/'effects.sqlite')); touched=[];requests=[]
                def adapter(request):
                    requests.append(request);return {'status':'completed','output':[call],**contradiction}
                def handler(args,key):
                    touched.append('handler'); (Path(tmp)/'receipt.json').write_text(json.dumps({'receipt':key})); return 'sent'
                tool={'schema':{'name':'send_invoice'},'validate':lambda args:touched.append('validate'),
                      'handler':handler,'side_effect':True}
                try:
                    with self.assertRaisesRegex(ValueError,'completed response'):
                        loop.run_loop(adapter,[],
                                      {'send_invoice':tool},'north','invoice-79',ledger,lambda *args:touched.append('authorize'))
                    self.assertEqual(len(requests),1); self.assertEqual(touched,[])
                    self.assertFalse((Path(tmp)/'receipt.json').exists())
                finally: ledger.close()

    def test_tool_loop_terminal_validation_preserves_phase_and_opaque_items(self):
        output=[{'type':'reasoning','encrypted_content':'opaque-thought'},
                {'type':'message','phase':'commentary','agent':{'agent_name':'/root'},'content':[{'type':'output_text','text':'Checking'}]},
                {'type':'future_hosted_item','opaque':{'bytes':[0,False,'keep']}},
                {'type':'function_call','call_id':'send-79','name':'send_invoice','arguments':'{}'}]
        final={'status':'completed','output':[{'type':'message','phase':'final_answer','agent':{'agent_name':'/root'},'content':[{'type':'output_text','text':'Sent'}]}]}
        turns=iter([{'status':'completed','output':output,'error':None,'incomplete_details':None},final]); requests=[];effects=[]
        def adapter(request):
            requests.append(json.loads(json.dumps(request))); return next(turns)
        def send(args,key):effects.append(key);return {'receipt':key}
        tool={'schema':{'name':'send_invoice'},'validate':lambda args:None,'handler':send,'side_effect':True}
        with tempfile.TemporaryDirectory() as tmp:
            ledger=loop.EffectLedger(str(Path(tmp)/'effects.sqlite'))
            try: result=loop.run_loop(adapter,[],{'send_invoice':tool},'north','invoice-79',ledger,lambda *args:None)
            finally: ledger.close()
        self.assertEqual(len(effects),1); self.assertEqual(len(requests),2)
        self.assertEqual(requests[1]['input'][:len(output)],output)
        self.assertEqual(result['history'][:len(output)],output); self.assertEqual(result['response'],final)
        self.assertEqual(result['history'][len(output)]['call_id'],'send-79')

    def test_tool_loop_preserves_legacy_message_content_without_display_parsing(self):
        output=[{'type':'message','phase':'commentary','content':'Working raw'},
                {'type':'future_hosted_item','opaque':{'keep':[0,False,'bytes']}},
                {'type':'function_call','call_id':'send-legacy','name':'send_invoice','arguments':'{}'}]
        final={'status':'completed','output':[{'type':'message','content':'done'}]}
        with self.assertRaisesRegex(ValueError,'message content must be an item array'):
            response.normalize(final)
        turns=iter([{'status':'completed','output':output,'error':None,'incomplete_details':None},final])
        requests=[];effects=[]
        def adapter(request):
            requests.append(json.loads(json.dumps(request)));return next(turns)
        def send(args,key):effects.append(key);return {'receipt':key}
        tool={'schema':{'name':'send_invoice'},'validate':lambda args:None,'handler':send,'side_effect':True}
        with tempfile.TemporaryDirectory() as tmp:
            ledger=loop.EffectLedger(str(Path(tmp)/'effects.sqlite'))
            try: result=loop.run_loop(adapter,[],{'send_invoice':tool},'north','legacy',ledger,lambda *args:None)
            finally: ledger.close()
        self.assertEqual(result['status'],'completed');self.assertEqual(result['response'],final)
        self.assertEqual(result['history'][-1],final['output'][0]);self.assertEqual(len(effects),1)
        self.assertEqual(len(requests),2);self.assertEqual(requests[1]['input'][:len(output)],output)

    def test_effect_ledger_preserves_confirmation_when_late_handler_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'effects.sqlite'); ledger=loop.EffectLedger(path)
            request={'invoice':'79'};confirmed={'receipt_id':'receiver-79','status':'delivered'};calls=[]
            def handler(key):
                calls.append(key); (Path(tmp)/'receipt.json').write_text(json.dumps(confirmed))
                controller=loop.EffectLedger(path)
                try: controller.reconcile('north',key,confirmed,'Actual receiver-79 receipt checked')
                finally: controller.close()
                return {'receipt_id':'receiver-79','local_status':'timeout'}
            try:
                with self.assertRaisesRegex(loop.ReconciliationRequired,'confirmed result retained'):
                    ledger.perform('north','send-79',request,handler)
                actual=ledger.perform('north','send-79',request,lambda key:self.fail('must not send again'))
                self.assertEqual(actual,confirmed); self.assertEqual(calls,['send-79'])
            finally: ledger.close()

    def test_effect_ledger_matching_late_confirmation_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'effects.sqlite'); ledger=loop.EffectLedger(path)
            confirmed={'receipt_id':'receiver-79','status':'delivered'};calls=[]
            def handler(key):
                calls.append(key); controller=loop.EffectLedger(path)
                try: controller.reconcile('north',key,confirmed,'Receiver-79 confirmed externally')
                finally: controller.close()
                return {'status':'delivered','receipt_id':'receiver-79'}
            try:
                self.assertEqual(ledger.perform('north','send-79',{'invoice':'79'},handler),confirmed)
                self.assertEqual(ledger.perform('north','send-79',{'invoice':'79'},lambda key:self.fail('duplicate')),confirmed)
                self.assertEqual(calls,['send-79'])
            finally: ledger.close()

    def test_effect_ledger_process_crash_keeps_pending_until_reconciled(self):
        child='''import importlib.util,json,os,sys
spec=importlib.util.spec_from_file_location('crash_loop',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ledger=m.EffectLedger(sys.argv[2])
def handler(key):
    with open(sys.argv[3],'a') as receipt:
        receipt.write(json.dumps({'receipt_id':'receiver-crash-79'})+'\\n');receipt.flush();os.fsync(receipt.fileno())
    os._exit(17)
ledger.perform('north','send-79',{'invoice':'79'},handler)
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'effects.sqlite');receipts=Path(tmp)/'receipts.jsonl'
            process=subprocess.run([sys.executable,'-B','-c',child,str(Path(loop.__file__).resolve()),path,str(receipts)],capture_output=True,text=True,timeout=10)
            self.assertEqual(process.returncode,17,process.stdout+process.stderr)
            ledger=loop.EffectLedger(path)
            try:
                with self.assertRaises(loop.ReconciliationRequired):
                    ledger.perform('north','send-79',{'invoice':'79'},lambda key:self.fail('unknown effect replay'))
                receipt=json.loads(receipts.read_text().strip())
                ledger.reconcile('north','send-79',receipt,'Actual persisted receiver-crash-79 receipt verified')
                self.assertEqual(ledger.perform('north','send-79',{'invoice':'79'},lambda key:self.fail('duplicate after reconciliation')),receipt)
                self.assertEqual(len(receipts.read_text().splitlines()),1)
            finally: ledger.close()

    def test_batch_http_success_does_not_hide_incomplete_body(self):
        raw = {'custom_id': 'x', 'response': {'status_code': 200, 'body': {'status': 'incomplete', 'usage': {'output_tokens': 17}}}}
        result = response.match_batch(['x'], [raw])
        self.assertIn('x', result['errors'])
        self.assertEqual(result['ordered'][0]['response']['body']['usage'], {'output_tokens': 17})

    def test_text_projection_distinguishes_commentary_and_final(self):
        output = [
            {'type': 'reasoning', 'encrypted_content': 'opaque'},
            {'type': 'message', 'role': 'assistant', 'phase': 'commentary', 'content': [{'type': 'output_text', 'text': 'Working'}]},
            {'type': 'function_call', 'call_id': 'c', 'name': 'lookup', 'arguments': '{}'},
        ]
        result = response.normalize({'status': 'completed', 'output': output})
        self.assertEqual(result.get('final_text'), '')
        self.assertEqual(result.get('commentary_text'), 'Working')
        self.assertFalse(result.get('answer_complete'))
        self.assertEqual(result['output_items'], output)
        final = response.normalize({'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'content': [{'type': 'output_text', 'text': 'Ready'}]}]})
        self.assertEqual(final.get('final_text'), 'Ready')
        self.assertTrue(final.get('answer_complete'))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.records = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'test': test.id(), 'status': 'passed'})
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'test': test.id(), 'status': 'failed', 'detail': self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'test': test.id(), 'status': 'error', 'detail': self._exc_info_to_string(err, test)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=ROOT / 'skills/amind-engineering')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    loop = load_module('loop_probe', args.skill_root / 'scripts/tool_loop.py')
    response = load_module('response_probe', args.skill_root / 'scripts/response_contract.py')
    context = load_module('context_probe', args.skill_root / 'scripts/context_audit.py')
    workflow = load_module('workflow_probe', args.skill_root / 'scripts/workflow_contract.py')
    cache = load_module('cache_probe', args.skill_root / 'scripts/cache_diagnostics.py')
    onboarding = load_module('onboarding_probe', args.skill_root / 'scripts/onboarding_contract.py')
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeldoutContracts))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({'skill_root': str(args.skill_root.resolve()), 'tests_run': result.testsRun,
                                        'tests': result.records, 'passed': result.wasSuccessful(),
                                        'failures': [{'test': str(test), 'detail': detail} for test, detail in result.failures + result.errors],
                                        'scope': 'offline kernel contracts, not agent behavior'}, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
