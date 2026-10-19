import json,subprocess,sys,tempfile,unittest
from pathlib import Path
class PublicGatewayTests(unittest.TestCase):
    def call(self,capture):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'capture.json';out=Path(t)/'out.json';source.write_text(json.dumps(capture))
            p=subprocess.run([sys.executable,'-m','gateway','--capture',str(source),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(out.read_text())
    def test_legacy_final(self):
        item={'type':'message','content':[{'type':'output_text','text':'Order received.'}]}
        result=self.call({'mode':'single','events':[{'type':'response.completed','response':{'status':'completed','output':[item]}}]})
        self.assertEqual(result['client']['final_text'],'Order received.')
    def test_partial_capture_is_retained(self):
        events=[{'type':'response.output_text.delta','delta':'Working'}]
        result=self.call({'mode':'single','events':events})
        self.assertEqual(result['archive']['events'],events);self.assertFalse(result['client']['answer_complete'])
    def test_empty_success_has_no_answer(self):
        result=self.call({'mode':'single','events':[{'type':'response.completed','response':{'status':'completed','output':[]}}]})
        self.assertFalse(result['client']['answer_complete'])
if __name__=='__main__':unittest.main()
