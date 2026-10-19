"""Offline reporting regressions through the public application/grader CLI."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/eval-improve/scripts'


class EvalReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='amind-reporting-')
        self.root = Path(self.temp.name).resolve()
        self.flow = self.root / 'flow'
        (self.root/'app.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'output':p['input'],'model':'fixture','cost_usd':.02,'synthetic':True}))\n")
        rows=[{'id':'a','input':'a'},{'id':'b','input':'b'}]
        self.jsonl(self.root/'cases.jsonl',rows)
        self.jsonl(self.root/'refs.jsonl',[{'id':r['id'],'expected':r['input']} for r in rows])
        card={'schema_version':2,'task':'offline report validation','dataset_version':'1','grader_version':'1',
              'cases':'cases.jsonl','references':'refs.jsonl','splits':{'train':[],'val':['a','b'],'test':[]},
              'metrics':[{'id':'quality','kind':'binary','better':'higher','role':'objective','min_improvement':0}],
              'runner':{'command':[sys.executable,'app.py'],'files':['app.py']},'grader':{'kind':'exact'},
              'variants':{'baseline':{'files':['app.py'],'config':{},'expected_model':'fixture'}},
              'limits':{'max_attempts':2,'concurrency':1,'timeout_s':5,'max_total_seconds':60,'retries':0}}
        self.json(self.root/'card.json',card)
        result=self.cli('run_eval.py','--card',self.root/'card.json','--flow',self.flow,
                        '--variant','baseline','--split','val','--execute')
        self.assertEqual(result['status'],'complete')
        self.variant=self.flow/'baseline'

    def tearDown(self):
        self.temp.cleanup()

    def json(self,path,value):
        path.write_text(json.dumps(value)+'\n')

    def jsonl(self,path,rows):
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def readlines(self,path):
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

    def cli(self,script,*args):
        p=subprocess.run([sys.executable,str(SCRIPTS/script),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        return json.loads(p.stdout)

    def rehash(self):
        manifest=json.loads((self.variant/'manifest.json').read_text())
        for kind in ('results','attempts'):
            manifest[kind+'_sha256']=hashlib.sha256((self.variant/(kind+'.jsonl')).read_bytes()).hexdigest()
        self.json(self.variant/'manifest.json',manifest)

    def report(self):
        self.cli('report_eval.py',self.flow)
        data=json.loads((self.flow/'report-data.json').read_text())
        return data['variants'][0],data['details']

    def test_interrupted_attempt_remains_unknown_and_counted_with_finished_cost(self):
        # Reproduce a process exit after attempt 2 started but before its result/finish.
        rows=self.readlines(self.variant/'results.jsonl')
        events=self.readlines(self.variant/'attempts.jsonl')
        self.jsonl(self.variant/'results.jsonl',[r for r in rows if r['attempt_id']!=2])
        self.jsonl(self.variant/'attempts.jsonl',[e for e in events if not (e['event']=='finished' and e['attempt_id']==2)])
        self.rehash()
        result,details=self.report()
        self.assertAlmostEqual(result['known_cost_usd'],.02)
        self.assertIsNone(result['total_cost_usd'])
        self.assertEqual(result['unknown_cost_attempts'],1)
        self.assertEqual(result['attempts'],2)
        self.assertEqual(result['interrupted_attempts'],1)
        self.assertEqual([d['interrupted_attempt']['attempt_id'] for d in details if 'interrupted_attempt' in d],[2])

    def test_all_interrupted_attempts_do_not_look_free(self):
        events=self.readlines(self.variant/'attempts.jsonl')
        self.jsonl(self.variant/'results.jsonl',[])
        self.jsonl(self.variant/'attempts.jsonl',[e for e in events if e['event']=='started'])
        self.rehash()
        result,_=self.report()
        self.assertEqual(result['known_cost_usd'],0)
        self.assertIsNone(result['total_cost_usd'])
        self.assertEqual(result['unknown_cost_attempts'],2)
        self.assertEqual(result['attempts'],2)

    def test_report_rejects_foreign_result_binding_even_with_updated_byte_hash(self):
        rows=self.readlines(self.variant/'results.jsonl')
        rows[0]['result_identity']['treatment_hash']='a-different-treatment'
        self.jsonl(self.variant/'results.jsonl',rows)
        self.rehash()
        result,_=self.report()
        self.assertTrue(result['integrity'].startswith('unverified:'))
        self.assertIn('result identity',result['integrity'])


    def assert_invalid_report(self, fragment):
        p=subprocess.run([sys.executable,str(SCRIPTS/'report_eval.py'),str(self.flow)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2,p.stderr+p.stdout)
        self.assertIn(fragment,json.loads(p.stdout)['error'])
        self.assertFalse((self.flow/'report-data.json').exists())

    def test_copied_baseline_cannot_be_reported_as_candidate(self):
        # Independent direction from the reviewer's candidate-as-baseline probe.
        shutil.copytree(self.variant,self.flow/'v1')
        self.assert_invalid_report('manifest variant differs from its directory')

    def test_duplicate_last_finished_event_is_rejected_after_rehash(self):
        events=self.readlines(self.variant/'attempts.jsonl')
        events.append([e for e in events if e['event']=='finished'][-1])
        self.jsonl(self.variant/'attempts.jsonl',events)
        self.rehash()
        self.assert_invalid_report('duplicate finished attempt ID')

    def test_duplicate_open_start_cannot_inflate_unknown_cost_count(self):
        events=self.readlines(self.variant/'attempts.jsonl')
        events=[e for e in events if not (e['event']=='finished' and e['attempt_id']==2)]
        events.append(next(e for e in events if e['event']=='started' and e['attempt_id']==2))
        self.jsonl(self.variant/'attempts.jsonl',events)
        self.rehash()
        self.assert_invalid_report('duplicate started attempt ID')

    def test_finished_event_must_match_started_case_and_repetition(self):
        events=self.readlines(self.variant/'attempts.jsonl')
        events[-1]['rep']=7
        self.jsonl(self.variant/'attempts.jsonl',events)
        self.rehash()
        self.assert_invalid_report('case/repetition differs from start')

    def test_duplicate_last_result_cannot_exceed_planned_population(self):
        rows=self.readlines(self.variant/'results.jsonl')
        rows.append(rows[-1])
        self.jsonl(self.variant/'results.jsonl',rows)
        self.rehash()
        self.assert_invalid_report('duplicate completed result key')

    def test_legacy_no_journal_report_preserves_descriptive_cost(self):
        (self.variant/'manifest.json').unlink()
        (self.variant/'attempts.jsonl').unlink()
        result,_=self.report()
        self.assertAlmostEqual(result['known_cost_usd'],.04)
        self.assertAlmostEqual(result['total_cost_usd'],.04)
        self.assertTrue(result['integrity'].startswith('unverified:'))
        self.assertIsNone(result['attempts'])

    def test_clean_complete_report_retains_cost_and_verified_export(self):
        result,_=self.report()
        self.assertAlmostEqual(result['total_cost_usd'],.04)
        self.assertEqual(result['unknown_cost_attempts'],0)
        self.assertEqual(result['attempts'],2)
        self.assertEqual(result['interrupted_attempts'],0)
        self.assertTrue(result['integrity'].startswith('hashes match export'))


if __name__=='__main__':
    unittest.main()
