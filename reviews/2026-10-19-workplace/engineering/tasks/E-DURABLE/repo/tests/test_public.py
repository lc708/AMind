import json,subprocess,sys,tempfile,unittest
from pathlib import Path
class IntakeTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    def call(self,op,**extra):
        req=self.p/'request.json';req.write_text(json.dumps({'op':op,'tenant':'acme','job':'J1',**extra}))
        p=subprocess.run([sys.executable,'-m','intake','--db',str(self.p/'jobs.db'),'--request',str(req),'--receipts',str(self.p/'receipts.jsonl')],capture_output=True,text=True)
        return p.returncode,json.loads(p.stdout)
    def test_submit_plans(self):
        rc,r=self.call('submit',spec={'items':[{'id':'a'}],'max_attempts':8});self.assertEqual(rc,0);self.assertEqual(r['coverage'],0)
    def test_small_job(self):
        self.call('submit',spec={'items':[{'id':'a'}],'max_attempts':8});rc,r=self.call('work');self.assertEqual(rc,0);self.assertEqual(r['status'],'completed')
    def test_population_required(self):
        rc,r=self.call('submit',spec={'items':[],'max_attempts':8});self.assertEqual(rc,2);self.assertIn('error',r)
if __name__=='__main__':unittest.main()
