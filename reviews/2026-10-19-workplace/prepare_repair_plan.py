#!/usr/bin/env python3
"""Reserve validation calls: fresh frozen starter, selected repaired skills, no retry."""
import argparse,hashlib,importlib.util,json,shutil
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];TEMP=ROOT/'.codex-tmp/workplace-2026-10-19'
def read(p):return json.loads(p.read_text())
def main(ids):
 protocol=read(OUT/'protocol.json');mainplan=read(OUT/'main-plan.json');tasks={x['id']:x for x in protocol['tasks']}
 assert len(ids)<=2 and len(ids)==len(set(ids)) and all(x in tasks for x in ids)
 assert all((OUT/'runs'/x['run_id']/'capture.json').exists() for x in mainplan['runs']),'Finish all main calls before reserved validation'
 dest=OUT/'repair-plan.json';assert not dest.exists()
 spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run_amind_workplace_trials.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 selected=read(OUT/'product-diagnostics/selected-repair.json')
 for name,digest in selected['files'].items():assert m.sha(TEMP/'repaired'/name)==digest,name
 base=Path(mainplan['root']);runs=[]
 for rep in range(3):
  for tid in ids:
   task=tasks[tid];rid=f'W{43+len(runs):03d}';work=base/rid;assert not (work/'skills').exists()
   packages=['amind'] if task['skill']=='amind' else ['amind-engineering','eval-improve']
   for name in packages:shutil.copytree(TEMP/'repaired/skills'/name,work/'skills'/name,ignore=m.IGNORE)
   if task.get('repo'):shutil.copytree(task['repo'],work/'repo',ignore=m.IGNORE)
   (work/'output').mkdir(exist_ok=True);m.write(work/'task.json',{'id':tid,'prompt':task['prompt']})
   runs.append({'run_id':rid,'task_id':tid,'axis':task['axis'],'rep':rep,'arm':'repaired','skill':task['skill'],'workspace':str(work),'skill_files':m.inventory(work/'skills'),'public_tests':m.inventory(work/'repo/tests') if (work/'repo/tests').exists() else {},'starter_files':m.inventory(work/'repo') if (work/'repo').exists() else {},'task_sha256':m.sha(work/'task.json')})
 refs=[{k:x[k] for k in ['run_id','task_id','rep','arm']} for x in mainplan['runs'] if x['task_id'] in ids and x['arm'] in ['current','citation-current']]
 m.write(dest,{'runs':runs,'root':str(base),'profile_name':mainplan['profile_name'],'protocol_sha256':m.sha(OUT/'protocol.json'),'runner_sha256':m.sha(ROOT/'scripts/run_amind_workplace_trials.py'),'repair_selection_sha256':m.sha(OUT/'product-diagnostics/selected-repair.json'),'comparison_reference_runs':refs,'evidence_use':'After-discovery validation on reused task families; no untouched holdout or population proof. Historical current references; no common sampling seed or contemporaneous serving attestation.'})
 print(json.dumps({'reserved_calls':len(runs),'tasks':ids,'baseline_references':len(refs),'model_called':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tasks',nargs='+',required=True);a=p.parse_args();main(a.tasks)
