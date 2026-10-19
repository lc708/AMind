#!/usr/bin/env python3
"""Build a local all-metric report with failures, spend, integrity status and escaped traces."""
import argparse
import html
import json
import re
import statistics
import sys
from pathlib import Path
from kernel_common import atomic, contract_hash, finite, in_root, read_bytes, read_json, read_jsonl, sha, write_json


def quantile(values,q):
    if not values: return None
    values=sorted(values); pos=(len(values)-1)*q; low=int(pos); high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(pos-low)


def esc(value):
    return html.escape(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value))



def validate_observations(rows, name):
    seen=set()
    for row in rows:
        key=(row.get('prompt_id'),row.get('rep'))
        if not isinstance(key[0],str) or not key[0] or type(key[1]) is not int or key[1]<0:
            raise ValueError(f'{name}: results require string prompt_id and nonnegative integer rep')
        if key in seen:
            raise ValueError(f'{name}: duplicate completed result key')
        seen.add(key)


def validate_attempts(events, name):
    starts,finishes={},{}
    for event in events:
        kind,number=event.get('event'),event.get('attempt_id')
        if kind not in ('started','finished') or type(number) is not int or number<=0:
            raise ValueError(f'{name}: invalid attempt journal event or ID')
        target=starts if kind=='started' else finishes
        if number in target:
            raise ValueError(f'{name}: duplicate {kind} attempt ID')
        if kind=='finished':
            if number not in starts:
                raise ValueError(f'{name}: finished attempt has no preceding start')
            if any(event.get(k)!=starts[number].get(k) for k in ('prompt_id','rep')):
                raise ValueError(f'{name}: finished attempt case/repetition differs from start')
        target[number]=event
    return list(finishes.values()),[event for number,event in starts.items() if number not in finishes]


def report_contract(state, manifest, name):
    """Bind report metadata to each v2 export, retaining descriptive legacy input."""
    if manifest.get('schema_version')!=2:
        split=manifest.get('split','val')
        return (state.get(split+'_ids',[]), manifest.get('reps',state.get('reps',1)), state['metrics'])
    identity=manifest.get('comparison_identity',{})
    if not isinstance(identity,dict) or not isinstance(state,dict):
        raise ValueError(f'{name}: missing bound report population/metrics/reps')
    splits=identity.get('splits',{})
    split,reps,metrics=identity.get('split'),identity.get('reps'),identity.get('metrics')
    if (not isinstance(splits,dict) or split not in ('train','val','test')
            or type(reps) is not int or reps<1 or not isinstance(metrics,list) or not metrics):
        raise ValueError(f'{name}: missing bound report population/metrics/reps')
    for partition in ('train','val','test'):
        ids=splits.get(partition,[])
        if (not isinstance(ids,list) or any(not isinstance(key,str) for key in ids)
                or state.get(partition+'_ids',[])!=ids):
            raise ValueError(f'{name}: report state {partition} population differs from experiment identity')
    if state.get('metrics')!=metrics:
        raise ValueError(f'{name}: report state metrics differ from experiment identity')
    if type(state.get('reps')) is not int or state['reps']!=reps:
        raise ValueError(f'{name}: report state reps differ from experiment identity')
    if manifest.get('split')!=split or type(manifest.get('reps')) is not int or manifest['reps']!=reps:
        raise ValueError(f'{name}: manifest split/reps differ from experiment identity')
    return splits.get(split,[]),reps,metrics


def summarize(flow):
    state=read_json(in_root(flow,'_state.json')); summaries=[]; details=[]
    dirs=sorted([p for p in flow.iterdir() if p.name=='baseline' or re.fullmatch(r'v[1-9][0-9]*',p.name)],
                key=lambda p:0 if p.name=='baseline' else int(p.name[1:]))
    for directory in dirs:
        name=directory.name
        rows=read_jsonl(in_root(flow,f'{name}/results.jsonl'))
        validate_observations(rows,name)
        errors_path=in_root(flow,f'{name}/errors.jsonl'); errors=read_jsonl(errors_path) if errors_path.exists() else []
        events_path=in_root(flow,f'{name}/attempts.jsonl')
        events=read_jsonl(events_path) if events_path.exists() else []
        attempts,interrupted=validate_attempts(events,name)
        manifest_path=in_root(flow,f'{name}/manifest.json'); manifest=read_json(manifest_path) if manifest_path.exists() else {}
        if manifest.get('schema_version')==2 and manifest.get('variant')!=name:
            raise ValueError(f'{name}: manifest variant differs from its directory')
        planned_ids,reps,metric_specs=report_contract(state,manifest,name)
        integrity='unverified legacy artifacts'
        try:
            contract_hash(manifest)
            if manifest['results_sha256']!=sha(read_bytes(in_root(flow,f'{name}/results.jsonl'))): raise ValueError('result hash changed')
            if manifest.get('attempts_sha256')!=sha(read_bytes(events_path)): raise ValueError('attempt hash changed')
            if manifest.get('result_identity_required'):
                for row in rows:
                    expected={'comparison_hash':manifest['comparison_hash'],
                              'treatment_hash':manifest.get('treatment_hash'),
                              'case_id':row.get('prompt_id'),'rep':row.get('rep')}
                    if row.get('result_identity')!=expected:
                        raise ValueError('result identity differs from its measurement/treatment/case')
            integrity='hashes match export; not a security attestation'
        except (OSError,ValueError,KeyError) as e:
            integrity='unverified: '+str(e)
        planned=len(planned_ids)*reps
        scores={}
        for m in metric_specs:
            values=[r.get('grade',{}).get(m['id']) for r in rows if r.get('status')=='ok']
            values=[float(v) for v in values if finite(v) or isinstance(v,bool)]
            scores[m['id']]={'mean':statistics.mean(values) if values else None,'scored':len(values)}
        cost_items=attempts if attempts or interrupted else rows
        known=sum(r.get('known_cost_usd',r.get('cost_usd') or 0.) for r in cost_items)
        unknown=sum(not finite(r.get('cost_usd')) for r in cost_items)+len(interrupted)
        latency=[r['latency_s'] for r in rows if finite(r.get('latency_s'))]
        summaries.append({'variant':name,'split':manifest.get('split','unknown'),'status':manifest.get('status','unknown'),
                          'scored_observations':len(rows),'planned_observations':planned,'metrics':scores,
                          'failed_attempts':len(errors),'attempts':len(attempts)+len(interrupted) if events else None,
                          'interrupted_attempts':len(interrupted),
                          'known_cost_usd':known,'unknown_cost_attempts':unknown,
                          'total_cost_usd':None if unknown else known,
                          'latency_p50_s':quantile(latency,.5),'latency_p95_s':quantile(latency,.95),
                          'integrity':integrity,'synthetic':any(r.get('meta',{}).get('synthetic') for r in rows)})
        summaries[-1]['stage_coverage'] = {'measured_complete': sum(r.get('coverage', {}).get('status') == 'measured_complete' for r in rows),
                                          'unmeasured': sum(r.get('coverage', {}).get('status') != 'measured_complete' for r in rows),
                                          'required_stages': manifest.get('comparison_identity', {}).get('coverage', {}).get('required_stages', [])}
        summaries[-1]['remaining_failed_attempts'] = manifest.get('remaining_failed_attempts')
        for row in rows:
            trace=None
            if row.get('trace_file'):
                try: trace=read_json(in_root(flow,f"{name}/{row['trace_file']}"))
                except (OSError,ValueError) as e: trace={'unavailable':str(e)}
            details.append({'variant':name,'case':row.get('prompt_id'),'rep':row.get('rep'),'grade':row.get('grade'),
                            'result_identity':row.get('result_identity'), 'billing_identity':row.get('billing_identity'),
                            'coverage':row.get('coverage', {'status':'unmeasured'}),
                            'cost_usd':row.get('cost_usd'),'output':row.get('output'),'explanation':row.get('explanation'),'trace':trace})
        for error in errors: details.append({'variant':name,'failure':error})
        for attempt in interrupted:
            details.append({'variant':name,'interrupted_attempt':attempt,'cost_usd':None,
                            'outcome':'unknown; reconcile before retrying'})
    return {'variants':summaries,'details':details,
            'interpretation':'Scored means exclude unscored attempts; inspect coverage before comparing. Validation is selection evidence. Synthetic runs do not measure model ability. No automatic winner.'}


def build(flow):
    report=summarize(flow)
    columns=['variant','split','status','scored_observations','planned_observations','failed_attempts','known_cost_usd','unknown_cost_attempts','latency_p50_s','latency_p95_s','synthetic']
    table='<table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in columns)+'</tr></thead><tbody>'
    for row in report['variants']:
        table+='<tr>'+''.join('<td>'+esc(row[k])+'</td>' for k in columns)+'</tr>'
    table+='</tbody></table>'
    sections=''
    for row in report['variants']:
        sections+='<h2>'+esc(row['variant'])+'</h2><p>'+esc(row['integrity'])+'</p><pre>'+esc(row['metrics'])+'</pre><pre>'+esc(row['stage_coverage'])+'</pre>'
    for detail in report['details']:
        label=f"{detail['variant']} · {detail.get('case','failed attempt')} · rep {detail.get('rep','—')}"
        sections+='<details><summary>'+esc(label)+'</summary><pre>'+esc(detail)+'</pre></details>'
    document='<!doctype html><html lang="en"><meta charset="utf-8"><title>AMind evaluation evidence</title><style>body{font:15px system-ui;margin:32px;color:#17242c;background:#f6f8fa}table{border-collapse:collapse;display:block;overflow:auto}td,th{padding:10px;border:1px solid #ccd6dc;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{background:white;padding:12px;margin:8px 0}summary{cursor:pointer}h1{font-size:26px}</style><h1>AMind evaluation evidence</h1><p>'+esc(report['interpretation'])+'</p>'+table+sections+'</html>'
    atomic(flow,'report-full.html',document); write_json(flow,'report-data.json',report)
    return {'report':str(flow/'report-full.html'),'data':str(flow/'report-data.json'),'variants':len(report['variants'])}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('flow',type=Path); a=p.parse_args()
    try: print(json.dumps(build(a.flow.resolve()),ensure_ascii=False)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
