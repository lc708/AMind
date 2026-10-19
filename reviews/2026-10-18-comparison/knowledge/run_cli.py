#!/usr/bin/env python3
"""Execute the preregistered public CLI commands; do not alter case definitions."""
import concurrent.futures,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent

def run(item):
 side,c,n,args=item
 skill=ROOT/'.codex-tmp/contrast-2026-10-18'/side/'skills/amind'
 argv=[sys.executable,str(skill/'scripts/query.py'),*args]
 started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='amind-contrast-') as cwd:
  p=subprocess.run(argv,cwd=cwd,text=True,capture_output=True)
 return {'side':side,'case_id':c,'command_index':n,'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'duration_s':round(time.monotonic()-started,4)}

def main():
 frozen=json.loads((OUT/'preregistration.json').read_text())
 for name,digest in frozen['files'].items():
  if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('preregistered file changed: '+name)
 cases=[json.loads(l) for l in (OUT/'cases.jsonl').read_text().splitlines()]
 jobs=[(side,c['id'],n,args) for side in ['old','new'] for c in cases for n,args in enumerate(c['commands'])]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
  results=list(executor.map(run,jobs))
 (OUT/'raw-cli.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in results))
 print(json.dumps({'runs':len(results),'exitcodes':{side:{str(k):sum(r['side']==side and r['returncode']==k for r in results) for k in [0,1,2]} for side in ['old','new']}},ensure_ascii=False))
if __name__=='__main__':main()
