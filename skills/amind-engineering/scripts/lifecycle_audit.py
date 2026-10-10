#!/usr/bin/env python3
"""Audit a normalized agent event journal for replay, cancellation and side-effect hazards."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def audit(events):
    seen={}; tasks={}; operations={}; findings=[]; duplicates=0
    def add(index,code,detail): findings.append({'event_index':index,'code':code,'detail':detail})
    for index,event in enumerate(events):
        for field in ('id','task_id','tenant_id','kind'):
            if not isinstance(event.get(field),str) or not event[field]: raise ValueError('event requires '+field)
        fingerprint=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        event_key=(event['tenant_id'],event['id'])
        if event_key in seen:
            if seen[event_key]!=fingerprint: add(index,'conflicting_event_replay','same event ID has different contents')
            else: duplicates+=1
            continue
        seen[event_key]=fingerprint
        key=(event['tenant_id'],event['task_id']); state=tasks.setdefault(key,{'terminal':False,'cancelled':False,'started':False})
        kind=event['kind']
        if state['terminal'] and kind not in ('usage','cleanup_completed'):
            add(index,'event_after_terminal',kind)
        if kind=='task_started':
            if state['started']: add(index,'duplicate_task_start','second start is not an identical replay')
            state['started']=True
        elif not state['started']: add(index,'event_before_start',kind)
        if kind=='cancel_requested': state['cancelled']=True
        if kind=='effect_started':
            op=event.get('idempotency_key'); external=event.get('external_operation_id')
            if not isinstance(op,str) or not op: add(index,'missing_idempotency_key','side effect lacks a durable application key'); continue
            opkey=(event['tenant_id'],op)
            if opkey in operations: add(index,'duplicate_effect_attempt','reconcile durable state before issuing the effect again')
            operations[opkey]={'task':key,'finished':False,'external_id':external}
            if state['cancelled']: add(index,'effect_after_cancel','dispatch occurred after cancellation request')
        elif kind in ('effect_succeeded','effect_failed','effect_reconciled'):
            opkey=(event['tenant_id'],event.get('idempotency_key'))
            if opkey not in operations: add(index,'orphan_effect_result','effect completion has no dispatch in this journal')
            elif operations[opkey]['task']!=key: add(index,'effect_wrong_task','completion belongs to another task')
            else: operations[opkey]['finished']=True
        elif kind=='task_completed':
            state['terminal']=True
            if state['cancelled']: add(index,'completed_after_cancel','define whether this is a cancellation race or an invalid success')
            if any(v['task']==key and not v['finished'] for v in operations.values()): add(index,'completed_with_unknown_effect','unreconciled effect at completion')
        elif kind in ('task_failed','task_cancelled'): state['terminal']=True
        elif kind=='memory_read':
            if event.get('memory_tenant_id')!=event['tenant_id']: add(index,'memory_tenant_mismatch','memory crosses tenant boundary')
            expires=event.get('expires_at'); now=event.get('at')
            if isinstance(expires,(int,float)) and isinstance(now,(int,float)) and expires<=now: add(index,'expired_memory','read past memory TTL')
        elif kind=='child_started':
            if event.get('child_budget') is None: add(index,'unbounded_child','child lacks a recorded budget allocation')
        elif kind=='webhook_received':
            if event.get('signature_verified') is not True: add(index,'unverified_webhook','authenticate the raw body before accepting the event')
    unresolved=[{'tenant_id':k[0],'idempotency_key':k[1],'external_operation_id':v['external_id']} for k,v in operations.items() if not v['finished']]
    return {'events':len(events),'duplicate_deliveries':duplicates,'tasks':len(tasks),'findings':findings,'unresolved_effects':unresolved,
            'limits':'Offline audit of normalized facts, not an execution runtime or proof of exactly-once effects. Signature_verified and ownership fields require trusted instrumentation.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('events',type=Path); a=p.parse_args()
    try:
        result=audit([json.loads(s) for s in a.events.read_text().splitlines() if s.strip()]); print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result['findings'] or result['unresolved_effects'] else 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
