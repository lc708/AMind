#!/usr/bin/env python3
from grade_common import run,require

def req(s,op,tenant='north',job='batch-23',expected=0,**kw):return s.call({'op':op,'tenant':tenant,'job':job,**kw},expected)
def submit(s,items=None,limit=12,tenant='north'):
    return req(s,'submit',tenant=tenant,spec={'items':items if items is not None else [{'id':'a'}],'max_attempts':limit})
def find(r,stage,item):return next(x for x in r['rows'] if x['stage']==stage and x['item']==item)
def identity(s):
    submit(s,[{'id':'north-only'}],tenant='north');submit(s,[{'id':'south-1'},{'id':'south-2'}],tenant='south');r=req(s,'report',tenant='south')
    require(r['tenant']=='south' and set(r['uncovered_ids'])=={'south-1','south-2'},'tenant populations mixed')
def keys(s):
    submit(s,tenant='north');submit(s,tenant='south');a=req(s,'report',tenant='north');b=req(s,'report',tenant='south')
    require({r['operation_key'] for r in a['rows']}.isdisjoint({r['operation_key'] for r in b['rows']}),'remote operation key collides across tenants')
def immutable(s):
    submit(s);req(s,'submit',spec={'items':[{'id':'changed'}],'max_attempts':50},expected=2);r=req(s,'report');require(r['uncovered_ids']==['a'] and r['remaining_attempts']==12,'resubmit changed immutable job')
def noop(s):
    submit(s);a=req(s,'work');n=len(s.received());b=req(s,'work');require(n==3 and len(s.received())==n and a['attempts']==b['attempts']==3,'settled work replayed or cumulative count reset')
def crash(s,limit=12):
    submit(s,[{'id':'a','payload':{'crash_after_effect':'inspect'}}],limit);req(s,'work',expected=17)
def crash_record(s):
    crash(s);r=req(s,'report');require(find(r,'inspect','a')['state']=='running' and r['attempts']==1,'dispatch was not durably reserved before effect')
def no_replay(s):
    crash(s);before=s.received();req(s,'work');after=s.received();r=req(s,'report');require(len(before)==len(after)==1 and r['attempts']==1 and r['status']=='unknown','unknown side effect replayed or dependent summary delivered')
def evidence(s):
    crash(s);req(s,'reconcile',stage='inspect',item='a',state='succeeded',result={'receipt':'seen'},expected=2)
def settled(s):
    submit(s);req(s,'work');req(s,'reconcile',stage='inspect',item='a',state='failed',evidence='manual note',result={},expected=2);r=req(s,'report');require(r['status']=='completed','settled operation rewritten')
def recovered(s):
    crash(s,3);before=req(s,'report');key=find(before,'inspect','a')['operation_key']
    req(s,'reconcile',stage='inspect',item='a',state='succeeded',result={'receipt':'confirmed'},evidence='receiver receipt confirmed externally');r=req(s,'work')
    require(r['status']=='completed' and r['attempts']==3 and r['remaining_attempts']==0 and len(s.received())==3 and find(r,'inspect','a')['operation_key']==key,'reconciliation lost effect identity, budget or progress')
def budget(s):
    submit(s,[{'id':'a'},{'id':'b'}],2);first=req(s,'work');n=len(s.received());second=req(s,'work');require(first['attempts']==second['attempts']==2 and len(s.received())==n==2 and second['remaining_attempts']==0,'restart renewed cumulative budget')
def cancel(s):
    submit(s);req(s,'cancel');r=req(s,'work');require(r['status']=='cancelled' and r['cancelled'] and not s.received(),'cancelled job dispatched after restart')
def resume(s):
    submit(s,[{'id':'a'},{'id':'b'}],2);req(s,'work');req(s,'cancel');req(s,'resume');r=req(s,'work');require(r['attempts']==2 and r['remaining_attempts']==0 and len(s.received())==2,'explicit resume reset original budget')
def review_gap(s):
    submit(s,[{'id':'a'},{'id':'b','payload':{'review':'fail'}}]);r=req(s,'work');summaries=[x for x in s.received() if x['stage']=='summary']
    require(r['coverage']==.5 and r['covered_ids']==['a'] and r['uncovered_ids']==['b'] and r['status']=='incomplete','failed review counted as covered');require(len(summaries)==1 and summaries[0]['coverage']['uncovered_ids']==['b'],'summary lost full population gap')
def dependency(s):
    submit(s,[{'id':'a'},{'id':'b','payload':{'inspect':'fail'}}]);r=req(s,'work');receipts=s.received();require(not any(x['stage']=='review' and x['item']=='b' for x in receipts),'failed prerequisite still dispatched review')
    require(find(r,'review','b')['state']=='not_covered' and r['uncovered_ids']==['b'] and len(receipts)==4,'dependency gap or full coverage report missing')
PROBES=[('D01','identity',True,identity),('D02','identity',True,keys),('D03','identity',False,immutable),('D04','continuity',False,noop),('D05','recovery',False,crash_record),('D06','recovery',True,no_replay),('D07','recovery',True,evidence),('D08','recovery',True,settled),('D09','recovery',False,recovered),('D10','budget',True,budget),('D11','cancellation',True,cancel),('D12','budget',False,resume),('D13','coverage',True,review_gap),('D14','coverage',False,dependency)]
if __name__=='__main__':run('E-DURABLE','intake',PROBES)
