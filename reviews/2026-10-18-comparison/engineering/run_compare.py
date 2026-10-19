#!/usr/bin/env python3
"""Offline registered application contract comparison. No provider/model/network calls."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

class Unsupported(Exception): pass

def load(root, name):
    path=root/'scripts'/f'{name}.py'
    if not path.exists(): raise Unsupported(f'No equivalent packaged public entry for {name}; not a quality failure')
    spec=importlib.util.spec_from_file_location('contrast_'+name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def message(text,owner=None,phase='final_answer'):
    value={'type':'message','phase':phase,'content':[{'type':'output_text','text':text}]}
    if owner is not None: value['agent']={'agent_name':owner}
    return value

def expect(condition, why):
    if not condition: raise AssertionError(why)

def execute(root, ident, ev, tmp):
    r=load(root,'response_contract')
    t=load(root,'tool_loop')
    if ident=='E01':
        value={'status':'completed','output':[message('Working.',phase='commentary'),message('Approved.')]}
        result=r.normalize(value);ev.update(input=value,result=result)
        expect(result['final_text']=='Approved.' and result['commentary_text']=='Working.' and result['answer_complete'],'phase projection wrong')
    elif ident=='E02':
        value={'status':'completed','error':{'code':'contradiction'},'output':[message('bad')]};ev['input']=value
        try: ev['result']=r.normalize(value)
        except ValueError as exc:ev['rejected']=str(exc);return
        raise AssertionError('completed response with error accepted')
    elif ident=='E03':
        ids=['one','two','three'];rows=[{'custom_id':i,'response':{'status_code':200,'body':{'status':'completed'}}} for i in ['two','one']]
        result=r.match_batch(ids,rows);ev.update(input={'request_ids':ids,'results':rows},result=result)
        expect([row['custom_id'] if row else None for row in result['ordered']]==['one','two',None] and result['missing']==['three'],'batch order or missing population wrong')
    elif ident in ('E04','E05'):
        actual=[];auth=[];cancel=[False]
        def authorize(*args):
            auth.append(args)
            if ident=='E05':cancel[0]=True
        tool={'schema':{'type':'function','name':'commit'},'validate':lambda args:None,'handler':lambda args,key:(actual.append({'args':args,'key':key}) or {'saved':args['v']}),'side_effect':True}
        call={'type':'function_call','call_id':'save-1','name':'commit','arguments':'{"v":17}'}
        outcomes=[]
        for index in range(2 if ident=='E04' else 1):
            ledger=t.EffectLedger(str(tmp/'effects.db'));responses=iter([{'status':'completed','output':[call]},{'status':'completed','output':[message('Saved.')]}])
            try:
                try:outcomes.append(t.run_loop(lambda request:next(responses),[],{'commit':tool},'tenant-A','task-1',ledger,authorize,cancelled=lambda:cancel[0]))
                except RuntimeError as exc:outcomes.append({'error':str(exc)})
            finally:ledger.close()
        ev.update(input={'call':call,'fresh_loop_invocations':2 if ident=='E04' else 1},results=outcomes,effects=actual,authorization_calls=len(auth))
        if ident=='E04':expect(len(actual)==1 and all(o['status']=='completed' for o in outcomes),'effect replay duplicated handler or lost result')
        else:expect(not actual and outcomes==[{'error':'cancelled'}],'authorization cancellation dispatched effect')
    elif ident=='E06':
        actual=[];key='external-order-1';request={'task':'job','order':17}
        def uncertain(k):actual.append(k);raise RuntimeError('simulated crash after remote effect')
        ledger=t.EffectLedger(str(tmp/'effects.db'))
        try:
            try:ledger.perform('tenant-A',key,request,uncertain)
            except RuntimeError as exc:ev['first_exception']=str(exc)
        finally:ledger.close()
        ledger=t.EffectLedger(str(tmp/'effects.db'))
        try:
            try:ev['retry_result']=ledger.perform('tenant-A',key,request,lambda k:actual.append(k))
            except t.ReconciliationRequired as exc:ev['recovery_exception']=str(exc)
            ledger.reconcile('tenant-A',key,{'remote_id':'confirmed-17'},'remote GET /orders/external-order-1 returned completed')
            result=ledger.perform('tenant-A',key,request,lambda k:actual.append(k));ev.update(input=request,effects=actual,result=result)
            expect(len(actual)==1 and 'recovery_exception' in ev and result=={'remote_id':'confirmed-17'},'unknown replay or reconciled result wrong')
        finally:ledger.close()
    elif ident in ('E07','E08'):
        items=[message('child draft','/root/helper')]
        if ident=='E08':items.append(message('root decision','/root'))
        result=r.normalize({'status':'completed','output':items});ev.update(input={'status':'completed','output':items},result=result)
        expect(result['output_items']==items,'raw items lost')
        expect(result['final_text']==('root decision' if ident=='E08' else '') and result['answer_complete']==(ident=='E08'),'child final exposed as user final')
    elif ident=='E09':
        unknown={'type':'future_hosted_item','opaque':{'bytes':'keep-23'}}
        output=[message('child draft','/root/helper'),message('Root progress.','/root','commentary'),unknown]
        events=[{'type':'response.output_item.added','output_index':0,'item':output[0]}, {'type':'response.output_text.delta','output_index':0,'delta':'child draft'}, {'type':'response.output_item.added','output_index':1,'item':output[1]}, {'type':'response.output_text.delta','output_index':1,'delta':'Root progress.'}, {'type':'response.completed','response':{'status':'completed','output':output}}]
        result=r.terminal_stream(events);ev.update(input=events,result=result)
        expect(result['display_deltas']=='Root progress.' and result['raw_events']==events and result['output_items'][-1]==unknown,'stream leaked child or lost opaque evidence')
    elif ident in ('E10','E18'):
        if ident=='E10':
            events=[{'type':'response.output_item.added','output_index':0,'agent':{'agent_name':'/root'},'item':message('secret','/root/helper')},{'type':'response.output_text.delta','output_index':0,'delta':'secret'}]
        else:
            events=[{'type':'response.output_item.added','output_index':0,'item':message('secret','/root')},{'type':'response.output_text.delta','output_index':0,'delta':'secret'},{'type':'response.completed','response':{'status':'completed','output':[message('secret','/root/helper')]}}]
        ev['input']=events
        try:ev['result']=r.terminal_stream(events)
        except ValueError as exc:ev['rejected']=str(exc);return
        raise AssertionError('conflicting attribution accepted')
    elif ident=='E11':
        items=[{'type':'multi_agent_call','call_id':'hosted-1','action':'spawn_agent'},{'type':'future_hosted_item','opaque':[17,{'bytes':'same'}]}]
        value={'status':'completed','output':items};normalized=r.normalize(value)
        ledger=t.EffectLedger(str(tmp/'effects.db'));auth=[]
        try:result=t.run_loop(lambda request:value,[],{},'tenant-A','hosted-job',ledger,lambda *args:auth.append(args))
        finally:ledger.close()
        ev.update(input=value,result=result,normalized=normalized,authorization_calls=len(auth))
        expect(normalized['output_items']==items and result['history']==items and result['tool_calls']==0 and not auth,'hosted/unknown content lost or dispatched')
    elif ident=='E12':
        events=[{'type':'response.output_text.delta','delta':'Partial only.'}];result=r.terminal_stream(events);ev.update(input=events,result=result)
        expect(result['status']=='disconnected' and result['scorable_transport'] is False and result['display_deltas']=='Partial only.','partial stream accepted as completion')
    elif ident in ('E13','E14','E15'):
        w=load(root,'workflow_contract')
        if ident=='E15':
            spec={'tenant_id':'tenant-A','run_id':'cli-1','items':[{'id':'a'}],'stages':[{'id':'read'},{'id':'verify','depends_on':['read']},{'id':'combine','scope':'aggregate','depends_on':['verify']}],'limits':{'max_attempts':3,'timeout_s':120}}
            path=tmp/'spec.json';path.write_text(json.dumps(spec));db=tmp/'stages.db';base=[sys.executable,'-B',str(root/'scripts/workflow_contract.py'),'--spec',str(path),'--db',str(db)];calls=[]
            for suffix in ([],['--execute-demo'],['--execute-demo']):
                argv=base+suffix;proc=subprocess.run(argv,text=True,capture_output=True);calls.append({'argv':argv,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'journal_exists_after':db.exists()});expect(proc.returncode==0,'CLI failed')
            ev.update(input=spec,calls=calls)
            expect(not calls[0]['journal_exists_after'] and json.loads(calls[0]['stdout'])['execution'] is False,'plan created journal')
            a,b=[json.loads(c['stdout']) for c in calls[1:]];expect(a['status']=='completed' and b['attempts']==a['attempts']==3,'CLI resume repeated work')
            return
        spec={'tenant_id':'tenant-A','run_id':'stage-1','items':[{'id':'a'},{'id':'b'}],'stages':[{'id':'read'},{'id':'verify','depends_on':['read']},{'id':'combine','scope':'aggregate','depends_on':['verify']}],'limits':{'max_attempts':2 if ident=='E14' else 12,'timeout_s':120}}
        calls=[];aggregate=[]
        def work(ctx):
            calls.append([ctx['stage'],ctx['item_id']])
            if ctx['stage']=='combine':aggregate.append(copy.deepcopy(ctx))
            return {'status':'failed' if ident=='E13' and ctx['stage']=='read' and ctx['item_id']=='b' else 'succeeded','output':ctx['item_id']}
        handlers={s['id']:work for s in spec['stages']};engine=w.Workflow(spec,tmp/'workflow.db')
        try:first=engine.run(handlers,lambda ctx:None)
        finally:engine.close()
        first_calls=copy.deepcopy(calls);engine=w.Workflow(spec,tmp/'workflow.db')
        try:second=engine.run(handlers,lambda ctx:None);rows=engine.rows()
        finally:engine.close()
        ev.update(input=spec,calls=calls,first=first,second=second,rows=rows,aggregate_context=aggregate)
        expect(calls==first_calls,'resume repeated succeeded/blocked work')
        if ident=='E13':expect(calls==[['read','a'],['read','b'],['verify','a'],['combine','__aggregate__']] and first['coverage']==.5 and first['uncovered_ids']==['b'] and aggregate[0]['coverage']['uncovered_ids']==['b'],'stage dependency or population gap lost')
        else:expect(calls==[['read','a'],['read','b']] and first['attempts']==second['attempts']==2 and second['remaining_attempts']==0 and second['stop_reason']=='attempt_budget','resume reset attempt budget')
    elif ident=='E16':
        c=load(root,'cache_diagnostics');value={'request_prompt_cache_options':{'comparison_response_id':'baseline-7'},'prompt_cache_diagnostics':{'type':'cache_hit'},'usage':{'input_tokens_details':{'cached_tokens':0}}}
        result=c.analyze(value,'baseline-7');mismatch=c.analyze(value,'wrong');absent=c.analyze({});path=tmp/'capture.json';path.write_text(json.dumps(value));argv=[sys.executable,'-B',str(root/'scripts/cache_diagnostics.py'),str(path),'--comparison-id','baseline-7'];proc=subprocess.run(argv,capture_output=True,text=True)
        ev.update(input=value,result=result,mismatch=mismatch,absent=absent,cli={'argv':argv,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
        expect(result['status']=='observed' and result['reported_cached_tokens']==0 and result['billing_cost_usd'] is None and mismatch['status']=='inconclusive' and absent['status']=='not_measured' and proc.returncode==0 and json.loads(proc.stdout)==result,'cache diagnostic mistaken for usage/billing/evidence')
    elif ident=='E17':
        c=load(root,'cache_diagnostics');observations=[{'id':'x','target_present':False,'check_applied':True,'same_scope':True,'violations':0,'evidence':'HTTP 200'}];result=c.probe_coverage(observations,['x','y']);ev.update(input={'observations':observations,'required_ids':['x','y']},result=result)
        expect(result['status']=='inconclusive' and result['measured']==0 and result['coverage']==0 and result['required']==2,'unexposed zero-defect probe passed')

def main():
    p=argparse.ArgumentParser();p.add_argument('--skill-root',type=Path,required=True);p.add_argument('--label',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.skill_root.resolve();here=Path(__file__).parent
    protocol=json.loads((here/'protocol.json').read_text());cases=[]
    for case in protocol['cases']:
        evidence={};status='passed';error=None
        with tempfile.TemporaryDirectory(prefix='amind-engineering-contrast-') as temp:
            try:execute(root,case['id'],evidence,Path(temp))
            except Unsupported as exc:status='unsupported';error=str(exc)
            except BaseException as exc:status='failed';error=f'{type(exc).__name__}: {exc}';evidence['traceback']=traceback.format_exc()
        cases.append({**case,'status':status,'error':error,'evidence':evidence})
    files={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob('*')) if path.is_file() and '__pycache__' not in path.parts}
    result={'label':a.label,'skill_root':str(root),'protocol_sha256':hashlib.sha256((here/'protocol.json').read_bytes()).hexdigest(),'invocation':sys.argv,'package_files_sha256':files,'summary':{state:sum(c['status']==state for c in cases) for state in ['passed','failed','unsupported']},'common_quality_summary':{state:sum(c['status']==state and c['stratum']!='capability' for c in cases) for state in ['passed','failed','unsupported']},'cases':cases,'evidence_level':'Offline public module/CLI execution; no model/network/provider evidence'}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['label','summary','common_quality_summary']}))
if __name__=='__main__':main()
