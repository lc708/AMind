#!/usr/bin/env python3
"""Reconcile interrupted attempts with explicit external evidence. Plans unless --apply."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from kernel_common import append_json, contract_hash, in_root, read_bytes, read_json, read_jsonl, sha, finite, write_json


def reconcile(directory,resolutions,apply=False):
    lock=in_root(directory,'.run.lock')
    if lock.exists():
        pid=read_json(lock).get('pid')
        if type(pid) is not int or pid<=0: raise ValueError('invalid lock; inspect manually')
        try: os.kill(pid,0)
        except ProcessLookupError: pass
        else: raise ValueError('recorded worker may still be running; do not reconcile it')
    manifest=read_json(in_root(directory,'manifest.json')); contract_hash(manifest)
    events=read_jsonl(in_root(directory,'attempts.jsonl')); rows=read_jsonl(in_root(directory,'results.jsonl'))
    starts={x['attempt_id']:x for x in events if x.get('event')=='started'}
    finished={x['attempt_id']:x for x in events if x.get('event')=='finished'}
    pending=set(starts)-set(finished)
    by_attempt={r['attempt_id']:r for r in rows}
    if len(by_attempt)!=len(rows): raise ValueError('duplicate result attempts; inspect manually')
    proposed=[]; seen=set()
    for r in resolutions:
        number=r.get('attempt_id')
        if number not in pending or number in seen: raise ValueError('resolution must identify each pending attempt once')
        seen.add(number)
        if not isinstance(r.get('evidence'),str) or not r['evidence'].strip(): raise ValueError('external outcome/cost evidence required')
        cost=r.get('cost_usd')
        if cost is not None and (not finite(cost) or cost<0): raise ValueError('cost must be nonnegative or null for unknown')
        success=number in by_attempt
        if success and r.get('resolution')!='recorded_success': raise ValueError('completed result exists; reconcile its recorded_success')
        if not success and r.get('resolution')!='abandoned': raise ValueError('without a result, mark abandoned; do not fabricate a grade')
        if success and cost!=by_attempt[number].get('attempt_cost_usd',by_attempt[number].get('cost_usd')): raise ValueError('recorded result cost differs; investigate before reconciliation')
        proposed.append({'event':'finished','attempt_id':number,'prompt_id':starts[number]['prompt_id'],'rep':starts[number]['rep'],
                         'status':'ok' if success else 'interrupted_reconciled','cost_usd':cost,'time':time.time(),
                         'reconciliation_evidence':r['evidence']})
    if seen!=pending: raise ValueError('resolve every interrupted attempt, or keep the run paused')
    if not pending: raise ValueError('no interrupted attempts; journal/results edits require a new export with provenance')
    if apply:
        for event in proposed:
            append_json(directory,'attempts.jsonl',event)
            if event['status']!='ok': append_json(directory,'errors.jsonl',event)
        append_json(directory,'reconciliation.jsonl',{'at':time.time(),'resolutions':resolutions,
                    'old_results_hash':manifest.get('results_sha256'),'old_journal_hash':manifest.get('attempts_sha256')})
        manifest.update(status='incomplete',results_sha256=sha(read_bytes(directory/'results.jsonl')),
                        attempts_sha256=sha(read_bytes(directory/'attempts.jsonl')))
        write_json(directory,'manifest.json',manifest)
        if lock.exists(): lock.unlink()
    return {'mode':'applied' if apply else 'plan','reconciled':proposed,
            'next':'Resume only after reconciliation. Unknown cost blocks a dollar-budgeted resume. Original attempt/time limits remain in force.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--variant-dir',type=Path,required=True)
    p.add_argument('--resolutions',type=Path,required=True); p.add_argument('--apply',action='store_true'); a=p.parse_args()
    try: print(json.dumps(reconcile(a.variant_dir,read_json(a.resolutions),a.apply),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
