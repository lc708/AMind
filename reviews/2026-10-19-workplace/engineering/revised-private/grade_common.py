"""Privileged grader utilities. Candidate code is executed only in subprocesses."""
import argparse,collections,json,os,subprocess,sys,tempfile
from pathlib import Path

def require(condition,message):
    if not condition:raise AssertionError(message)
class Session:
    def __init__(self,repo,module):
        self.repo=repo;self.module=module;self.counter=0;self.calls=[]
        base=Path(os.environ.get('AMIND_GRADER_SCRATCH',str(repo.parent)))
        base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='integration-',dir=str(base));self.path=Path(self.temp.name).resolve()
        self.db=self.path/'jobs.sqlite';self.receipts=self.path/'receipts.jsonl'
    def close(self):self.temp.cleanup()
    def call(self,value,expected=0):
        self.counter+=1;source=self.path/f'input-{self.counter}.json';source.write_text(json.dumps(value));out=self.path/f'view-{self.counter}.json'
        prefix=json.loads(os.environ.get('AMIND_APP_COMMAND_PREFIX_JSON','[]'))
        require(isinstance(prefix,list) and all(isinstance(v,str) for v in prefix),'invalid application command prefix')
        argv=prefix+[sys.executable,'-B','-m',self.module]
        argv+=['--capture',str(source),'--out',str(out)] if self.module=='gateway' else ['--db',str(self.db),'--request',str(source),'--receipts',str(self.receipts)]
        p=subprocess.run(argv,cwd=self.repo,text=True,capture_output=True,timeout=8)
        record={'argv':argv,'returncode':p.returncode,'stdout':p.stdout[:4000],'stderr':p.stderr[:2000]};self.calls.append(record)
        require(p.returncode==expected,f'CLI exit {p.returncode}, expected {expected}')
        if expected==17:return None
        require(len(p.stdout)<1000000,'oversized CLI response');envelope=json.loads(p.stdout)
        if expected==2:
            require(isinstance(envelope,dict) and isinstance(envelope.get('error'),str),'controlled JSON error required')
            if self.module=='gateway':require(not out.exists(),'invalid capture published client artifact')
            return envelope
        result=json.loads(out.read_text()) if self.module=='gateway' else envelope
        return result
    def received(self):
        return [json.loads(line) for line in self.receipts.read_text().splitlines() if line] if self.receipts.exists() else []

def run(task,module,probes):
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();repo=a.repo.resolve();rows=[];domains=collections.defaultdict(lambda:{'score':0,'max_score':0});guards={}
    for ident,domain,fatal,fn in probes:
        session=Session(repo,module);ok=False;error=None
        try:fn(session);ok=True
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        row={'id':ident,'domain':domain,'score':int(ok),'max_score':1,'passed':ok,'fatal':fatal,'error':error,'calls':session.calls};rows.append(row)
        if hasattr(session,'observations'):row['observations']=session.observations
        domains[domain]['score']+=int(ok);domains[domain]['max_score']+=1
        if fatal:guards[ident]=ok
        session.close()
    domain_scores={name:{'score':int(d['score']==d['max_score']),'max_score':1,'probe_passed':d['score'],'probe_total':d['max_score']} for name,d in domains.items()}
    grade={'task_id':task,'score':sum(d['score'] for d in domain_scores.values()),'max_score':len(domain_scores),'probe_passed':sum(r['score'] for r in rows),'probe_total':len(rows),'domain_scores':domain_scores,'domains':dict(domains),'fatal_guardrails':guards,'fatal_pass':all(guards.values()),'cases':rows,'evidence_level':'offline real CLI subprocesses and persisted journals; no provider/model/network'}
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(grade,indent=2)+'\n')
    print(json.dumps(grade))
