"""Post-diagnostic review validation, not part of the frozen 22-contract score."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=HERE.parent/'runs/repaired_new/E14/flow'

def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def lines(p,value):p.write_text(''.join(json.dumps(x)+'\n' for x in value))
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

results=[]
for arm,script in [('frozen_new',ROOT/'.codex-tmp/contrast-2026-10-18/new/skills/eval-improve/scripts/report_eval.py'),('final_repair',ROOT/'skills/eval-improve/scripts/report_eval.py')]:
 for scene in ('wrong-directory-variant','duplicate-finish','duplicate-result','duplicate-open-start','mismatched-finish','clean','legacy-no-journal'):
  dest=HERE/'runs'/arm/scene
  if dest.exists():raise ValueError('Refuse to overwrite evidence '+str(dest))
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(SOURCE,dest)
  for filename in ('report-data.json','report-full.html'):
   if (dest/filename).exists():(dest/filename).unlink()
  v=dest/'baseline'
  transform={}
  if scene=='wrong-directory-variant':
   shutil.rmtree(v);shutil.copytree(dest/'v1',v);transform={'copied':'v1 directory into baseline, no artifact hash changed'}
  elif scene=='legacy-no-journal':
   (v/'attempts.jsonl').unlink();(v/'manifest.json').unlink();transform={'removed':'manifest and attempt journal; descriptive legacy costs remain on result rows'}
  elif scene!='clean':
   kind='results' if scene=='duplicate-result' else 'attempts';path=v/(kind+'.jsonl');data=rows(path)
   if scene=='duplicate-finish':data.append(next(x for x in data if x.get('event')=='finished'))
   elif scene=='duplicate-result':data.append(data[0])
   elif scene=='duplicate-open-start':
    data=[x for x in data if not (x.get('event')=='finished' and x['attempt_id']==1)];data.append(next(x for x in data if x.get('event')=='started' and x['attempt_id']==1))
   elif scene=='mismatched-finish':next(x for x in data if x.get('event')=='finished')['prompt_id']='a-different-case'
   lines(path,data);manifest=json.loads((v/'manifest.json').read_text());manifest[kind+'_sha256']=sha(path);save(v/'manifest.json',manifest);transform={'ledger':kind,'operation':scene,'byte_hash_updated':True}
  command=[sys.executable,str(script),str(dest)]
  p=subprocess.run(command,capture_output=True,text=True,env={'PYTHONDONTWRITEBYTECODE':'1'},timeout=20)
  report=json.loads((dest/'report-data.json').read_text()) if (dest/'report-data.json').exists() else None
  baseline=next((x for x in report['variants'] if x['variant']=='baseline'),None) if report else None
  case={'arm':arm,'scenario':scene,'source':'registered real CLI flow E14 copied verbatim before explicit transform','transform':transform,'command':command,'script_sha256':sha(script),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'baseline_summary':baseline,'evidence_use':'post-diagnostic validation; no untouched holdout claim'}
  results.append(case);save(dest/'review-command.json',case)
save(HERE/'results.json',{'results':results,'frozen_score_unchanged':True})
print(json.dumps([{'arm':r['arm'],'scenario':r['scenario'],'returncode':r['returncode'],'summary':r['baseline_summary']} for r in results],ensure_ascii=False,indent=2))
