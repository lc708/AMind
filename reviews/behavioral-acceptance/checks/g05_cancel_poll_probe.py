"""Reviewer follow-up, same logical cancelled/unknown scenario for both artifacts.
Not an independent agent rerun. No network, writes confined to temporary DBs.
"""
from pathlib import Path
import importlib.util,json,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
OP={'tenant':'t1','task':'job1','call_id':'c1','action':'charge','amount':20}

def load(runid):
    spec=importlib.util.spec_from_file_location(runid,ROOT/'artifacts'/runid/'recovery.py')
    module=importlib.util.module_from_spec(spec);sys.modules[runid]=module;spec.loader.exec_module(module);return module

results={}
with tempfile.TemporaryDirectory(prefix='amind-cancel-poll-') as scratch:
    root=Path(scratch)
    for runid in ('R01','R05'):
        m=load(runid); clock=[0.0]
        if runid=='R01':
            remote=m.FixedRemote(root/(runid+'-remote.db'),charge_fault='before_timeout')
            service=m.Recovery(root/(runid+'-local.db'),remote,lambda:clock[0])
            principal=m.Context('t1','job1',True,True)
            service.execute(principal,OP);service.cancel(principal,OP)
            for i in range(12):
                clock[0]=100.0*(i+1);outcome=service.execute(principal,OP)
            results[runid]={'poll_invocations':12,'charge_calls':remote.charge_calls,'lookup_calls':remote.lookup_calls,'effects':remote.count(),'state':outcome['state'],'automatic_halted':outcome['manual_review']}
            service.close();remote.close()
        else:
            remote=m.MockRemote(root/(runid+'-remote.db'));remote.mode='before_timeout'
            service=m.Recovery(root/(runid+'-local.db'),remote,clock=lambda:clock[0]);principal=m.Principal('t1',frozenset({'job1'}))
            service.run(OP,principal);service.cancel(OP,principal)
            for i in range(12):
                clock[0]=100.0*(i+1);outcome=service.run(OP,principal)
            results[runid]={'poll_invocations':12,'charge_calls':remote.counts()['charge'],'lookup_calls':remote.counts()['lookup'],'effects':remote.counts()['effects'],'state':outcome['state'],'automatic_halted':outcome['state']=='manual_review'}
print(json.dumps({'scope':'Local reviewer probe of original artifacts, after initial tasks; not new agent work','results':results},indent=2))
