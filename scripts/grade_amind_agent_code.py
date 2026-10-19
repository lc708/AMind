#!/usr/bin/env python3
"""Execute reserved generated programs against frozen external probes, offline."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reviews/2026-10-18-comparison'


def strict_equal(actual,expected):
    if isinstance(expected,bool) or expected is None:return type(actual) is type(expected) and actual==expected
    if isinstance(expected,(int,float)):return not isinstance(actual,bool) and isinstance(actual,(int,float)) and abs(actual-expected)<1e-9
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(strict_equal(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(strict_equal(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def main():
    probes=json.loads((OUT/'confirmation-code-probes.json').read_text())
    fingerprint=json.loads((OUT/'confirmation-code-probes-fingerprint.json').read_text())['sha256']
    assert hashlib.sha256((OUT/'confirmation-code-probes.json').read_bytes()).hexdigest()==fingerprint
    plan=json.loads((OUT/'agent-confirmation-plan.json').read_text());rows=[]
    for run in plan['runs']:
        if run['case_id'] not in probes:continue
        capture=OUT/'agent-runs'/run['run_id']/'capture.json'
        if not capture.exists():continue
        workspace=Path(run['workspace']);name='solution.py' if run['case_id']=='C-G' else 'audit.py';program=workspace/'output'/name
        result={'run_id':run['run_id'],'case_id':run['case_id'],'arm':run['arm'],'artifact_present':program.is_file(),'probes':[]}
        if program.is_file():
            result['program_sha256']=hashlib.sha256(program.read_bytes()).hexdigest()
            policy=Path(plan['root'])/'control'/(run['run_id']+'.sb')
            offline=policy.read_text()+'\n(deny network*)\n'
            offline_path=Path(plan['root'])/'control'/(run['run_id']+'-offline-grade.sb');offline_path.write_text(offline)
            for probe in probes[run['case_id']]:
                cmd=['/usr/bin/sandbox-exec','-f',str(offline_path),'/usr/bin/python3','-B',str(program)]
                try:
                    p=subprocess.run(cmd,input=json.dumps(probe['input']),text=True,capture_output=True,cwd=workspace,timeout=4)
                    try:answer=json.loads(p.stdout)
                    except ValueError:answer=None
                    passed=p.returncode==0 and isinstance(answer,dict) and all(k in answer and strict_equal(answer[k],v) for k,v in probe['expected'].items())
                    row={'id':probe['id'],'pass':passed,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'expected':probe['expected']}
                except subprocess.TimeoutExpired:
                    row={'id':probe['id'],'pass':False,'error':'timeout','expected':probe['expected']}
                result['probes'].append(row)
        result['score']=sum(p['pass'] for p in result['probes']);result['max_score']=len(probes[run['case_id']]);rows.append(result)
    output={'source_probe_sha256':fingerprint,'grading':'Actual generated programs; Seatbelt-protected references and siblings, OS network denied; 4s per probe',
            'independence':'Probe variants cluster into two implementation tasks, not fifteen independent tasks','rows':rows}
    (OUT/'confirmation-code-grades.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='probes'} for r in rows],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
