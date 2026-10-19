"""Executable capability contracts, using synthetic local processes; never calls a model."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'skills/eval-improve'
sys.path.insert(0, str(EVAL / 'scripts'))
import kernel_common as common
import run_eval as runner
import compare_runs as comparison
import price_usage
import calibrate_grader
import report_eval
import seal_selection
import reconcile_run
sys.path.insert(0,str(ROOT / "skills/amind-engineering/scripts"))
import context_audit
import lifecycle_audit
import prompt_inventory
import tool_loop
import response_contract

APP = r'''
import json, sys, time
from pathlib import Path
p = json.load(sys.stdin)
i, c = p['input'], p['context']
assert 'reference' not in p and 'expected' not in p and 'baseline_output' not in p
with Path('calls.jsonl').open('a') as f: f.write(json.dumps(p) + '\n')
action = i.get('action')
if action == 'timeout': time.sleep(20)
if action == 'oversize':
    print('x' * 100000); sys.exit()
if action == 'retry':
    marker = Path('tried-' + c['case_id'])
    if not marker.exists():
        marker.write_text('1')
        print(json.dumps({'error':{'kind':'rate_limit','retryable':True}, 'cost_usd': .01})); sys.exit(1)
if action == 'drift': Path('control.txt').write_text('changed')
if action == 'artifact':
    w = Path(c['workspace']); (w / 'answer.txt').write_text('correct')
    if i.get('extra'): (w / 'extra.txt').write_text('unwanted')
out = i['text'].upper() if c['config'].get('uppercase') else i['text']
r = {'output':out,'cost_usd':.02,'model':i.get('served','mock'),'synthetic':True}
if action == 'unknown_cost': r.pop('cost_usd')
if action == 'bad_cost': r['cost_usd'] = -1
if action == 'truncated': r['status'] = 'truncated'
print(json.dumps(r))
'''


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='amind-kernel-offline-')
        self.root = Path(self.temp.name).resolve()
        self.flow = self.root / 'flow'
        (self.root / 'app.py').write_text(APP)
        (self.root / 'control.txt').write_text('stable')
        self.cases = [{'id':'a','input':{'text':'apple'}}, {'id':'b','input':{'text':'pear'}}]
        self.refs = [{'id':'a','expected':'APPLE'}, {'id':'b','expected':'PEAR'}]
        self.card = {'schema_version':2,'task':'synthetic','dataset_version':'1','grader_version':'1',
                     'cases':'cases.jsonl','references':'refs.jsonl',
                     'splits':{'train':[],'val':['a','b'],'test':[]},
                     'metrics':[{'id':'quality','kind':'binary','better':'higher','role':'objective','min_improvement':0}],
                     'runner':{'command':[sys.executable,'app.py'],'files':['app.py'],'retry_safe':True},
                     'grader':{'kind':'exact'},'control_files':['control.txt'], 'mutable_config':['uppercase'],
                     'variants':{k:{'files':['app.py'],'config':{'uppercase':v},'expected_model':'mock'}
                                 for k,v in [('baseline',False),('v1',True)]},
                     'limits':{'max_attempts':8,'concurrency':2,'timeout_s':2,'max_total_seconds':60,'retries':0}}
        self.save()

    def tearDown(self): self.temp.cleanup()
    def save(self):
        for name, rows in [('cases.jsonl',self.cases),('refs.jsonl',self.refs)]:
            (self.root / name).write_text(''.join(json.dumps(x)+'\n' for x in rows))
        (self.root / 'card.json').write_text(json.dumps(self.card))
    def prep(self, variant='baseline', reps=1):
        self.save(); return runner.prepare(self.root / 'card.json',variant,'val',reps)
    def run_variant(self, variant='baseline', **kwargs): return runner.run(self.prep(variant),self.flow,**kwargs)
    def complete(self):
        self.assertEqual(self.run_variant()['status'],'complete')
        self.assertEqual(self.run_variant('v1')['status'],'complete')
    def manifest(self, variant='baseline'): return common.read_json(self.flow / variant / 'manifest.json')
    def test_plan_has_no_execution_or_results(self):
        result = subprocess.run([sys.executable,str(EVAL/'scripts/run_eval.py'),'--card',str(self.root/'card.json'),
                                 '--flow',str(self.flow),'--variant','baseline','--split','val'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'],'plan')
        self.assertFalse(self.flow.exists()); self.assertFalse((self.root/'calls.jsonl').exists())
    def test_application_grading_identity_and_resume(self):
        self.complete()
        before = (self.root/'calls.jsonl').read_bytes()
        self.assertEqual(self.run_variant('v1',resume=True)['attempts'],2)
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)
        result = comparison.compare(self.flow,'v1','val','quality',1,samples=200)
        self.assertEqual(result['verdict'],'improvement_clears_threshold')
        self.assertTrue(result['identity_verified'])
        self.assertEqual(comparison.assess(self.flow,'v1','val',1,200)['decision'],'gates_passed')
        for call in common.read_jsonl(self.root/'calls.jsonl'):
            self.assertNotIn('expected',str(call)); self.assertNotIn('reference',call)
    def test_unknown_judge_cost_keeps_known_application_spend(self):
        (self.root/'judge.py').write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'grade':{'quality':1}}))\n")
        self.card['grader']={'kind':'command','command':[sys.executable,'judge.py'],'files':['judge.py']}
        result=self.run_variant()
        self.assertAlmostEqual(result['known_cost_usd'],.04); self.assertEqual(result['unknown_cost_attempts'],2)
        data=report_eval.summarize(self.flow)['variants'][0]
        self.assertAlmostEqual(data['known_cost_usd'],.04); self.assertIsNone(data['total_cost_usd'])

    def test_invalid_budget_and_metric_scale_fail_before_calls(self):
        self.card['limits']['max_cost_uds']=1
        with self.assertRaisesRegex(ValueError,'unknown limit'): self.prep()
        del self.card['limits']['max_cost_uds']
        self.card['metrics'][0].update(min=2,max=1)
        with self.assertRaisesRegex(ValueError,'minimum exceeds'): self.prep()
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_original_deadline_survives_resume(self):
        self.cases[0]['input']['action']='retry'; self.card['limits'].update(concurrency=1,max_total_seconds=.1)
        result=self.run_variant(); time.sleep(.11)
        before=len(common.read_jsonl(self.root/'calls.jsonl'))
        result=self.run_variant(resume=True,retry_errors=True)
        self.assertEqual(len(common.read_jsonl(self.root/'calls.jsonl')),before)
        self.assertEqual(result['status'],'incomplete')

    def test_replaced_artifact_root_is_rejected(self):
        directory=self.root/'artifacts'; directory.mkdir(); external=self.root/'external'; external.mkdir()
        directory.rmdir(); directory.symlink_to(external,target_is_directory=True)
        with self.assertRaises(ValueError): common.atomic(directory,'file.txt','bad')
        self.assertFalse((external/'file.txt').exists())

    def test_judge_retry_reuses_the_same_application_output(self):
        (self.root/'judge.py').write_text("import json,sys\nfrom pathlib import Path\np=json.load(sys.stdin)\nm=Path('judge-tried-'+p['output'])\nif not m.exists():\n m.write_text('1'); print(json.dumps({'error':{'kind':'rate_limit','retryable':True},'cost_usd':.01})); sys.exit(1)\nprint(json.dumps({'grade':{'quality':1},'cost_usd':.02}))\n")
        self.card['grader']={'kind':'command','command':[sys.executable,'judge.py'],'files':['judge.py']}
        self.card['limits']['retries']=1
        result=self.run_variant()
        self.assertEqual(result['status'],'complete'); self.assertEqual(result['attempts'],4)
        self.assertEqual(len(common.read_jsonl(self.root/'calls.jsonl')),2)
        self.assertAlmostEqual(result['known_cost_usd'],.10)
        scores=common.read_jsonl(self.flow/'baseline/results.jsonl')
        self.assertTrue(all(r['meta']['reused_application_for_grading'] for r in scores))
        self.assertTrue(all(abs(r['cost_usd']-.05)<1e-8 for r in scores))

    def test_failed_attempt_cost_survives_retry(self):
        self.cases[0]['input']['action']='retry'; self.card['limits']['retries']=1
        result = self.run_variant()
        self.assertEqual(result['status'],'complete'); self.assertEqual(result['attempts'],3)
        self.assertAlmostEqual(result['known_cost_usd'],.05)
        self.assertEqual(result['unknown_cost_attempts'],0)
        self.assertEqual(len(common.read_jsonl(self.flow/'baseline/errors.jsonl')),1)
    def test_timeout_and_output_ceiling(self):
        for action in ('timeout','oversize'):
            with self.subTest(action=action):
                self.flow=self.root/('flow-'+action); self.cases[0]['input']['action']=action
                self.card['limits'].update(timeout_s=.2,max_output_bytes=1000)
                result=self.run_variant()
                self.assertEqual(result['status'],'incomplete')
                errors=common.read_jsonl(self.flow/'baseline/errors.jsonl')
                self.assertIn('timeout' if action=='timeout' else 'output_limit',{x['status'] for x in errors})
    def test_model_substitution_and_truncation_not_scored(self):
        for mode in ('served','truncated'):
            self.flow=self.root/('flow-'+mode)
            self.cases[0]['input']={'text':'apple',**({'served':'other'} if mode=='served' else {'action':'truncated'})}
            result=self.run_variant(); self.assertEqual(result['completed_cases'],1)
    def test_endpoint_scope_substitution_not_scored_and_cost_retained(self):
        identity = {'provider':'fixture','interface':'decisions','model':'mock','service_tier':'standard','region':'global'}
        for variant in self.card['variants'].values(): variant['expected_billing_identity'] = identity
        result = self.run_variant()
        self.assertEqual(result['completed_cases'], 0)
        self.assertAlmostEqual(result['known_cost_usd'], .04)
        self.assertEqual({e['status'] for e in common.read_jsonl(self.flow/'baseline/errors.jsonl')}, {'serving_substitution'})
    def test_required_stage_coverage_rejects_a_plausible_final_answer(self):
        self.card['coverage'] = {'required_stages':['workers','aggregate'],'expected_totals':{'workers':2,'aggregate':2}}
        result = self.run_variant('v1')
        self.assertEqual(result['completed_cases'], 0)
        self.assertEqual({e['status'] for e in common.read_jsonl(self.flow/'v1/errors.jsonl')}, {'coverage_missing'})
        report = {'coverage':{'stages':[{'id':key,'total':2,'coverage':1,'counts':{'succeeded':2},'uncovered':[]} for key in ('workers','aggregate')]}}
        self.assertEqual(runner.stage_coverage(report, self.card['coverage'])['status'], 'measured_complete')
        report['coverage']['stages'][0].update(total=1,counts={'succeeded':1})
        with self.assertRaises(runner.RunError): runner.stage_coverage(report, self.card['coverage'])
        report['coverage']['stages'][0].update(total=2,counts={'succeeded':2})
        report['coverage']['stages'][0]['counts'] = {'succeeded':1,'failed':1}
        with self.assertRaises(runner.RunError): runner.stage_coverage(report, self.card['coverage'])
    def test_failure_budget_survives_retry_and_resume(self):
        self.cases[0]['input']['action']='retry'
        self.card['limits'].update(concurrency=1,retries=1,max_failed_attempts=1)
        result=self.run_variant(); self.assertEqual(result['attempts'],1)
        before=(self.root/'calls.jsonl').read_bytes()
        result=self.run_variant(resume=True,retry_errors=True)
        self.assertEqual(result['attempts'],1); self.assertEqual(result['status'],'incomplete')
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)
        self.assertEqual(self.manifest()['remaining_failed_attempts'],0)
    def test_reconciled_cancelled_attempt_consumes_failure_budget(self):
        self.card['limits'].update(concurrency=1,max_failed_attempts=1)
        self.run_variant(); directory=self.flow/'baseline'
        rows=common.read_jsonl(directory/'results.jsonl'); attempt=rows[0]['attempt_id']
        common.atomic(directory,'results.jsonl',''.join(common.canonical(r)+'\n' for r in rows if r['attempt_id']!=attempt))
        events=[e for e in common.read_jsonl(directory/'attempts.jsonl') if not (e['event']=='finished' and e['attempt_id']==attempt)]
        common.atomic(directory,'attempts.jsonl',''.join(common.canonical(e)+'\n' for e in events))
        reconcile_run.reconcile(directory,[{'attempt_id':attempt,'resolution':'abandoned','cost_usd':.02,'evidence':'fixture cancellation externally reconciled'}],True)
        before=(self.root/'calls.jsonl').read_bytes()
        result=self.run_variant(resume=True,retry_errors=True)
        self.assertEqual(result['attempts'],2); self.assertEqual(result['status'],'incomplete')
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)
    def test_result_transplant_rejected_even_after_rehash(self):
        self.complete(); directory=self.flow/'v1'
        rows=common.read_jsonl(directory/'results.jsonl')
        rows[0]['result_identity']['treatment_hash']=self.manifest()['treatment_hash']
        common.atomic(directory,'results.jsonl',''.join(common.canonical(r)+'\n' for r in rows))
        manifest=common.read_json(directory/'manifest.json'); manifest['results_sha256']=common.sha(common.read_bytes(directory/'results.jsonl'))
        common.write_json(directory,'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'result identity'): comparison.compare(self.flow,'v1','val','quality',1,samples=200)
    def test_cost_budget_stops_unknown_spend(self):
        self.cases[0]['input']['action']='unknown_cost'
        self.card['limits'].update(concurrency=1,max_cost_usd=.1,reservation_usd_per_attempt=.04)
        result=self.run_variant(); self.assertEqual(result['attempts'],1); self.assertEqual(result['unknown_cost_attempts'],1)
        with self.assertRaisesRegex(ValueError,'unknown historical cost'):
            self.run_variant(resume=True,retry_errors=True)
    def test_attempt_budget_is_not_reset_on_resume(self):
        self.card['limits'].update(max_attempts=2,retries=1,concurrency=1)
        self.cases[0]['input']['action']='retry'
        self.assertEqual(self.run_variant()['attempts'],2)
        result=self.run_variant(resume=True,retry_errors=True)
        self.assertEqual(result['attempts'],2); self.assertEqual(result['status'],'incomplete')
    def test_changed_target_cannot_resume(self):
        self.run_variant(); (self.root/'app.py').write_text(APP+'\n# changed\n')
        with self.assertRaisesRegex(ValueError,'comparison_hash|treatment_hash'): self.run_variant(resume=True)
    def test_control_drift_detected_before_success(self):
        self.cases[0]['input']['action']='drift'; self.card['limits']['concurrency']=1
        result=self.run_variant(); self.assertEqual(result['completed_cases'],0)
        self.assertEqual(common.read_jsonl(self.flow/'baseline/errors.jsonl')[0]['status'],'file_drift')
    def test_results_and_attempt_journal_tampering_rejected(self):
        self.run_variant()
        journal=self.flow/'baseline/attempts.jsonl'; old=journal.read_bytes(); journal.write_bytes(old+b'\n')
        with self.assertRaisesRegex(ValueError,'journal changed'): self.run_variant(resume=True)
        journal.write_bytes(old)
        path=self.flow/'baseline/results.jsonl'; path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'results changed'): self.run_variant(resume=True)
    def test_frozen_baseline_cannot_be_replaced(self):
        self.run_variant(); (self.flow/'baseline/frozen-outputs.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'baseline reference'): self.run_variant('v1')
    def test_duplicate_and_normalized_ids_rejected(self):
        for value in ('a','A','Ａ'):
            self.cases[1]['id']=value
            with self.assertRaisesRegex(ValueError,'collision'): self.prep()
    def test_references_do_not_belong_in_public_input_contract(self):
        self.cases[0]['expected']='APPLE'
        with self.assertRaisesRegex(ValueError,'references stay separate'): self.prep()
    def test_related_cases_cannot_cross_splits(self):
        self.cases[0]['group']=self.cases[1]['group']='document-1'
        self.card['splits']={'train':['a'],'val':['b'],'test':[]}
        with self.assertRaisesRegex(ValueError,'group crosses'): self.prep()
    def test_undeclared_config_changes_rejected(self):
        self.card['variants']['v1']['config']['retriever']='different'
        with self.assertRaisesRegex(ValueError,'undeclared fixed'): self.prep()
    def test_comparison_rejects_dataset_or_grader_drift(self):
        self.complete()
        path=self.flow/'v1/manifest.json'; original=common.read_json(path)
        for field in ('dataset','grader_version','fixed_config','runner'):
            m=copy.deepcopy(original); m['comparison_identity'][field]='changed'
            m['comparison_hash']=common.sha(m['comparison_identity']); path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'incompatible experiments'): comparison.compare(self.flow,'v1','val','quality',1)
        path.write_text(json.dumps(original))
    def test_comparison_rejects_result_edit_and_wrong_population(self):
        self.complete()
        with self.assertRaisesRegex(ValueError,'population'): comparison.compare(self.flow,'v1','val','quality',2)
        path=self.flow/'v1/results.jsonl'; path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'result bytes'): comparison.compare(self.flow,'v1','val','quality',1)
    def test_related_cases_are_one_independent_unit(self):
        self.cases[0]['group']=self.cases[1]['group']='document'
        self.complete()
        self.assertEqual(comparison.compare(self.flow,'v1','val','quality',1)['verdict'],'insufficient_independent_cases')
    def test_legacy_mode_cannot_claim_improvement(self):
        self.complete(); (self.flow/'baseline/manifest.json').unlink()
        with self.assertRaises(FileNotFoundError): comparison.compare(self.flow,'v1','val','quality',1)
        self.assertEqual(comparison.compare(self.flow,'v1','val','quality',1,allow_legacy=True)['verdict'],'exploratory_unverified')
    def test_symlink_and_hardlink_artifacts_rejected(self):
        external=self.root/'outside'; external.write_text('private')
        self.run_variant()
        (self.flow/'baseline/results.jsonl').unlink(); (self.flow/'baseline/results.jsonl').symlink_to(external)
        with self.assertRaises(ValueError): self.run_variant(resume=True)
        with self.assertRaises(ValueError): common.read_bytes(self.flow/'baseline/results.jsonl')
        (self.flow/'baseline/results.jsonl').unlink(); os.link(external,self.flow/'link')
        with self.assertRaises(ValueError): common.read_bytes(self.flow/'link')
        self.assertEqual(external.read_text(),'private')
    def test_path_traversal_and_linked_parent_rejected(self):
        self.flow.mkdir(); (self.flow/'linked').symlink_to(self.root,target_is_directory=True)
        for path in ('../outside','/tmp/outside','linked/outside'):
            with self.assertRaises(ValueError): common.atomic(self.flow,path,'bad')
    def test_null_is_not_missing_and_typed_values_differ(self):
        grade=lambda out,expected: runner.grade_builtin('json_fields',out,expected,{},self.root,'q')['grade']['q']
        self.assertEqual(grade({}, {'x':None}),0); self.assertEqual(grade({'x':None},{'x':None}),1)
        self.assertEqual(grade({'x':True},{'x':1}),0)
    def test_artifact_state_and_unexpected_files_graded(self):
        self.cases[0]['input']['action']=self.cases[1]['input']['action']='artifact'
        self.cases[1]['input']['extra']=True; self.card['grader']={'kind':'artifact_checks'}
        for ref in self.refs: ref['expected']={'files':{'answer.txt':'correct'},'allowed_files':['answer.txt']}
        self.run_variant()
        scores={r['prompt_id']:r['grade']['quality'] for r in common.read_jsonl(self.flow/'baseline/results.jsonl')}
        self.assertEqual(scores,{'a':1,'b':0})
    def test_grader_failure_keeps_application_and_judge_cost(self):
        (self.root/'judge.py').write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'error':{'kind':'judge_failed'},'cost_usd':.03}))\n")
        self.card['grader']={'kind':'command','command':[sys.executable,'judge.py'],'files':['judge.py']}
        result=self.run_variant(); self.assertEqual(result['status'],'incomplete')
        self.assertAlmostEqual(result['known_cost_usd'],.10)
        self.assertEqual(result['unknown_cost_attempts'],0)
    def test_negative_cost_does_not_crash_or_score(self):
        self.cases[0]['input']['action']='bad_cost'
        self.assertEqual(self.run_variant()['status'],'incomplete')
    def test_predeclared_guardrail_can_veto_objective(self):
        (self.root/'judge.py').write_text("import json,sys\np=json.load(sys.stdin)\nq=int(p['output']==p['reference'])\nprint(json.dumps({'grade':{'quality':q,'safety':1-q},'cost_usd':0}))\n")
        self.card['grader']={'kind':'command','command':[sys.executable,'judge.py'],'files':['judge.py']}
        self.card['metrics'].append({'id':'safety','kind':'binary','better':'higher','role':'guardrail','max_regression':0})
        self.complete()
        result=comparison.assess(self.flow,'v1','val',1,200)
        self.assertEqual(result['decision'],'do_not_promote')
        self.assertEqual(result['metrics'][0]['alpha'],.025)
        self.assertFalse(result['metrics'][1]['gate_passed'])

    def test_full_report_escapes_content_and_accounts_failed_spend(self):
        self.cases[0]['input'].update(action='retry',text='<script>bad</script>')
        self.card['limits']['retries']=1
        self.run_variant()
        result=report_eval.build(self.flow)
        document=Path(result['report']).read_text()
        self.assertIn('&lt;script&gt;',document); self.assertNotIn('<script>bad',document)
        data=common.read_json(self.flow/'report-data.json')['variants'][0]
        self.assertAlmostEqual(data['known_cost_usd'],.05); self.assertEqual(data['failed_attempts'],1)
        self.assertTrue(data['synthetic'])
    def test_final_test_requires_frozen_target(self):
        self.cases.append({'id':'held','input':{'text':'lemon'}}); self.refs.append({'id':'held','expected':'LEMON'})
        self.card['splits']['test']=['held']; self.complete()
        with self.assertRaisesRegex(ValueError,'requires --selection'):
            runner.prepare(self.root/'card.json','v1','test',1)
        certificate=self.root/'selection.json'
        seal_selection.seal(self.flow,'v1',certificate,'Synthetic validation selected the uppercase treatment')
        prepared=runner.prepare(self.root/'card.json','v1','test',1,certificate)
        self.assertIn('selection_certificate_hash',prepared['manifest'])
        self.card['variants']['v1']['config']['uppercase']=False; self.save()
        with self.assertRaisesRegex(ValueError,'target was not frozen'):
            runner.prepare(self.root/'card.json','v1','test',1,certificate)
    def test_interrupted_recorded_success_can_be_reconciled_without_reexecution(self):
        self.run_variant(); directory=self.flow/'baseline'
        rows=common.read_jsonl(directory/'results.jsonl'); attempt=rows[0]['attempt_id']
        events=[e for e in common.read_jsonl(directory/'attempts.jsonl') if not (e['event']=='finished' and e['attempt_id']==attempt)]
        common.atomic(directory,'attempts.jsonl',''.join(common.canonical(e)+'\n' for e in events))
        with self.assertRaisesRegex(ValueError,'journal changed'): self.run_variant(resume=True)
        resolutions=[{'attempt_id':attempt,'resolution':'recorded_success','cost_usd':rows[0]['cost_usd'],'evidence':'offline crash fixture; complete output/grade/cost were durably recorded'}]
        self.assertEqual(reconcile_run.reconcile(directory,resolutions)['mode'],'plan')
        reconcile_run.reconcile(directory,resolutions,True)
        before=(self.root/'calls.jsonl').read_bytes()
        self.assertEqual(self.run_variant(resume=True)['status'],'complete')
        self.assertEqual(before,(self.root/'calls.jsonl').read_bytes())
    def test_retries_require_idempotency_review(self):
        self.card['runner']['retry_safe']=False; self.card['limits']['retries']=1
        with self.assertRaisesRegex(ValueError,'retry_safe'): self.prep()
    def test_cost_comparison_counts_all_attempts(self):
        self.cases[0]['input']['action']='retry'; self.card['limits']['retries']=1
        self.complete()
        result=comparison.compare(self.flow,'v1','val','cost_usd',1,samples=200)
        self.assertAlmostEqual(result['baseline_mean'],.025)
        self.assertAlmostEqual(result['candidate_mean'],.02)


class BillingCalibrationTests(unittest.TestCase):
    def identity(self, interface='responses', region='global'):
        return {'provider':'fixture','interface':interface,'model':'same-model','service_tier':'standard','region':region}
    def rate_card(self):
        return {'version':'synthetic-v1','effective_date':'2026-10-18','source':'synthetic offline fixture',
                'rates':[{'billing_identity':self.identity(), 'usage_adapter':'text_tokens_v1',
                          'input_per_million':10,'cached_input_per_million':1,'output_per_million':20},
                         {'billing_identity':self.identity('decisions'),'usage_adapter':'input_only_v1','input_per_million':2}]}
    def event(self, interface='responses'):
        return {'billing_identity':self.identity(interface), 'usage_adapter':'input_only_v1' if interface=='decisions' else 'text_tokens_v1',
                'usage':{'input_tokens':1000} if interface=='decisions' else {'input_tokens':1000,'cached_input_tokens':100,'output_tokens':20},
                'all_billable_usage_included':True}
    def test_same_model_on_different_endpoints_never_uses_the_other_rate(self):
        card=self.rate_card(); event=self.event('decisions')
        self.assertAlmostEqual(price_usage.price(event,card)['cost_usd'],.002)
        event['billing_identity']['interface']='unadapted'
        self.assertEqual(price_usage.price(event,card)['status'],'unknown')
        card['rates']=card['rates'][:1]
        self.assertIsNone(price_usage.price(self.event('decisions'),card)['cost_usd'])
    def test_region_tier_context_and_adapter_are_exact(self):
        for field in ('region','service_tier','context_band'):
            event=self.event(); event['billing_identity'][field]='different'
            self.assertEqual(price_usage.price(event,self.rate_card())['status'],'unknown')
        event=self.event(); event['usage_adapter']='units_v1'
        self.assertEqual(price_usage.price(event,self.rate_card())['status'],'unknown')
    def test_duplicate_flat_billing_scope_cannot_contradict_identity(self):
        for field in ('provider','interface','model','service_tier','region','context_band'):
            event=self.event(); event[field]='contradiction'
            with self.assertRaisesRegex(ValueError,'billing_identity'): price_usage.price(event,self.rate_card())
    def test_legacy_card_cannot_silently_price_a_declared_endpoint(self):
        card=self.rate_card(); card['models']={'same-model':card['rates'][0]}
        event={'model':'same-model','interface':'decisions','usage':{'input_tokens':1000,'output_tokens':0,'cached_input_tokens':0}}
        self.assertEqual(price_usage.price(event,card)['status'],'unknown')
    def test_legacy_card_requires_unknown_cost_for_any_explicit_context_band(self):
        card=self.rate_card(); card['models']={'same-model':card['rates'][0]}
        event={'model':'same-model','usage':{'input_tokens':1000,'output_tokens':20,'cached_input_tokens':100},
               'all_billable_usage_included':True}
        legacy=price_usage.price(event,card)
        self.assertEqual(legacy['status'],'estimated_complete')
        self.assertEqual(legacy['identity_status'],'legacy_model_only')
        self.assertAlmostEqual(legacy['cost_usd'],.0095)
        for context_band in ('long_context','unknown','',None):
            scoped={**event,'context_band':context_band}
            with self.subTest(context_band=context_band):
                result=price_usage.price(scoped,card)
                self.assertEqual(result['status'],'unknown'); self.assertIsNone(result['cost_usd'])
                reported=price_usage.price({**scoped,'cost_usd':.02,'cost_source':'provider reconciled receipt'},card)
                self.assertEqual(reported['status'],'reported'); self.assertEqual(reported['cost_usd'],.02)
    def test_cache_write_accounting_is_explicit_and_not_double_counted(self):
        card=self.rate_card(); event=self.event(); event['usage']['cache_write_input_tokens']=200
        self.assertEqual(price_usage.price(event,card)['status'],'unknown')
        card['rates'][0].update(cache_write_accounting='input_subset',cache_write_input_per_million=12)
        result=price_usage.price(event,card)
        self.assertAlmostEqual(result['components']['uncached_input'],.007)
        self.assertAlmostEqual(result['components']['cache_write_input'],.0024)
        card['rates'][0]['cache_write_accounting']='separate'
        self.assertAlmostEqual(price_usage.price(event,card)['components']['uncached_input'],.009)
        card['rates'][0]['cache_write_accounting']='input_subset'; event['usage']['cache_write_input_tokens']=1000
        with self.assertRaises(ValueError): price_usage.price(event,card)
    def test_input_only_usage_rejects_text_fields_and_unpriced_units(self):
        card=self.rate_card(); event=self.event('decisions'); event['usage']['output_tokens']=0
        self.assertEqual(price_usage.price(event,card)['status'],'unknown')
        del event['usage']['output_tokens']; event['usage']['units']={'tool_calls':2}
        self.assertEqual(price_usage.price(event,card)['status'],'unknown')
        card['rates'][1]['unit_rates']={'tool_calls':{'per':1,'usd':.01}}
        self.assertAlmostEqual(price_usage.price(event,card)['cost_usd'],.022)
    def test_unadapted_native_fields_never_look_free(self):
        event=self.event(); event['usage']['audio_tokens']=20
        self.assertEqual(price_usage.price(event,self.rate_card())['status'],'unknown')
    def test_conflicting_cache_or_reasoning_normalizations_are_rejected(self):
        event=self.event(); event['usage']['input_tokens_details']={'cached_tokens':99}
        with self.assertRaisesRegex(ValueError,'conflicting'): price_usage.price(event,self.rate_card())
        event=self.event(); event['usage'].update(reasoning_tokens=10,output_tokens_details={'reasoning_tokens':11})
        with self.assertRaisesRegex(ValueError,'conflicting'): price_usage.price(event,self.rate_card())
        event=self.event(); event['usage']['input_tokens_details']={'audio_tokens':20}
        self.assertEqual(price_usage.price(event,self.rate_card())['status'],'unknown')
    def labels(self, dataset='fixture-1', judge='judge-1'):
        identity={'dataset_version':dataset,'grader_version':judge,'rubric_sha256':'fixture-rubric','judge_model':judge}
        return [{'id':'positive','human':1,'grade':1,'evaluation_identity':identity},
                {'id':'negative-a','human':0,'grade':1,'evaluation_identity':identity},
                {'id':'negative-b','human':0,'grade':0,'evaluation_identity':identity}]
    def test_false_positives_and_base_rates_are_visible(self):
        result=calibrate_grader.calibrate(self.labels(),.01)
        self.assertEqual(result['false_positive_rate'],.5)
        self.assertAlmostEqual(result['population_adjusted_precision'],.01/(.01+.5*.99))
        self.assertEqual(result['measurement_status']['order_bias'],'unmeasured')
        self.assertFalse(result['ready_for_review'])
    def test_missing_negative_controls_cannot_pass_or_produce_zero_drift(self):
        rows=self.labels()[:1]; result=calibrate_grader.calibrate(rows)
        self.assertIsNone(result['false_positive_rate']); self.assertFalse(result['ready_for_review'])
        self.assertEqual(calibrate_grader.drift(rows,rows)['status'],'unmeasured')
    def test_paired_judges_require_matching_cases_rubric_and_human_labels(self):
        baseline=self.labels(); candidate=self.labels(judge='judge-2'); candidate[1]['grade']=0
        result=calibrate_grader.paired(baseline,candidate)
        self.assertEqual((result['improved'],result['regressed']),(1,0))
        with self.assertRaisesRegex(ValueError,'identical'): calibrate_grader.paired(baseline,candidate[:1])
        candidate[0]['evaluation_identity']['rubric_sha256']='changed'
        with self.assertRaises(ValueError): calibrate_grader.paired(baseline,candidate)
    def test_drift_alert_does_not_confuse_judge_change_with_population_change(self):
        old=self.labels(); old[1]['grade']=0
        new=self.labels(dataset='fixture-2')
        self.assertEqual(calibrate_grader.drift(old,new,.1)['status'],'alert')
        with self.assertRaises(ValueError): calibrate_grader.drift(old,self.labels(judge='judge-2'))


class EngineeringKernelTests(unittest.TestCase):
    def test_stream_requires_terminal_and_preserves_failure_usage(self):
        partial=[{'type':'response.output_text.delta','delta':'looks finished'}]
        self.assertFalse(response_contract.terminal_stream(partial)['scorable_transport'])
        final={'id':'r','status':'incomplete','output':[],'usage':{'output_tokens':3},'incomplete_details':{'reason':'max_output_tokens'}}
        result=response_contract.terminal_stream(partial+[{'type':'response.incomplete','response':final}])
        self.assertEqual(result['usage'],{'output_tokens':3}); self.assertFalse(result['scorable_transport'])
    def test_malformed_content_is_a_controlled_protocol_error(self):
        with self.assertRaisesRegex(ValueError,'content must be an item array'):
            response_contract.normalize({'status':'completed','output':[{'type':'message','content':'not-an-array'}]})

    def test_response_keeps_phase_opaque_items_and_refusal(self):
        output=[{'type':'reasoning','encrypted_content':'opaque'}, {'type':'message','phase':'final_answer','content':[{'type':'refusal','refusal':'declined'}]}]
        result=response_contract.normalize({'status':'completed','output':output})
        self.assertEqual(result['output_items'],output); self.assertEqual(result['refusals'],['declined'])
        self.assertTrue(result['scorable_transport']); self.assertIsNone(result['usage'])
    def test_batch_results_match_by_id_and_expose_missing(self):
        result=response_contract.match_batch(['a','b','c'],[{'custom_id':'b','error':{'code':'bad'}},{'custom_id':'a','response':{'status_code':200}}])
        self.assertEqual(result['missing'],['c']); self.assertEqual(result['errors'],['b']); self.assertEqual(result['ordered'][0]['custom_id'],'a')
        with self.assertRaises(ValueError): response_contract.match_batch(['a'],[{'custom_id':'a'},{'custom_id':'a'}])

    def test_usage_subsets_are_not_double_counted(self):
        card={'version':'fixture','effective_date':'2026-09-30','source':'synthetic rate fixture',
              'models':{'mock':{'input_per_million':10,'cached_input_per_million':1,'output_per_million':20}}}
        event={'model':'mock','usage':{'input_tokens':1000,'cached_input_tokens':900,'output_tokens':100,'reasoning_tokens':80},'all_billable_usage_included':True}
        priced=price_usage.profile([event],card)
        self.assertAlmostEqual(priced['total_cost_usd'],.0039)
        event['usage']['reasoning_tokens']=101
        with self.assertRaises(ValueError): price_usage.price(event,card)
    def test_unknown_and_partial_cost_cannot_look_free(self):
        card={'version':'v','effective_date':'2026-09-30','source':'synthetic','models':{'m':{'input_per_million':1,'cached_input_per_million':1,'output_per_million':1}}}
        result=price_usage.profile([{'model':'other','usage':{}},{'model':'m','usage':{'input_tokens':1,'cached_input_tokens':0,'output_tokens':1}}],card)
        self.assertIsNone(result['total_cost_usd']); self.assertEqual(result['unknown_events'],1); self.assertEqual(result['partial_events'],1)
    def test_grader_calibration_flags_false_positives_and_order_bias(self):
        result=calibrate_grader.calibrate([{'id':'a','human':0,'grade':1,'swapped_grade':1}, {'id':'b','human':1,'grade':1}, {'id':'b','rep':1,'human':1,'grade':0}])
        self.assertEqual(result['confusion'],{'tp':1,'tn':0,'fp':1,'fn':1})
        self.assertEqual(result['unstable_cases'],['b']); self.assertEqual(result['order_inconsistency_rate'],1)
        self.assertFalse(result['ready_for_review'])
    def trace(self):
        first={'state_owner':'client','request':{'input':[{'role':'user','content':'hi'}]},
               'response':{'id':'r1','status':'completed','output':[{'role':'assistant','phase':'commentary','content':'working'}, {'type':'function_call','call_id':'c1','name':'read','arguments':'{}'}]}}
        second={'state_owner':'client','terminal':True,'request':{'input':copy.deepcopy(first['request']['input']+first['response']['output'])+[{'type':'function_call_output','call_id':'c1','output':'ok'}]},
                'response':{'id':'r2','status':'completed','output':[{'role':'assistant','phase':'final_answer','content':'done'}]}}
        return [first,second]
    def test_context_preserves_phase_and_tool_correspondence(self):
        turns=self.trace(); self.assertEqual(context_audit.audit(turns)['errors'],0)
        del turns[1]['request']['input'][1]['phase']
        report=context_audit.audit(turns)
        self.assertIn('history_drift',{x['code'] for x in report['findings']})
        self.assertNotIn('working',json.dumps(report))
    def test_mixed_owners_and_orphan_results_are_detected(self):
        turns=self.trace(); turns[1]['request']['previous_response_id']='r1'; turns[1]['request']['input'][-1]['call_id']='wrong'
        codes={x['code'] for x in context_audit.audit(turns)['findings']}
        self.assertIn('mixed_state_owners',codes); self.assertIn('orphan_tool_result',codes); self.assertIn('unresolved_tool_calls',codes)
    def test_compaction_is_opaque_and_hash_verified(self):
        turns=self.trace(); item={'type':'compaction','encrypted_content':'opaque-not-readable'}
        turns[1].update(compaction_boundary=True,expected_compaction_hash=context_audit.digest(item),terminal=False)
        turns[1]['request']['input']=[copy.deepcopy(item)]
        self.assertEqual(context_audit.audit(turns)['errors'],0)
        turns[1]['request']['input'][0]['encrypted_content']='changed'
        self.assertIn('changed_compaction',{x['code'] for x in context_audit.audit(turns)['findings']})
    def test_lifecycle_replay_cancel_and_memory_boundaries(self):
        def e(i,kind,**extra): return {'id':str(i),'task_id':'task','tenant_id':'tenant','kind':kind,**extra}
        start=e(1,'task_started')
        events=[start,copy.deepcopy(start),e(2,'cancel_requested'),e(3,'effect_started',idempotency_key='write'),e(4,'memory_read',memory_tenant_id='other'),e(5,'task_completed')]
        result=lifecycle_audit.audit(events); codes={x['code'] for x in result['findings']}
        self.assertEqual(result['duplicate_deliveries'],1)
        self.assertTrue({'effect_after_cancel','memory_tenant_mismatch','completed_with_unknown_effect'}<=codes)
        self.assertEqual(len(result['unresolved_effects']),1)
    def test_inventory_returns_locations_not_secret_contents(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name); (root/'app.py').write_text('system_prompt = "private words"\nmodel = "chosen"\n')
            (root/'secrets.json').write_text('{"instructions":"SECRET"}')
            result=prompt_inventory.inventory(root,['.'])
            self.assertEqual(result['surfaces'][0]['path'],'app.py')
            self.assertNotIn('private words',json.dumps(result)); self.assertNotIn('SECRET',json.dumps(result))
            self.assertEqual(result['skipped'][0]['reason'],'credential-like filename')
    def test_durable_effect_deduplication_conflict_and_reconciliation(self):
        with tempfile.TemporaryDirectory() as name:
            ledger=tool_loop.EffectLedger(str(Path(name)/'effects.sqlite')); calls=[]
            try:
                value=ledger.perform('tenant','key',{'amount':1},lambda key:calls.append(key) or {'ok':True})
                self.assertEqual(ledger.perform('tenant','key',{'amount':1},lambda key:self.fail('duplicate effect')),value)
                self.assertEqual(calls,['key'])
                with self.assertRaises(ValueError): ledger.perform('tenant','key',{'amount':2},lambda key:None)
                with self.assertRaises(TimeoutError): ledger.perform('tenant','pending',{},lambda key:(_ for _ in ()).throw(TimeoutError()))
                with self.assertRaises(tool_loop.ReconciliationRequired): ledger.perform('tenant','pending',{},lambda key:None)
                ledger.reconcile('tenant','pending',{'ok':True},'remote operation lookup confirmed success')
                self.assertEqual(ledger.perform('tenant','pending',{},lambda key:self.fail()),{'ok':True})
            finally: ledger.close()
    def test_tool_loop_authorization_budget_and_full_items(self):
        with tempfile.TemporaryDirectory() as name:
            ledger=tool_loop.EffectLedger(str(Path(name)/'effects.sqlite')); requests=[]; effects=[]
            first={'status':'completed','output':[{'type':'reasoning','encrypted_content':'opaque'}, {'type':'function_call','name':'write','call_id':'1','arguments':'{"value":2}'}]}
            def model(request):
                requests.append(copy.deepcopy(request))
                return first if len(requests)==1 else {'status':'completed','output':[{'type':'message','phase':'final_answer','content':'done'}]}
            def validate(args):
                if set(args)!={'value'} or type(args['value']) is not int: raise ValueError('bad schema')
            tools={'write':{'schema':{'type':'function','name':'write'},'validate':validate,'side_effect':True,'handler':lambda args,key:effects.append(args) or {'ok':True}}}
            try:
                result=tool_loop.run_loop(model,[],tools,'tenant','task',ledger,lambda *args:None)
                self.assertEqual(result['status'],'completed'); self.assertEqual(len(effects),1)
                self.assertEqual(requests[1]['input'][0],first['output'][0])
                with self.assertRaises(PermissionError): tool_loop.run_loop(lambda r:first,[],tools,'tenant','denied',ledger,lambda *args:(_ for _ in ()).throw(PermissionError()))
                with self.assertRaises(RuntimeError): tool_loop.run_loop(lambda r:first,[],tools,'tenant','budget',ledger,lambda *args:None,max_tool_calls=0)
                self.assertEqual(len(effects),1)
            finally: ledger.close()

if __name__ == '__main__': unittest.main()
