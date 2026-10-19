#!/usr/bin/env python3
"""Durable, provider-neutral staged work. No built-in model/client or scheduler.

One coordinator per journal; handlers receive stable operation keys and must
enforce I/O deadlines, authorization and remote idempotency themselves. A crash
leaves running work unknown. Closing a process does not cancel remote work.
"""
import argparse
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path


def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def fingerprint(value): return hashlib.sha256(encode(value).encode()).hexdigest()


def validate(spec):
    for key in ('tenant_id','run_id'):
        if not isinstance(spec.get(key),str) or not spec[key].strip(): raise ValueError('trusted '+key+' required')
    items=spec.get('items'); stages=spec.get('stages'); limits=spec.get('limits',{})
    if not isinstance(items,list) or not items: raise ValueError('nonempty item population required')
    ids=[i.get('id') for i in items if isinstance(i,dict)]
    if len(ids)!=len(items) or any(not isinstance(i,str) or not i or i=='__aggregate__' for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('unique nonempty item IDs required')
    if not isinstance(stages,list) or not stages: raise ValueError('nonempty ordered stages required')
    prior={}
    for stage in stages:
        key=stage.get('id'); scope=stage.get('scope','item'); deps=stage.get('depends_on',[])
        if not isinstance(key,str) or not key or key in prior: raise ValueError('unique stage IDs required')
        if scope not in ('item','aggregate'): raise ValueError('stage scope must be item or aggregate')
        if not isinstance(deps,list) or len(set(deps))!=len(deps) or any(d not in prior for d in deps):
            raise ValueError('dependencies must name unique earlier stages')
        for flag in ('required','retry_safe'):
            if flag in stage and type(stage[flag]) is not bool: raise ValueError(flag+' must be boolean')
        prior[key]=stage
    if not any(s.get('required',True) and s.get('scope','item')=='item' for s in stages):
        raise ValueError('required item stage needed for population coverage')
    for key in ('max_attempts','timeout_s'):
        value=limits.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0: raise ValueError('positive finite '+key+' required')
    if type(limits['max_attempts']) is not int: raise ValueError('max_attempts must be integer')
    return spec


class Workflow:
    """Immutable run identity, cumulative budgets, explicit unknown outcomes.

    The started record is committed before dispatch; an advisory coordinator lock
    prevents another live coordinator from mistaking active work for a crash.
    This is a local reference, not a distributed lease implementation.
    """
    def __init__(self,spec,path,clock=time.time):
        self.spec=json.loads(encode(validate(spec))); self.clock=clock; self.path=Path(path)
        spec=self.spec
        self.db=sqlite3.connect(str(path),timeout=1,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS run (identity TEXT PRIMARY KEY,spec TEXT,started REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS work (stage TEXT,item TEXT,state TEXT,result TEXT,attempts INTEGER,operation_key TEXT, PRIMARY KEY(stage,item))')
        self.db.execute('CREATE TABLE IF NOT EXISTS reconciliation (stage TEXT,item TEXT,evidence TEXT,state TEXT,at REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS control (key TEXT PRIMARY KEY,value TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS lifecycle (at REAL,event TEXT)')
        old=self.db.execute('SELECT identity,started FROM run').fetchall()
        identity=fingerprint(spec)
        if old and (len(old)!=1 or old[0][0]!=identity):
            self.db.close(); raise ValueError('journal belongs to a different tenant/run/specification')
        if old: self.started=old[0][1]
        else:
            self.started=clock()
            self.db.execute('BEGIN IMMEDIATE')
            try:
                self.db.execute('INSERT INTO run VALUES (?,?,?)',(identity,encode(spec),self.started))
                for stage in spec['stages']:
                    ids=['__aggregate__'] if stage.get('scope','item')=='aggregate' else [i['id'] for i in spec['items']]
                    for item in ids:
                        key=fingerprint([spec['tenant_id'],spec['run_id'],stage['id'],item])
                        self.db.execute('INSERT INTO work VALUES (?,?,?,NULL,0,?)',(stage['id'],item,'pending',key))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK'); self.db.close(); raise
    def close(self): self.db.close()
    def rows(self):
        return [{'stage':s,'id':i,'status':state,'result':json.loads(result) if result is not None else None,
                 'attempts':attempts,'operation_key':key} for s,i,state,result,attempts,key in self.db.execute('SELECT * FROM work ORDER BY rowid')]
    def report(self):
        rows=self.rows(); stages=[]; population=[i['id'] for i in self.spec['items']]
        eligible=set(population)
        for stage in self.spec['stages']:
            subset=[r for r in rows if r['stage']==stage['id']]; counts={}
            for r in subset: counts[r['status']]=counts.get(r['status'],0)+1
            passed={r['id'] for r in subset if r['status']=='succeeded'}
            if stage.get('required',True) and stage.get('scope','item')=='item': eligible &= passed
            stages.append({'id':stage['id'],'scope':stage.get('scope','item'),'required':stage.get('required',True),
                'total':len(subset),'counts':counts,'coverage':len(passed)/len(subset),
                'uncovered':[{'id':r['id'],'status':'unknown' if r['status']=='running' else r['status']} for r in subset if r['status']!='succeeded']})
        attempts=sum(r['attempts'] for r in rows)
        required_aggregate_failed=any(r['status']!='succeeded' for r in rows if any(s['id']==r['stage'] and s.get('required',True) and s.get('scope','item')=='aggregate' for s in self.spec['stages']))
        unknown=any(r['status']=='running' for r in rows)
        pending=any(r['status']=='pending' for r in rows)
        status='unknown' if unknown else ('pending' if pending else ('completed' if len(eligible)==len(population) and not required_aggregate_failed else 'incomplete'))
        stop=self.db.execute("SELECT value FROM control WHERE key='stop_reason'").fetchone()
        stop_reason=stop[0] if stop else None
        if stop_reason=='cancelled': status='cancelled'
        return {'schema_version':1,'run_id':self.spec['run_id'],'status':status,'stop_reason':stop_reason,
            'cancellation_requested':stop_reason=='cancelled','stages':stages,'coverage':len(eligible)/len(population),
            'covered_ids':[i for i in population if i in eligible],'uncovered_ids':[i for i in population if i not in eligible],
            'attempts':attempts,'remaining_attempts':max(0,self.spec['limits']['max_attempts']-attempts),
            'remaining_seconds':max(0,self.spec['limits']['timeout_s']-(self.clock()-self.started)),
            'scope':'local workflow journal and adapter outcomes; not provider cancellation or task-quality proof'}
    def reconcile(self,stage,item,state,result,evidence):
        import fcntl
        with self.path.with_suffix(self.path.suffix+'.coordinator').open('a') as guard:
            try: fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('stop the active coordinator before reconciling an operation')
            return self._reconcile_stopped(stage,item,state,result,evidence)
    def _reconcile_stopped(self,stage,item,state,result,evidence):
        if state not in ('succeeded','failed') or not isinstance(evidence,str) or not evidence.strip():
            raise ValueError('external outcome and evidence required')
        payload=encode(result)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            n=self.db.execute("UPDATE work SET state=?,result=? WHERE stage=? AND item=? AND state='running'",(state,payload,stage,item)).rowcount
            if n!=1: raise ValueError('exactly one unknown operation required')
            self.db.execute('INSERT INTO reconciliation VALUES (?,?,?,?,?)',(stage,item,evidence,state,self.clock())); self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise
    def run(self,handlers,authorize,cancelled=lambda:False,retry_failed=False,resume_cancelled=False):
        # flock is released by the OS on crash. It does not prove the remote
        # action stopped; running records still require reconciliation.
        import fcntl
        with self.path.with_suffix(self.path.suffix+'.coordinator').open('a') as guard:
            try: fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('another coordinator owns this journal')
            def stop(reason):
                self.db.execute("INSERT OR REPLACE INTO control VALUES ('stop_reason',?)",(reason,))
                self.db.execute('INSERT INTO lifecycle VALUES (?,?)',(self.clock(),reason))
                return self.report()
            if self.report()['cancellation_requested']:
                if not resume_cancelled: return self.report()
                self.db.execute("DELETE FROM control WHERE key='stop_reason'")
                self.db.execute('INSERT INTO lifecycle VALUES (?,?)',(self.clock(),'explicit_resume_after_cancel'))
            for stage in self.spec['stages']:
                if stage['id'] not in handlers: raise ValueError('missing handler for stage '+stage['id'])
                for row in [r for r in self.rows() if r['stage']==stage['id']]:
                    if row['status']=='running': continue  # Unknown effects never auto-replay.
                    if row['status']=='failed' and not (retry_failed and stage.get('retry_safe') is True): continue
                    if row['status']=='failed' and retry_failed:
                        downstream={stage['id']}
                        for candidate in self.spec['stages']:
                            if downstream.intersection(candidate.get('depends_on',[])): downstream.add(candidate['id'])
                        if any(r['stage'] in downstream-{stage['id']} and r['attempts'] for r in self.rows()):
                            raise ValueError('downstream already consumed this outcome; start a new run instead of reusing stale synthesis')
                    if row['status'] not in ('pending','failed','not_covered'): continue
                    current=self.report()
                    if cancelled(): return stop('cancelled')
                    if current['remaining_seconds']<=0: return stop('deadline')
                    if current['remaining_attempts']<=0: return stop('attempt_budget')
                    previous=[r for r in self.rows() if r['stage'] in stage.get('depends_on',[])]
                    if stage.get('scope','item')=='item':
                        prereqs=[r for r in previous if r['id'] in (row['id'],'__aggregate__')]
                        if any(r['status']!='succeeded' for r in prereqs):
                            # Unknown/pending ancestors may be reconciled on a later run.
                            if any(r['status'] in ('running','pending') for r in prereqs): continue
                            self.db.execute("UPDATE work SET state='not_covered' WHERE stage=? AND item=?",(stage['id'],row['id'])); continue
                        previous=prereqs  # Item workers receive only their own dependency context.
                    elif any(r['status'] in ('running','pending') for r in previous): continue
                    context={'tenant_id':self.spec['tenant_id'],'run_id':self.spec['run_id'],'stage':stage['id'],'item_id':row['id'],
                        'item':next((i for i in self.spec['items'] if i['id']==row['id']),None),
                        'dependencies':previous,'coverage':current,'operation_key':row['operation_key'],
                        'remaining_seconds':current['remaining_seconds']}
                    authorize(context)
                    if cancelled(): return stop('cancelled')
                    if self.report()['remaining_seconds']<=0: return stop('deadline')
                    self.db.execute("UPDATE work SET state='running',attempts=attempts+1 WHERE stage=? AND item=?",(stage['id'],row['id']))
                    # Any exception/malformed outcome leaves running: it may
                    # have happened after a real external side effect.
                    outcome=handlers[stage['id']](context)
                    if not isinstance(outcome,dict) or outcome.get('status') not in ('succeeded','failed') or 'output' not in outcome:
                        raise ValueError('handler must return status succeeded/failed and output; outcome remains unknown')
                    encoded=encode(outcome['output'])
                    self.db.execute('UPDATE work SET state=?,result=? WHERE stage=? AND item=?',(outcome['status'],encoded,stage['id'],row['id']))
                    if cancelled(): return stop('cancelled')
            return self.report()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True); parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--execute-demo',action='store_true',help='Execute deterministic local handlers only; no provider calls')
    args=parser.parse_args(); spec=validate(json.loads(args.spec.read_text()))
    if not args.execute_demo:
        print(json.dumps({'plan':spec,'journal_exists':args.db.exists(),'execution':False},indent=2)); return
    journal=Workflow(spec,args.db)
    try:
        def demo(context):
            return {'status':'succeeded','output':{'item_id':context['item_id'],'stage':context['stage'],'observed_coverage':context['coverage']['coverage']}}
        print(json.dumps(journal.run({s['id']:demo for s in spec['stages']},lambda ctx:None),indent=2))
    finally: journal.close()


if __name__=='__main__': main()
