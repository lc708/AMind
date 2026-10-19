#!/usr/bin/env python3
"""Independent offline product diagnostics; no workplace target runs read.

Only imports product public modules, calls their public APIs, and writes to this
reproduction's temporary journal/receipt paths. It does not call a model/network.
"""
import argparse,hashlib,importlib.util,json,os,subprocess,sys,tempfile,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def load(root,name):
    p=root/'scripts'/f'{name}.py'
    if not p.exists():return None
    spec=importlib.util.spec_from_file_location('diagnostic_'+name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n');f.flush();os.fsync(f.fileno())

def workflow_alias(root,tmp,alias):
    m=load(root,'workflow_contract')
    if m is None:return {'supported':False,'reason':'old package has no equivalent staged Workflow public entry'}
    spec={'tenant_id':'tenant-north','run_id':'delivery-79','items':[{'id':'invoice-1'}],
          'stages':[{'id':'deliver'}],'limits':{'max_attempts':3,'timeout_s':60}}
    path=tmp/'delivery.sqlite';engine=m.Workflow(spec,path);otherpath=tmp/'active.sqlite'
    if alias:otherpath.symlink_to(path)
    else:otherpath=path
    control={};receipt={'receipt_id':'receiver-79','delivered':True}
    def deliver(context):
        # The receiver has accepted the effect; the worker is still validating
        # the resulting artifact and has not returned a settled handler outcome.
        append(tmp/'receipts.jsonl',{'event':'receiver_accepted','operation_key':context['operation_key'],**receipt})
        other=m.Workflow(spec,otherpath)
        try:
            try:
                other.reconcile('deliver','invoice-1','succeeded',receipt,'Receiver receipt receiver-79 observed in receipts.jsonl')
                control['reconcile_accepted_while_handler_active']=True
                control['report_during_active_handler']=other.report()
            except RuntimeError as exc:control.update(reconcile_accepted_while_handler_active=False,rejection=str(exc))
        finally:other.close()
        append(tmp/'receipts.jsonl',{'event':'handler_validation_finished','operation_key':context['operation_key']})
        return {'status':'succeeded','output':{**receipt,'validation':'passed'}}
    try:final=engine.run({'deliver':deliver},lambda context:None);rows=engine.rows()
    finally:engine.close()
    return {'supported':True,'uses_symlink_file_alias':alias,'active_path':str(path),'recovery_path':str(otherpath),'paths_same_file':os.path.samefile(path,otherpath),'observed':control,'final':final,'final_rows':rows,'receipts':[json.loads(x) for x in (tmp/'receipts.jsonl').read_text().splitlines()]}

def response_dispatch(root,tmp,error_status):
    loop=load(root,'tool_loop');normalizer=load(root,'response_contract');ledger=loop.EffectLedger(str(tmp/'effects.sqlite'));receipts=[];requests=[]
    bad={'id':'r-contradictory','status':error_status,'error':{'code':'provider_adapter_failure'},'output':[{'type':'function_call','call_id':'send-79','name':'send_invoice','arguments':'{"invoice":"79"}'}]}
    final={'status':'completed','output':[{'type':'message','phase':'final_answer','content':[{'type':'output_text','text':'Invoice sent.'}]}]}
    normalization={}
    try:normalization['result']=normalizer.normalize(bad)
    except ValueError as exc:normalization['rejection']=str(exc)
    def saved_adapter(request):
        requests.append(request);return bad if len(requests)==1 else final
    def send(args,key):
        receipt={'invoice':args['invoice'],'operation_key':key,'receipt_id':'sent-79'};receipts.append(receipt);append(tmp/'receipts.jsonl',receipt);return receipt
    tool={'schema':{'type':'function','name':'send_invoice'},'validate':lambda args:None,'handler':send,'side_effect':True}
    try:
        try:result=loop.run_loop(saved_adapter,[],{'send_invoice':tool},'tenant-north','invoice-79',ledger,lambda *args:None)
        except Exception as exc:result={'exception':type(exc).__name__,'message':str(exc)}
    finally:ledger.close()
    return {'supported':True,'adapter_kind':'fixed offline captured response callable, not a model client','provider_fixture':bad,'normalizer':normalization,'loop_result':result,'actual_side_effect_receipts':receipts,'adapter_invocations':len(requests)}

def ledger_active(root,tmp):
    m=load(root,'tool_loop');path=tmp/'effects.sqlite';worker=m.EffectLedger(str(path));key=m.operation_key('north','invoice-79','deliver');request={'invoice':'79'};receipt={'receipt_id':'receiver-79'};observed={}
    def handler(operation):
        append(tmp/'receipts.jsonl',receipt)
        controller=m.EffectLedger(str(path))
        try:
            controller.reconcile('north',key,{**receipt,'verified_by':'receipt-controller'},'Actual receiver-79 receipt observed in receipts.jsonl')
            observed['cached_after_reconcile']=controller.perform('north',key,request,lambda k:(_ for _ in ()).throw(AssertionError('must not redeliver')))
        finally:controller.close()
        return {**receipt,'verified_by':'late-worker'}
    try:
        observed['handler_result']=worker.perform('north',key,request,handler)
        observed['cached_after_late_handler_commit']=worker.perform('north',key,request,lambda k:(_ for _ in ()).throw(AssertionError('must not redeliver')))
        observed['reconciliation_audit']=[json.loads(row[0]) for row in worker.db.execute('SELECT evidence FROM reconciliations')]
    finally:worker.close()
    return {'supported':True,'observed':observed,'receipts':[json.loads(x) for x in (tmp/'receipts.jsonl').read_text().splitlines()]}

def ledger_crash_child(root,tmp):
    m=load(root,'tool_loop');ledger=m.EffectLedger(str(tmp/'effects.sqlite'));key=m.operation_key('north','invoice-79','deliver')
    def handler(k):append(tmp/'receipts.jsonl',{'receipt_id':'receiver-crash-79'});os._exit(17)
    ledger.perform('north',key,{'invoice':'79'},handler)

def ledger_crash_control(root,tmp):
    argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker','crash-child','--skill-root',str(root),'--scratch',str(tmp)]
    process=subprocess.run(argv,capture_output=True,text=True,timeout=10);m=load(root,'tool_loop');ledger=m.EffectLedger(str(tmp/'effects.sqlite'));key=m.operation_key('north','invoice-79','deliver');obs={'child_returncode':process.returncode,'child_argv':argv}
    try:
        try:ledger.perform('north',key,{'invoice':'79'},lambda k:append(tmp/'receipts.jsonl',{'unexpected':'duplicate'}))
        except m.ReconciliationRequired as exc:obs['replay_refused']=str(exc)
        ledger.reconcile('north',key,{'receipt_id':'receiver-crash-79'},'Actual persisted receiver-crash-79 receipt checked after worker exit17')
        obs['reused']=ledger.perform('north',key,{'invoice':'79'},lambda k:append(tmp/'receipts.jsonl',{'unexpected':'duplicate'}))
    finally:ledger.close()
    return {'supported':True,'observed':obs,'receipts':[json.loads(x) for x in (tmp/'receipts.jsonl').read_text().splitlines()]}

FUNCTIONS={'workflow-alias':lambda r,t:workflow_alias(r,t,True),'workflow-samepath-control':lambda r,t:workflow_alias(r,t,False),'contradictory-response-dispatch':lambda r,t:response_dispatch(r,t,'completed'),'failed-response-control':lambda r,t:response_dispatch(r,t,'failed'),'ledger-active-reconcile':ledger_active,'ledger-crash-control':ledger_crash_control}
def main():
    p=argparse.ArgumentParser();p.add_argument('--worker');p.add_argument('--skill-root',type=Path);p.add_argument('--scratch',type=Path);p.add_argument('--output',type=Path,default=HERE/'evidence.json');a=p.parse_args()
    if a.worker:
        if a.worker=='crash-child':ledger_crash_child(a.skill_root,a.scratch)
        else:print(json.dumps(FUNCTIONS[a.worker](a.skill_root,a.scratch),ensure_ascii=False))
        return
    roots={'old-0.2.1':ROOT/'.codex-tmp/contrast-2026-10-18/old/skills/amind-engineering','current-0.3.1':ROOT/'skills/amind-engineering'};rows=[]
    for version,root in roots.items():
        for ident in FUNCTIONS:
            with tempfile.TemporaryDirectory(prefix='product-diagnostic-') as tmp:
                scratch=Path(tmp).resolve();argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker',ident,'--skill-root',str(root),'--scratch',str(scratch)]
                process=subprocess.run(argv,capture_output=True,text=True,timeout=15);row={'version':version,'case':ident,'argv':argv,'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr}
                if process.returncode==0:row['result']=json.loads(process.stdout)
                rows.append(row)
    hashes={version:{name:hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest() if (root/'scripts'/name).exists() else None for name in ['workflow_contract.py','tool_loop.py','response_contract.py']} for version,root in roots.items()}
    result={'scope':'Independent post-freeze product diagnostics, not workplace/model task evidence. No target runs/captures read; no product edits/model/network calls.','product_files_sha256':hashes,'cases':rows};a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for row in rows:
        result=row.get('result',{});print(json.dumps({'version':row['version'],'case':row['case'],'returncode':row['returncode'],'supported':result.get('supported'),'observed':result.get('observed'),'effects':len(result.get('actual_side_effect_receipts',[]))},ensure_ascii=False))
if __name__=='__main__':main()
