#!/usr/bin/env python3
"""Frozen, offline public-CLI behavioral comparison; no imported skill internals."""
import argparse, copy, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / 'fixtures'
SOURCES = {'old': ROOT/'.codex-tmp/contrast-2026-10-18/old/skills/eval-improve',
           'frozen_new': ROOT/'.codex-tmp/contrast-2026-10-18/new/skills/eval-improve',
           'repaired_new': ROOT/'skills/eval-improve'}
IDENTITY = {'provider':'fixture','interface':'responses','model':'same-model','service_tier':'standard','region':'global'}
TEXT = {'input_per_million':10,'cached_input_per_million':1,'output_per_million':20}
USAGE = {'input_tokens':1000000,'cached_input_tokens':200000,'output_tokens':100000,'reasoning_tokens':30000}
LEGACY = {'version':'synthetic-registered-v1','effective_date':'2026-10-18','source':'synthetic offline challenge, no real provider prices','models':{'same-model':TEXT}}
SCOPED = {**{k:v for k,v in LEGACY.items() if k!='models'}, 'rates':[{'billing_identity':IDENTITY,'usage_adapter':'text_tokens_v1',**TEXT},{'billing_identity':{**IDENTITY,'interface':'decisions'},'usage_adapter':'input_only_v1','input_per_million':2}]}
APP = '''import json,sys\nfrom pathlib import Path\np=json.load(sys.stdin)\ni,c=p['input'],p['context']\nlog=Path(__file__).with_name('calls.jsonl')\nwith log.open('a') as f:f.write(json.dumps({'case':c['case_id'],'input':i})+'\\n')\nif i.get('failure'):\n print(json.dumps({'error':{'kind':'synthetic_service_failure','retryable':True},'cost_usd':.02,'synthetic':True}));sys.exit(1)\nout=i.get('text','ok')\nif c['config'].get('uppercase'):out=out.upper()\nr={'output':out,'model':i.get('served_model','same-model'),'cost_usd':.02,'synthetic':True,'billing_identity':{'provider':'fixture','interface':'responses','model':'same-model','service_tier':i.get('served_tier','standard'),'region':'global'}}\nif 'coverage' in i:r['coverage']=i['coverage']\nprint(json.dumps(r))\n'''

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def lines(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))

def readlines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def labels(conf, dataset='calibration-v1', judge='judge-v1'):
    ident={'dataset_version':dataset,'grader_version':judge,'rubric_sha256':'synthetic-rubric-v1','judge_model':judge}
    result=[]
    for kind,n in conf.items():
        human=1 if kind in ('tp','fn') else 0; grade=1 if kind in ('tp','fp') else 0
        for j in range(n):result.append({'id':f'{kind}-{j}','human':human,'grade':grade,'evaluation_identity':ident})
    return result

def event(**changes):return {'id':'e','model':'same-model','usage':copy.deepcopy(USAGE),'all_billable_usage_included':True,**changes}

def card(inputs, cases=None, **updates):
    rows=cases or [{'id':'a','input':inputs}]
    base={'schema_version':2,'task':'Registered offline behavioral challenge; synthetic local application','dataset_version':'challenge-v1','grader_version':'exact-v1','cases':'cases.jsonl','references':'refs.jsonl','splits':{'train':[],'val':[r['id'] for r in rows],'test':[]},'metrics':[{'id':'quality','kind':'binary','better':'higher','role':'objective','min_improvement':0}],'runner':{'command':[sys.executable,'app.py'],'files':['app.py'],'retry_safe':True},'grader':{'kind':'exact'},'mutable_config':['uppercase'],'variants':{k:{'files':['app.py'],'config':{'uppercase':v},'expected_model':'same-model'} for k,v in [('baseline',False),('v1',True)]},'limits':{'max_attempts':6,'concurrency':1,'timeout_s':3,'max_total_seconds':300,'retries':0}}
    base.update(updates)
    return base,rows

def prepare():
    FIX.mkdir(parents=True,exist_ok=True)
    price={
      'E01':([event()],LEGACY),
      'E02':([event(id='unknown',model='unpriced'),event(id='partial',all_billable_usage_included=False)],LEGACY),
      'E03':([event(billing_identity=IDENTITY,usage_adapter='text_tokens_v1'),event(id='decisions',billing_identity={**IDENTITY,'interface':'decisions'},usage_adapter='input_only_v1',usage={'input_tokens':1000000})],SCOPED),
      'E04':([event(interface='decisions')],LEGACY),
      'E05':([event(usage={**USAGE,'input_tokens_details':{'cached_tokens':200000,'audio_tokens':15000}})],LEGACY),
      'E06':([event(usage={**USAGE,'input_tokens_details':{'cached_tokens':100000}})],LEGACY),
      'E07':([event(billing_identity=IDENTITY,usage_adapter='text_tokens_v1',usage={**USAGE,'cache_write_input_tokens':200000})],{**SCOPED,'rates':[{**SCOPED['rates'][0],'cache_write_accounting':'input_subset','cache_write_input_per_million':12}]})}
    for cid,(events,rates) in price.items():
        lines(FIX/cid/'events.jsonl',events);write(FIX/cid/'rates.json',rates)
    clean=labels({'tp':2,'tn':2,'fp':1,'fn':1})
    for row in clean:row['swapped_grade']=1-row['grade']
    lines(FIX/'E08/labels.jsonl',clean)
    lines(FIX/'E09/labels.jsonl',labels({'tp':2}))
    contradict=labels({'tp':1});contradict.append({**contradict[0],'rep':1,'human':0})
    lines(FIX/'E10/labels.jsonl',contradict)
    lines(FIX/'E11/labels.jsonl',labels({'tp':90,'fn':10,'fp':18,'tn':882}))
    lines(FIX/'E12/reference.jsonl',labels({'tp':10,'fp':2,'tn':98},'prior'))
    lines(FIX/'E12/labels.jsonl',labels({'tp':10,'fp':8,'tn':92},'current'))
    prior=labels({'tp':1,'tn':1,'fp':1,'fn':1})
    candidate=copy.deepcopy(prior)
    for r in candidate:
        r['evaluation_identity'].update(grader_version='judge-v2',judge_model='judge-v2')
        if r['id']=='fp-0':r['grade']=0
        if r['id']=='tn-0':r['grade']=1
    lines(FIX/'E13/reference.jsonl',prior);lines(FIX/'E13/labels.jsonl',candidate)
    for cid in [f'E{i:02}' for i in range(14,23)]:
        inputs={'text':'ok'}
        cases=None
        if cid=='E14':
            cases=[{'id':'a','input':{'text':'apple'}},{'id':'b','input':{'text':'pear'}}]
        if cid=='E15':inputs['served_model']='substituted-model'
        if cid=='E16':inputs['coverage']={'stages':[{'id':'workers','total':2,'coverage':1,'counts':{'succeeded':2},'uncovered':[]},{'id':'aggregate','total':1,'coverage':1,'counts':{'succeeded':1},'uncovered':[]}]}
        if cid=='E17':inputs['served_tier']='flex'
        if cid=='E18':inputs['failure']=True
        c,rows=card(inputs,cases)
        if cid=='E16':c['coverage']={'required_stages':['workers','aggregate'],'expected_totals':{'workers':3,'aggregate':1}}
        if cid=='E17':
            for v in c['variants'].values():v['expected_billing_identity']=IDENTITY
        if cid in ('E18','E22'):c['limits'].update(max_attempts=4,max_failed_attempts=1,retries=1)
        d=FIX/cid;d.mkdir(parents=True,exist_ok=True);(d/'app.py').write_text(APP)
        lines(d/'cases.jsonl',rows);lines(d/'refs.jsonl',[{'id':r['id'],'expected':r['input']['text'].upper() if cid=='E14' else 'ok'} for r in rows]);write(d/'card.json',c)
    freeze={'protocol_sha256':sha(HERE/'protocol.json'),'registered_at':'before any frozen challenge execution','files':{p.relative_to(HERE).as_posix():sha(p) for p in sorted(FIX.rglob('*')) if p.is_file()},'harness_sha256':sha(Path(__file__)),'skill_snapshots':{name:{p.relative_to(src).as_posix():sha(p) for p in sorted(src.rglob('*')) if p.is_file() and '__pycache__' not in p.parts} for name,src in SOURCES.items() if name!='repaired_new'}}
    write(HERE/'freeze.json',freeze);print(json.dumps({'inputs':len(freeze['files']),'protocol_sha256':freeze['protocol_sha256'],'freeze_sha256':sha(HERE/'freeze.json')}))

def approx(a,b):return isinstance(a,(int,float)) and abs(a-b)<1e-8

def invoke(root, tool, args, evidence, label):
    cmd=[sys.executable,str(root/'scripts'/tool),*map(str,args)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=30,cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    write(evidence/(label+'.command.json'),{'argv':cmd,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    try:data=json.loads(p.stdout)
    except ValueError:data={}
    return p.returncode,data

def interrupted(d,evidence):
    """Simulate crash after a real public run's started record; never invent scores."""
    manifest=json.loads((d/'manifest.json').read_text());events=readlines(d/'attempts.jsonl')
    starts=[e for e in events if e['event']=='started'];lines(d/'attempts.jsonl',starts);lines(d/'results.jsonl',[])
    if (d/'errors.jsonl').exists():(d/'errors.jsonl').unlink()
    manifest.update(status='incomplete',completed_cases=0,results_sha256=sha(d/'results.jsonl'),attempts_sha256=sha(d/'attempts.jsonl'))
    write(d/'manifest.json',manifest)
    write(evidence/'interruption-transform.json',{'synthetic_crash_boundary':'after started, before result or finished','removed_finished':len(events)-len(starts),'retained_started':starts,'no_score_fabricated':True})

def run_variant(name):
    source=SOURCES[name];out=HERE/'runs'/name
    if out.exists():raise RuntimeError('Never overwrite prior evidence: '+str(out))
    out.mkdir(parents=True)
    protocol=json.loads((HERE/'protocol.json').read_text()); results=[]
    for challenge in protocol['challenges']:
        cid=challenge['id'];d=out/cid;d.mkdir();fixture=FIX/cid
        shutil.copytree(fixture,d/'input');inp=d/'input'
        evidence=d/'evidence';evidence.mkdir();root=source
        status='fail';detail={};rc=None
        if cid<='E07':
            rc,data=invoke(root,'price_usage.py',['--events',inp/'events.jsonl','--rates',inp/'rates.json'],evidence,'price')
            rows=data.get('rows',[]);total=data.get('total_cost_usd');detail=data
            if cid=='E01':ok=rc==0 and approx(total,10.2) and approx(rows[0]['components']['output_including_reasoning'],2)
            elif cid=='E02':ok=rc==0 and total is None and data.get('unknown_events')==1 and data.get('partial_events')==1 and approx(data.get('known_or_estimated_subtotal_usd'),10.2)
            elif cid=='E03':ok=rc==0 and len(rows)==2 and approx(rows[0].get('cost_usd'),10.2) and approx(rows[1].get('cost_usd'),2)
            elif cid in ('E04','E05'):ok=rc==0 and rows[0].get('status')=='unknown' and total is None
            elif cid=='E06':ok=rc==2 and 'conflicting' in data.get('error','')
            else:ok=rc==0 and approx(total,10.6) and approx(rows[0]['components']['uncached_input'],6)
        elif cid<='E13':
            args=[inp/'labels.jsonl']
            if cid=='E11':args+=['--population-prevalence','.001']
            if cid=='E12':args+=['--drift-reference',inp/'reference.jsonl','--max-fpr-increase','.03']
            if cid=='E13':args+=['--baseline',inp/'reference.jsonl']
            rc,data=invoke(root,'calibrate_grader.py',args,evidence,'calibrate');detail=data
            if cid=='E08':ok=rc==0 and data.get('confusion')=={'tp':2,'tn':2,'fp':1,'fn':1} and approx(data.get('agreement'),2/3) and approx(data.get('recall'),2/3) and approx(data.get('precision'),2/3) and data.get('order_inconsistency_rate')==0
            elif cid=='E09':ok=rc==0 and data.get('ready_for_review') is False and data.get('false_positive_rate') is None
            elif cid=='E10':ok=rc==2 and 'adjudication changed' in data.get('error','')
            elif cid=='E11':ok=rc==0 and approx(data.get('false_positive_rate'),.02) and approx(data.get('false_negative_rate'),.1) and approx(data.get('population_adjusted_precision'),.04310344827586207)
            elif cid=='E12':ok=rc==0 and data.get('drift',{}).get('status')=='alert' and approx(data.get('drift',{}).get('false_positive_rate_delta'),.06)
            else:ok=rc==0 and data.get('paired_judges',{}).get('improved')==1 and data.get('paired_judges',{}).get('regressed')==1
        else:
            flow=d/'flow';args=['--card',inp/'card.json','--flow',flow,'--variant','baseline','--split','val','--execute']
            rc,data=invoke(root,'run_eval.py',args,evidence,'run-baseline');detail={'run':data}
            variant=flow/'baseline';manifest=json.loads((variant/'manifest.json').read_text()) if (variant/'manifest.json').exists() else {}
            if cid=='E14':
                r2,x=invoke(root,'run_eval.py',[*args[:args.index('--variant')],'--variant','v1','--split','val','--execute'],evidence,'run-candidate')
                r3,comp=invoke(root,'compare_runs.py',['--flow',flow,'--candidate','v1','--split','val','--metric','quality','--reps','1','--bootstrap','200'],evidence,'compare');detail.update(candidate=x,comparison=comp)
                ok=rc==0 and r2==0 and r3==0 and data.get('status')=='complete' and x.get('status')=='complete' and comp.get('complete_pairs')==2 and approx(comp.get('delta_candidate_minus_baseline'),1) and comp.get('identity_verified') is True
            elif cid in ('E15','E16','E17'):
                errors=readlines(variant/'errors.jsonl') if (variant/'errors.jsonl').exists() else []
                want='coverage_incomplete' if cid=='E16' else 'serving_substitution'
                detail.update(errors=errors)
                ok=rc==2 and data.get('completed_cases')==0 and len(errors)==1 and errors[0].get('status')==want and approx(data.get('known_cost_usd'),.02)
            elif cid=='E18':
                before=len(readlines(inp/'calls.jsonl')) if (inp/'calls.jsonl').exists() else 0
                r2,x=invoke(root,'run_eval.py',[*args,'--resume','--retry-errors'],evidence,'resume');after=len(readlines(inp/'calls.jsonl')) if (inp/'calls.jsonl').exists() else 0
                detail.update(resume=x,calls_before=before,calls_after=after)
                ok=rc==2 and r2==2 and data.get('attempts')==1 and x.get('attempts')==1 and before==after==1 and x.get('status')=='incomplete'
            elif cid in ('E19','E21','E22'):
                if rc!=0:
                    ok=False
                else:
                    interrupted(variant,evidence)
                    if cid=='E19':
                        r2,x=invoke(root,'report_eval.py',[flow],evidence,'report')
                        report=json.loads((flow/'report-data.json').read_text());v=report['variants'][0];detail.update(report=v)
                        ok=r2==0 and v.get('total_cost_usd') is None and v.get('unknown_cost_attempts')==1 and v.get('attempts')==1
                    elif cid=='E21':
                        before=len(readlines(inp/'calls.jsonl'))
                        r2,x=invoke(root,'run_eval.py',[*args,'--resume'],evidence,'resume');after=len(readlines(inp/'calls.jsonl'))
                        detail.update(resume=x,calls_before=before,calls_after=after)
                        ok=r2==2 and 'reconcile' in x.get('error','') and before==after
                    else:
                        write(d/'resolution.json',[{'attempt_id':1,'resolution':'abandoned','cost_usd':.02,'evidence':'Synthetic interrupted application outcome externally verified as abandoned by offline fixture operator; preserve original attempt and failure ceiling.'}])
                        r2,x=invoke(root,'reconcile_run.py',['--variant-dir',variant,'--resolutions',d/'resolution.json','--apply'],evidence,'reconcile')
                        before=len(readlines(inp/'calls.jsonl'))
                        r3,res=invoke(root,'run_eval.py',[*args,'--resume','--retry-errors'],evidence,'resume');after=len(readlines(inp/'calls.jsonl'))
                        detail.update(reconcile=x,resume=res,calls_before=before,calls_after=after)
                        ok=r2==0 and r3==2 and before==after==1 and res.get('attempts')==1 and res.get('status')=='incomplete'
            else:
                rows=readlines(variant/'results.jsonl');rows[0]['result_identity']={'comparison_hash':manifest.get('comparison_hash'),'treatment_hash':'foreign-treatment-binding','case_id':'a','rep':0}
                lines(variant/'results.jsonl',rows);manifest['results_sha256']=sha(variant/'results.jsonl');write(variant/'manifest.json',manifest)
                write(evidence/'transplant-transform.json',{'field':'result_identity.treatment_hash','replacement':'foreign-treatment-binding','updated_byte_hash_only':True})
                r2,x=invoke(root,'report_eval.py',[flow],evidence,'report');report=json.loads((flow/'report-data.json').read_text());v=report['variants'][0];detail.update(report=v)
                ok=r2==0 and v.get('integrity','').startswith('unverified:') and 'result identity' in v.get('integrity','')
        status='pass' if ok else 'unsupported' if name=='old' and challenge['classification']=='extension' else 'fail'
        result={**challenge,'variant':name,'outcome':status,'contract_satisfied':bool(ok),'evidence':d.relative_to(HERE).as_posix(),'observed':detail}
        write(d/'result.json',result);results.append(result)
        print(cid,name,status,flush=True)
    summary={'variant':name,'protocol_sha256':sha(HERE/'protocol.json'),'freeze_sha256':sha(HERE/'freeze.json'),'evidence_use':'pre-repair registered comparison' if name!='repaired_new' else 'validation after observed failures and repair','pass':sum(x['outcome']=='pass' for x in results),'fail':sum(x['outcome']=='fail' for x in results),'unsupported':sum(x['outcome']=='unsupported' for x in results),'results':results}
    write(HERE/(name+'-results.json'),summary)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--variant',choices=SOURCES);a=p.parse_args()
    if a.prepare:prepare()
    elif a.variant:run_variant(a.variant)
    else:p.error('use --prepare before execution, or --variant')
if __name__=='__main__':main()
