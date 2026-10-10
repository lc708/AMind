#!/usr/bin/env python3
"""Differential offline probes against the pinned upstream runner's documented hooks.
Synthetic local processes only. This compares selected runner contracts, not model/skill quality.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVAL=ROOT/'skills/eval-improve/scripts'
EXPECTED='8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4'


def invoke(command,cwd):
    p=subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=15)
    return {'exit_code':p.returncode,'stdout':p.stdout[-1800:],'stderr':p.stderr[-1200:]}


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def benchmark(upstream):
    source=(upstream/'shared/evals/report/runner-scaffold.mjs').read_text()
    inventory=json.loads((ROOT/'skills/amind-engineering/references/upstream-capabilities.json').read_text())
    expected=next(e['sha256'] for e in inventory['entries'] if e['path']=='shared/evals/report/runner-scaffold.mjs')
    if hashlib.sha256(source.encode()).hexdigest()!=expected: raise ValueError('upstream source does not match the pinned inventory')
    source=source.replace("throw new Error('TODO: loadCases');","return JSON.parse(readFileSync('cases.json', 'utf8'));")
    source=source.replace("throw new Error('TODO: runCase');", "writeFileSync('calls.jsonl', JSON.stringify({id:input.id})+'\\n', {flag:'a'}); return {output:input.input.text, ...(input.input.missing_model ? {} : {model:ctx.model}), usage:{input_tokens:1, output_tokens:1}, transcript:[{role:'assistant',content:input.input.text}]};")
    source=source.replace("throw new Error('TODO: gradeCase');", "return {grade:{quality:input.input.bad_grade ? 'not-a-score' : 1}};")
    observations=[]
    with tempfile.TemporaryDirectory(prefix='amind-upstream-comparison-') as temp:
        base=Path(temp).resolve()
        for scenario in ('normal_resume','casefold_collision','missing_served_model','invalid_grade'):
            cases=[{'id':'a','input':{'text':'a'}},{'id':'b','input':{'text':'b'}}]
            if scenario=='casefold_collision': cases[1]['id']='A'
            if scenario=='missing_served_model':
                for c in cases: c['input']['missing_model']=True
            if scenario=='invalid_grade':
                for c in cases: c['input']['bad_grade']=True
            upstream_root=base/scenario/'upstream'; upstream_root.mkdir(parents=True)
            (upstream_root/'runner.mjs').write_text(source); (upstream_root/'cases.json').write_text(json.dumps(cases))
            (upstream_root/'flow').mkdir(); (upstream_root/'flow/_state.json').write_text(json.dumps({'metrics':[{'id':'quality','kind':'binary'}],'val_ids':[c['id'] for c in cases],'train_ids':[],'test_ids':[]}))
            command=['node','runner.mjs','--flow','flow','--variant','baseline','--model','mock','--timeout-s','2']
            first=invoke(command+['--approve-harness'],upstream_root)
            old_rows=rows(upstream_root/'flow/baseline/results.jsonl'); before=len(rows(upstream_root/'calls.jsonl'))
            resume=invoke(command,upstream_root) if scenario=='normal_resume' else None
            old={'exit_code':first['exit_code'],'scored_rows':len(old_rows),'statuses':[r.get('status') for r in old_rows],
                 'grades':[r.get('grade') for r in old_rows], 'calls':before}
            if resume: old.update(resume_exit=resume['exit_code'],calls_after_resume=len(rows(upstream_root/'calls.jsonl')))
            new_root=base/scenario/'amind'; new_root.mkdir()
            (new_root/'app.py').write_text("import json,sys\np=json.load(sys.stdin)\ni=p['input']\nwith open('calls.jsonl','a') as f:f.write(json.dumps({'id':p['context']['case_id']})+'\\n')\nprint(json.dumps({'output':i, 'cost_usd':0, **({} if i.get('missing_model') else {'model':'mock'})}))\n")
            (new_root/'judge.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'grade':{'quality':'not-a-score' if p['output'].get('bad_grade') else 1},'cost_usd':0}))\n")
            (new_root/'cases.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in cases))
            card={'schema_version':2,'task':'synthetic differential probe','dataset_version':'1','grader_version':'1','cases':'cases.jsonl',
                  'splits':{'train':[],'val':[c['id'] for c in cases],'test':[]},'metrics':[{'id':'quality','kind':'binary'}],
                  'runner':{'command':[sys.executable,'app.py'],'files':['app.py']},
                  'grader':{'kind':'command','command':[sys.executable,'judge.py'],'files':['judge.py']},
                  'variants':{'baseline':{'files':['app.py'],'config':{},'expected_model':'mock'}},'limits':{'timeout_s':2,'max_total_seconds':60}}
            (new_root/'card.json').write_text(json.dumps(card))
            cmd=[sys.executable,str(EVAL/'run_eval.py'),'--card','card.json','--flow','flow','--variant','baseline','--split','val','--execute']
            result=invoke(cmd,new_root); new_rows=rows(new_root/'flow/baseline/results.jsonl')
            new={'exit_code':result['exit_code'],'scored_rows':len(new_rows),'statuses':[r.get('status') for r in new_rows],
                 'failure_classes':[r.get('status') for r in rows(new_root/'flow/baseline/errors.jsonl')], 'calls':len(rows(new_root/'calls.jsonl'))}
            if scenario=='normal_resume':
                result2=invoke(cmd+['--resume'],new_root); new.update(resume_exit=result2['exit_code'],calls_after_resume=len(rows(new_root/'calls.jsonl')))
            observations.append({'scenario':scenario,'upstream':old,'amind':new})
    return {'upstream_commit':EXPECTED,'upstream_runner_sha256':expected,'fixture':'same two public inputs and synthetic outcomes; only the three documented upstream TODO hooks filled',
            'observations':observations,'limits':'Selected deterministic runner contracts only. No live model, independent agent, eight-language runtime or overall skill superiority claim.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--upstream',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=benchmark(a.upstream);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
