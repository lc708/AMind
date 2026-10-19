#!/usr/bin/env python3
"""Run frozen app graders against portable captured repositories, never import them."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reviews/2026-10-19-workplace'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(plan_file):
    protocol=read(OUT/'protocol.json');assert sha(OUT/'protocol.json')==read(OUT/'protocol-fingerprint.json')['sha256']
    for name,digest in read(OUT/'measurement-files.json').items():assert sha(ROOT/name)==digest,name
    tasks={x['id']:x for x in protocol['tasks']};plan=read(OUT/plan_file)
    spec=importlib.util.spec_from_file_location('workplace_runner',ROOT/'scripts/run_amind_workplace_trials.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    rows=[]
    for run in plan['runs']:
        if run['skill']=='amind':continue
        dest=OUT/'app-grades'/run['run_id'];assert not dest.exists(),'Do not replace grades';dest.mkdir(parents=True)
        captured=read(OUT/'runs'/run['run_id']/'capture.json');meta={k:run[k] for k in ['run_id','task_id','rep','arm']};meta['runtime_status']=captured['status']
        if captured['status']!='captured':
            meta.update(grade_status='runtime_incomplete',score=None,max_score=tasks[run['task_id']]['max_score']);rows.append(meta);(dest/'summary.json').write_text(json.dumps(meta,indent=2)+'\n');continue
        source=OUT/'runs'/run['run_id']/'repo';workspace=Path(run['workspace']);repo=workspace/'grade-repo'
        assert not repo.exists();shutil.copytree(source,repo,ignore=runner.IGNORE)
        policy=runner.make_policy(Path(plan['root']),run['run_id'],grading=True);env=os.environ.copy();env['AMIND_APP_COMMAND_PREFIX_JSON']=json.dumps(['/usr/bin/sandbox-exec','-f',str(policy)]);env['AMIND_GRADER_SCRATCH']=str(workspace/'grade-scratch')
        task=tasks[run['task_id']];command=['python3',task['grader_path'],'--repo',str(repo)]
        p=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True,timeout=180)
        (dest/'stdout.txt').write_text(p.stdout);(dest/'stderr.txt').write_text(p.stderr)
        assert p.returncode==0,('grader runtime failure',run['run_id'],p.stderr)
        result=json.loads(p.stdout);assert 0<=result['score']<=result['max_score']==task['max_score']
        (dest/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        passed=result.get('fatal_pass',result.get('guardrails_passed'))
        meta.update(grade_status='graded',score=result['score'],max_score=result['max_score'],guardrails_passed=passed,probe_passed=result.get('probe_passed'),probe_total=result.get('probe_total'),portable_no_skill_dependency=True,network_denied_during_probes=True)
        (dest/'summary.json').write_text(json.dumps(meta,indent=2)+'\n');rows.append(meta);print(json.dumps(meta),flush=True)
    (OUT/(Path(plan_file).stem+'-application-scores.json')).write_text(json.dumps({'rows':rows,'independent_tasks':4,'repetitions_per_task_arm':3,'note':'Curated domain checks; probes/repetitions are not independent work distributions.'},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',default='main-plan.json');a=p.parse_args();main(a.plan)
