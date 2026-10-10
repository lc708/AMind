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


def summarize(flow):
    state=read_json(in_root(flow,'_state.json')); summaries=[]; details=[]
    dirs=sorted([p for p in flow.iterdir() if p.name=='baseline' or re.fullmatch(r'v[1-9][0-9]*',p.name)],
                key=lambda p:0 if p.name=='baseline' else int(p.name[1:]))
    for directory in dirs:
        name=directory.name
        rows=read_jsonl(in_root(flow,f'{name}/results.jsonl'))
        errors_path=in_root(flow,f'{name}/errors.jsonl'); errors=read_jsonl(errors_path) if errors_path.exists() else []
        events_path=in_root(flow,f'{name}/attempts.jsonl')
        attempts=[e for e in read_jsonl(events_path) if e.get('event')=='finished'] if events_path.exists() else []
        manifest_path=in_root(flow,f'{name}/manifest.json'); manifest=read_json(manifest_path) if manifest_path.exists() else {}
        integrity='unverified legacy artifacts'
        try:
            contract_hash(manifest)
            if manifest['results_sha256']!=sha(read_bytes(in_root(flow,f'{name}/results.jsonl'))): raise ValueError('result hash changed')
            if manifest.get('attempts_sha256')!=sha(read_bytes(events_path)): raise ValueError('attempt hash changed')
            integrity='hashes match export; not a security attestation'
        except (OSError,ValueError,KeyError) as e:
            integrity='unverified: '+str(e)
        planned=len(state.get(manifest.get('split','val')+'_ids',[]))*manifest.get('reps',state.get('reps',1))
        scores={}
        for m in state['metrics']:
            values=[r.get('grade',{}).get(m['id']) for r in rows if r.get('status')=='ok']
            values=[float(v) for v in values if finite(v) or isinstance(v,bool)]
            scores[m['id']]={'mean':statistics.mean(values) if values else None,'scored':len(values)}
        cost_items=attempts if attempts else rows
        known=sum(r.get('known_cost_usd',r.get('cost_usd') or 0.) for r in cost_items)
        unknown=sum(not finite(r.get('cost_usd')) for r in cost_items)
        latency=[r['latency_s'] for r in rows if finite(r.get('latency_s'))]
        summaries.append({'variant':name,'split':manifest.get('split','unknown'),'status':manifest.get('status','unknown'),
                          'scored_observations':len(rows),'planned_observations':planned,'metrics':scores,
                          'failed_attempts':len(errors),'attempts':len(attempts) if attempts else None,
                          'known_cost_usd':known,'unknown_cost_attempts':unknown,
                          'total_cost_usd':None if unknown else known,
                          'latency_p50_s':quantile(latency,.5),'latency_p95_s':quantile(latency,.95),
                          'integrity':integrity,'synthetic':any(r.get('meta',{}).get('synthetic') for r in rows)})
        for row in rows:
            trace=None
            if row.get('trace_file'):
                try: trace=read_json(in_root(flow,f"{name}/{row['trace_file']}"))
                except (OSError,ValueError) as e: trace={'unavailable':str(e)}
            details.append({'variant':name,'case':row.get('prompt_id'),'rep':row.get('rep'),'grade':row.get('grade'),
                            'cost_usd':row.get('cost_usd'),'output':row.get('output'),'explanation':row.get('explanation'),'trace':trace})
        for error in errors: details.append({'variant':name,'failure':error})
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
        sections+='<h2>'+esc(row['variant'])+'</h2><p>'+esc(row['integrity'])+'</p><pre>'+esc(row['metrics'])+'</pre>'
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
