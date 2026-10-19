#!/usr/bin/env python3
"""Build offline workplace fixtures, before any target-agent trial."""
from pathlib import Path
import json, shutil, textwrap
BASE=Path(__file__).resolve().parent

def put(root,name,content):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(textwrap.dedent(content).lstrip('\n'))
def blob(root,name,value):put(root,name,json.dumps(value,indent=2)+'\n')

good=BASE/'private/reference/gateway';starter=BASE/'tasks/E-GATEWAY/repo'
for root in [good,starter]:
 put(root,'gateway/__init__.py','')
 put(root,'gateway/__main__.py','''
 import argparse,json,sys
 from pathlib import Path
 from .replay import replay
 def main():
     p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
     try:result=replay(json.loads(a.capture.read_text()))
     except (ValueError,TypeError,KeyError) as exc:
         print(json.dumps({'error':str(exc)}));return 2
     a.out.write_text(json.dumps(result,ensure_ascii=False));print(json.dumps({'written':str(a.out)}));return 0
 if __name__=='__main__':sys.exit(main())
 ''')
 put(root,'gateway/render.py','''
 import html
 def render(text):
     return '<article>'+html.escape(text,quote=True)+'</article>'
 ''')
 put(root,'gateway/replay.py','''
 import copy
 from .projection import project
 def replay(capture):
     # Archive is an operations artifact. Only client is returned by our web route.
     client,items=project(capture)
     return {'client':client,'archive':{'events':copy.deepcopy(capture['events']),'output_items':copy.deepcopy(items)}}
 ''')
 put(root,'gateway/projection.py','''
 from .render import render
 TERMINALS={'response.completed':'completed','response.failed':'failed','response.incomplete':'incomplete','response.cancelled':'cancelled'}
 def owner(value):
     agent=value.get('agent')
     if agent is None:return None
     if not isinstance(agent,dict) or not isinstance(agent.get('agent_name'),str):raise ValueError('invalid attribution')
     return agent['agent_name']
 def project(capture):
     mode=capture.get('mode','single');events=capture.get('events')
     if mode not in ('single','multi_agent') or not isinstance(events,list):raise ValueError('invalid capture')
     owners={};deltas=[];terminal=None;failed=None
     for event in events:
         if not isinstance(event,dict):raise ValueError('event object required')
         if terminal is not None or failed is not None:raise ValueError('event after terminal')
         kind=event.get('type');outer=owner(event);inner=owner(event.get('item') or {})
         if outer is not None and inner is not None and outer!=inner:raise ValueError('conflicting event attribution')
         who=outer or inner;index=event.get('output_index')
         if who is not None and index is not None:
             if index in owners and owners[index]!=who:raise ValueError('stream ownership changed')
             owners[index]=who
         if kind=='response.output_text.delta':
             text=event.get('delta','')
             if not isinstance(text,str):raise ValueError('delta string required')
             deltas.append((index,who,text))
         elif kind in TERMINALS:
             terminal=event.get('response')
             if not isinstance(terminal,dict) or terminal.get('status')!=TERMINALS[kind]:raise ValueError('terminal status mismatch')
         elif kind=='error':failed=event
     items=terminal.get('output',[]) if terminal else []
     if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):raise ValueError('output item array required')
     multi=mode=='multi_agent' or bool(owners) or any(owner(i) is not None for i in items)
     for index,item in enumerate(items):
         who=owner(item)
         if who is not None:
             if index in owners and owners[index]!=who:raise ValueError('terminal ownership changed')
             owners[index]=who
     display=''.join(text for index,who,text in deltas if not multi or (who or owners.get(index))=='/root')
     final=[];refusal=False;pending=False
     for item in items:
         if item.get('type')=='function_call':pending=True
         if item.get('type')!='message':continue
         if multi and owner(item)!='/root':continue
         phase=item.get('phase')
         if phase!='final_answer' and not(not multi and phase is None):continue
         for content in item.get('content',[]):
             if content.get('type')=='output_text':final.append(content.get('text',''))
             elif content.get('type')=='refusal':refusal=True
     status=terminal['status'] if terminal else ('stream_error' if failed else 'disconnected')
     if terminal and status=='completed' and (terminal.get('error') is not None or terminal.get('incomplete_details') is not None):raise ValueError('contradictory completed response')
     final_text=''.join(final)
     return {'status':status,'display_text':display,'final_text':final_text,
             'answer_complete':status=='completed' and not pending and bool(final_text or refusal),
             'html':render(final_text or display)},items
 ''')
 # Healthy baseline checks deliberately cover supported single-agent traffic.
 put(root,'tests/test_public.py','''
 import json,subprocess,sys,tempfile,unittest
 from pathlib import Path
 class PublicGatewayTests(unittest.TestCase):
     def call(self,capture):
         with tempfile.TemporaryDirectory() as t:
             source=Path(t)/'capture.json';out=Path(t)/'out.json';source.write_text(json.dumps(capture))
             p=subprocess.run([sys.executable,'-m','gateway','--capture',str(source),'--out',str(out)],capture_output=True,text=True)
             self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(out.read_text())
     def test_legacy_final(self):
         item={'type':'message','content':[{'type':'output_text','text':'Order received.'}]}
         result=self.call({'mode':'single','events':[{'type':'response.completed','response':{'status':'completed','output':[item]}}]})
         self.assertEqual(result['client']['final_text'],'Order received.')
     def test_partial_capture_is_retained(self):
         events=[{'type':'response.output_text.delta','delta':'Working'}]
         result=self.call({'mode':'single','events':events})
         self.assertEqual(result['archive']['events'],events);self.assertFalse(result['client']['answer_complete'])
     def test_empty_success_has_no_answer(self):
         result=self.call({'mode':'single','events':[{'type':'response.completed','response':{'status':'completed','output':[]}}]})
         self.assertFalse(result['client']['answer_complete'])
 if __name__=='__main__':unittest.main()
 ''')
 put(root,'README.md','''
 # Response desk gateway
 This offline gateway replays recorded Responses traffic into the browser-facing
 support desk view and a separate operations archive. Python standard library only.
 Run: `python -m gateway --capture traces/incident.json --out /tmp/view.json`.
 Public checks: `python -m unittest discover -s tests`.

 ## Incident 418: internal notes reached customer sessions
 After hosted workers were enabled, staff saw research notes in the customer reply
 pane. A reconnect also showed a reassuring completed badge for an unfinished reply.
 A transcript from the new workflow is saved in `traces/incident.json`. The old
 single-agent path and its tests are still in use. Repair the integration across
 replay, projection and presentation; leave the public CLI compatible. Add useful
 regression tests and explain the cause and verification in `PATCH-NOTES.md`.

 ## Public contract
 Capture JSON has `mode` (single or multi_agent) and ordered `events`. A message's
 `agent.agent_name` identifies its owner; `/root` owns the customer conversation.
 Item-added events associate `output_index` with an owner for later text deltas.
 A final answer in multi-agent traffic requires an explicit root `final_answer`.
 Unattributed multi-agent text is retained for operations, not guessed as root text.
 Legacy single-agent messages without a phase remain supported. Commentary may
 appear as progress but cannot turn into a final answer. A completed transport
 alone is insufficient while a developer function call is pending.

 CLI writes `{client,archive}` JSON. `client` has status, display_text, final_text,
 answer_complete and html (an article element containing safely escaped visible
 text). Only this object goes to the browser. `archive.events` and
 `archive.output_items` preserve captured data exactly, including unknown hosted
 item types. No captured item triggers local tools or code execution.
 Terminal events are completed/failed/incomplete/cancelled and must agree with
 response.status. A missing terminal stays disconnected, or stream_error after an
 error event. Contradictory terminal data or inconsistent attribution is a capture
 error: return exit 2 with JSON `{error:...}` and do not publish a new output file.
 Calls are offline; there is no provider SDK, network, or credential setup to add.
 ''')
 def msg(text,agent,phase):return {'type':'message','agent':{'agent_name':agent},'phase':phase,'content':[{'type':'output_text','text':text}]}
 capture={'mode':'multi_agent','events':[{'type':'response.output_item.added','output_index':0,'item':msg('Internal draft','/root/search','final_answer')},{'type':'response.output_text.delta','output_index':0,'delta':'Internal draft'},{'type':'response.output_item.added','output_index':1,'item':msg('Checking your request.','/root','commentary')},{'type':'response.output_text.delta','output_index':1,'delta':'Checking your request.'},{'type':'response.completed','response':{'status':'completed','output':[msg('Internal draft','/root/search','final_answer'),msg('Checking your request.','/root','commentary'),{'type':'agent_message','opaque':{'receipt':'h-418'}}]}}]}
 blob(root,'traces/incident.json',capture)
 blob(root,'traces/legacy.json',{'mode':'single','events':[{'type':'response.completed','response':{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Order received.'}]}]}}]})
# The starter is a plausible pre-hosted implementation, not an assertion oracle.
put(starter,'gateway/projection.py','''
from .render import render
TERMINALS={'response.completed':'completed','response.failed':'failed','response.incomplete':'incomplete','response.cancelled':'cancelled'}
def project(capture):
    events=capture['events'];display=[];terminal=None;status='disconnected'
    for event in events:
        if event.get('type')=='response.output_text.delta':display.append(event.get('delta',''))
        if event.get('type') in TERMINALS:
            terminal=event.get('response') or {};status=TERMINALS[event['type']]
        elif event.get('type')=='error':status='stream_error'
    items=(terminal or {}).get('output',[]);final=[]
    for item in items:
        if item.get('type')!='message':continue
        if item.get('phase') not in (None,'final_answer'):continue
        final.extend(c.get('text','') for c in item.get('content',[]) if c.get('type')=='output_text')
    final_text=''.join(final);display_text=''.join(display)
    return {'status':status,'display_text':display_text,'final_text':final_text,
            'answer_complete':status=='completed' and bool(final_text),
            'html':render(final_text or display_text)},items
''')
put(starter,'gateway/render.py',"def render(text):\n    return '<article>'+text+'</article>'\n")
put(starter,'gateway/replay.py','''
import copy
from .projection import project
SUPPORTED={'message','reasoning','function_call','web_search_call'}
def replay(capture):
    client,items=project(capture)
    # The archive predates hosted tool items; old readers only accept these types.
    archived=[i for i in items if i.get('type') in SUPPORTED]
    return {'client':client,'archive':{'events':copy.deepcopy(capture['events']),'output_items':archived}}
''')
print('gateway repositories built')
good=BASE/'private/reference/durable';starter=BASE/'tasks/E-DURABLE/repo'
for root in [good,starter]:
 put(root,'intake/__init__.py','')
 put(root,'intake/__main__.py','''
 import argparse,json,sys
 from pathlib import Path
 from .store import Store
 from .service import handle
 def main():
     p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--receipts',type=Path,required=True);a=p.parse_args()
     store=None
     try:
         request=json.loads(a.request.read_text());store=Store(a.db);answer=handle(store,request,a.receipts)
         print(json.dumps(answer));return 0
     except (ValueError,KeyError,TypeError) as exc:
         print(json.dumps({'error':str(exc)}));return 2
     finally:
         if store:store.close()
 if __name__=='__main__':sys.exit(main())
 ''')
 put(root,'intake/store.py','''
 import hashlib,json,sqlite3
 def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
 def operation_key(tenant,job,stage,item):return hashlib.sha256(packed([tenant,job,stage,item]).encode()).hexdigest()
 class Store:
     def __init__(self,path):
         self.db=sqlite3.connect(str(path),isolation_level=None)
         self.db.execute('PRAGMA journal_mode=WAL')
         self.db.execute('CREATE TABLE IF NOT EXISTS jobs(tenant TEXT,job TEXT,spec TEXT,cancelled INTEGER,attempts INTEGER,PRIMARY KEY(tenant,job))')
         self.db.execute('CREATE TABLE IF NOT EXISTS work(tenant TEXT,job TEXT,stage TEXT,item TEXT,state TEXT,result TEXT,operation_key TEXT,PRIMARY KEY(tenant,job,stage,item))')
     def close(self):self.db.close()
     def job(self,tenant,job):
         row=self.db.execute('SELECT spec,cancelled,attempts FROM jobs WHERE tenant=? AND job=?',(tenant,job)).fetchone()
         if row is None:raise ValueError('job not found for tenant')
         return {'spec':json.loads(row[0]),'cancelled':bool(row[1]),'attempts':row[2]}
     def rows(self,tenant,job):
         return [dict(zip(('stage','item','state','result','operation_key'),r)) for r in self.db.execute('SELECT stage,item,state,result,operation_key FROM work WHERE tenant=? AND job=? ORDER BY rowid',(tenant,job))]
     def update(self,tenant,job,stage,item,state,result=None):
         self.db.execute('UPDATE work SET state=?,result=? WHERE tenant=? AND job=? AND stage=? AND item=?',(state,packed(result),tenant,job,stage,item))
 ''')
 put(root,'intake/receiver.py','''
 import json,os
 def perform(context,path):
     # Simulated external receiver. Every invocation is observable, even on crash.
     payload=context.get('payload') or {};stage=context['stage']
     outcome={'status':'failed' if payload.get(stage)=='fail' else 'succeeded','output':{'item':context['item'],'stage':stage}}
     receipt={**context,'outcome':outcome}
     with path.open('a') as f:
         f.write(json.dumps(receipt)+'\\n');f.flush();os.fsync(f.fileno())
     if payload.get('crash_after_effect')==stage:os._exit(17)
     return outcome
 ''')
 put(root,'intake/service.py','''
 import json
 from .store import operation_key,packed
 from .receiver import perform
 STAGES=('inspect','review','summary')
 def validate(spec):
     items=spec.get('items');limit=spec.get('max_attempts')
     if not isinstance(items,list) or not items:raise ValueError('nonempty item population required')
     ids=[i.get('id') for i in items if isinstance(i,dict)]
     if len(ids)!=len(items) or any(not isinstance(i,str) or not i or i=='__all__' for i in ids) or len(set(ids))!=len(ids):raise ValueError('unique item IDs required')
     if type(limit) is not int or limit<1:raise ValueError('positive max_attempts required')
     return spec
 def report(store,tenant,job):
     entry=store.job(tenant,job);rows=store.rows(tenant,job);population=[i['id'] for i in entry['spec']['items']]
     covered=[i for i in population if all(any(r['stage']==stage and r['item']==i and r['state']=='succeeded' for r in rows) for stage in ('inspect','review'))]
     pending=any(r['state']=='pending' for r in rows);unknown=any(r['state']=='running' for r in rows)
     status='unknown' if unknown else ('pending' if pending else ('completed' if len(covered)==len(population) else 'incomplete'))
     if entry['cancelled']:status='cancelled'
     return {'tenant':tenant,'job':job,'status':status,'attempts':entry['attempts'],
             'remaining_attempts':max(0,entry['spec']['max_attempts']-entry['attempts']),
             'coverage':len(covered)/len(population),'covered_ids':covered,'uncovered_ids':[i for i in population if i not in covered],
             'cancelled':entry['cancelled'],'rows':rows}
 def submit(store,tenant,job,spec):
     spec=validate(spec)
     old=store.db.execute('SELECT spec FROM jobs WHERE tenant=? AND job=?',(tenant,job)).fetchone()
     if old:
         if json.loads(old[0])!=spec:raise ValueError('immutable job specification differs')
         return report(store,tenant,job)
     store.db.execute('BEGIN IMMEDIATE')
     try:
         store.db.execute('INSERT INTO jobs VALUES(?,?,?,0,0)',(tenant,job,packed(spec)))
         for stage in STAGES:
             for item in (['__all__'] if stage=='summary' else [i['id'] for i in spec['items']]):
                 store.db.execute('INSERT INTO work VALUES(?,?,?,?,?,?,?)',(tenant,job,stage,item,'pending',None,operation_key(tenant,job,stage,item)))
         store.db.execute('COMMIT')
     except BaseException:store.db.execute('ROLLBACK');raise
     return report(store,tenant,job)
 def work(store,tenant,job,receipts):
     for stage in STAGES:
         for row in [r for r in store.rows(tenant,job) if r['stage']==stage]:
             if row['state']!='pending':continue
             entry=store.job(tenant,job)
             if entry['cancelled'] or entry['attempts']>=entry['spec']['max_attempts']:return report(store,tenant,job)
             previous=[r for r in store.rows(tenant,job) if r['stage'] in ('inspect','review')]
             if stage=='review':
                 dependency=next(r for r in previous if r['stage']=='inspect' and r['item']==row['item'])
                 if dependency['state'] in ('running','pending'):continue
                 if dependency['state']!='succeeded':store.update(tenant,job,stage,row['item'],'not_covered');continue
             if stage=='summary' and any(r['state'] in ('running','pending') for r in previous):continue
             context={'tenant':tenant,'job':job,'stage':stage,'item':row['item'],'operation_key':row['operation_key'],
                      'payload':next((i.get('payload',{}) for i in entry['spec']['items'] if i['id']==row['item']),{}),
                      'coverage':report(store,tenant,job)}
             store.db.execute('BEGIN IMMEDIATE')
             try:
                 store.update(tenant,job,stage,row['item'],'running')
                 store.db.execute('UPDATE jobs SET attempts=attempts+1 WHERE tenant=? AND job=?',(tenant,job));store.db.execute('COMMIT')
             except BaseException:store.db.execute('ROLLBACK');raise
             outcome=perform(context,receipts)
             store.update(tenant,job,stage,row['item'],outcome['status'],outcome['output'])
     return report(store,tenant,job)
 def handle(store,request,receipts):
     tenant=request.get('tenant');job=request.get('job');op=request.get('op')
     if any(not isinstance(v,str) or not v for v in (tenant,job)):raise ValueError('trusted tenant and job identity required')
     if op=='submit':return submit(store,tenant,job,request['spec'])
     store.job(tenant,job)
     if op=='report':return report(store,tenant,job)
     if op=='work':return work(store,tenant,job,receipts)
     if op in ('cancel','resume'):
         store.db.execute('UPDATE jobs SET cancelled=? WHERE tenant=? AND job=?',(int(op=='cancel'),tenant,job));return report(store,tenant,job)
     if op=='reconcile':
         evidence=request.get('evidence');state=request.get('state')
         if not isinstance(evidence,str) or not evidence.strip() or state not in ('succeeded','failed'):raise ValueError('external outcome and evidence required')
         target=next((r for r in store.rows(tenant,job) if r['stage']==request.get('stage') and r['item']==request.get('item')),None)
         if target is None or target['state']!='running':raise ValueError('exactly one unknown operation required')
         store.update(tenant,job,target['stage'],target['item'],state,request.get('result'))
         return report(store,tenant,job)
     raise ValueError('unknown operation')
 ''')
 put(root,'tests/test_public.py','''
 import json,subprocess,sys,tempfile,unittest
 from pathlib import Path
 class IntakeTests(unittest.TestCase):
     def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
     def tearDown(self):self.t.cleanup()
     def call(self,op,**extra):
         req=self.p/'request.json';req.write_text(json.dumps({'op':op,'tenant':'acme','job':'J1',**extra}))
         p=subprocess.run([sys.executable,'-m','intake','--db',str(self.p/'jobs.db'),'--request',str(req),'--receipts',str(self.p/'receipts.jsonl')],capture_output=True,text=True)
         return p.returncode,json.loads(p.stdout)
     def test_submit_plans(self):
         rc,r=self.call('submit',spec={'items':[{'id':'a'}],'max_attempts':8});self.assertEqual(rc,0);self.assertEqual(r['coverage'],0)
     def test_small_job(self):
         self.call('submit',spec={'items':[{'id':'a'}],'max_attempts':8});rc,r=self.call('work');self.assertEqual(rc,0);self.assertEqual(r['status'],'completed')
     def test_population_required(self):
         rc,r=self.call('submit',spec={'items':[],'max_attempts':8});self.assertEqual(rc,2);self.assertIn('error',r)
 if __name__=='__main__':unittest.main()
 ''')
 put(root,'README.md','''
 # Intake desk
 A small multi-tenant back-office worker. It receives immutable jobs, inspects each
 selected item, reviews successful inspections, and produces a summary receipt.
 It runs without network access or a provider SDK. Python standard library only.

 ## Incident 73: a reopened job lost work and sent another receipt
 Operations restored a worker after a process exit during delivery. Some receipts
 were sent again; a later summary said all selected items were handled even though
 one inspection failed. A second customer sharing the same job number also saw a
 confusing recovery error. The saved requests in `traces/` are operational examples.
 Repair the intake path across storage, worker and reporting. Preserve the public
 CLI, add focused regressions, and document the fix and checks in `PATCH-NOTES.md`.
 Public checks: `python -m unittest discover -s tests`.

 ## Public CLI contract
 `python -m intake --db jobs.sqlite --request request.json --receipts receipts.jsonl`
 reads one JSON request and prints one JSON report (exit 0), or `{error:...}` (exit 2).
 Every command includes trusted tenant and job strings. `submit` includes immutable
 spec `{items:[{id,payload}],max_attempts}`; IDs are unique and nonempty. Remaining
 operations are work, report, cancel, resume, reconcile. Job identity, data, effects
 and reconciliation are tenant-scoped. Resubmitting the same spec is a no-op; a
 changed population or budget is a different job and must be rejected.

 Worker stages are inspect(item), review(item, requires its successful inspection),
 summary(aggregate). The report retains the entire submitted population. Coverage
 requires success at both item stages; synthesis cannot erase gaps. Failed item
 outcomes are known gaps, not new work to retry automatically. Unknown or pending
 item dependencies prevent summary delivery. Each receipt includes context with
 coverage and operation_key; keys remain stable across restarts and distinct across
 tenants. Only new dispatches consume cumulative max_attempts, including crashes.
 Cancel is durable; only explicit resume permits further dispatch under original
 budgets. Reporting and resubmission cannot reset attempts or cancellation.

 The local receiver appends a JSONL receipt on each call. Payload keys `inspect`
 and `review` may be `fail`, otherwise that stage succeeds. For incident replay,
 `crash_after_effect` equal to a stage exits the process with code 17 after writing
 its receipt. An exit cannot prove the external delivery failed: retain that work
 as running/unknown and never auto-replay it on restart. Reconcile takes stage,
 item, state (succeeded or failed), result and nonempty external evidence. It may
 resolve only an existing unknown operation, and must not rewrite settled work.
 There is one local coordinator; distributed locking is outside this incident.
 ''')
 blob(root,'traces/new-job.json',{'op':'submit','tenant':'acme','job':'INC-73','spec':{'items':[{'id':'invoice-A'},{'id':'invoice-B','payload':{'inspect':'fail'}}],'max_attempts':8}})
 blob(root,'traces/crash-job.json',{'op':'submit','tenant':'acme','job':'INC-74','spec':{'items':[{'id':'delivery-A','payload':{'crash_after_effect':'inspect'}}],'max_attempts':8}})
# Legacy starter retains incomplete assumptions, with public happy paths healthy.
p=starter/'intake/store.py';s=p.read_text().replace('packed([tenant,job,stage,item])','packed([job,stage,item])').replace("WHERE tenant=? AND job=?',(tenant,job)).fetchone()","WHERE job=?',(job,)).fetchone()")
p.write_text(s)
p=starter/'intake/service.py';s=p.read_text()
s=s.replace("for stage in ('inspect','review')","for stage in ('inspect',)")
s=s.replace("    for stage in STAGES:\n        for row", "    store.db.execute('UPDATE jobs SET attempts=0,cancelled=0 WHERE tenant=? AND job=?',(tenant,job))\n    for stage in STAGES:\n        for row")
s=s.replace("if dependency['state'] in ('running','pending'):continue","if dependency['state'] in ('running','pending'):pass")
s=s.replace("if dependency['state']!='succeeded':store.update(tenant,job,stage,row['item'],'not_covered');continue","if dependency['state']!='succeeded':pass")
s=s.replace("if stage=='summary' and any(r['state'] in ('running','pending') for r in previous):continue","# Summary reads whatever results are currently available.")
s=s.replace("            store.db.execute('BEGIN IMMEDIATE')", "            outcome=perform(context,receipts)\n            store.db.execute('BEGIN IMMEDIATE')")
s=s.replace("            outcome=perform(context,receipts)\n            store.update", "            store.update")
s=s.replace("if not isinstance(evidence,str) or not evidence.strip() or state not in ('succeeded','failed'):","if state not in ('succeeded','failed'):")
s=s.replace("if target is None or target['state']!='running':","if target is None:")
p.write_text(s)
print('durable repositories built')
# Shared gateway transport/storage boundary, used by the public replay command.
for root in [BASE/'private/reference/gateway',BASE/'tasks/E-GATEWAY/repo']:
 put(root,'gateway/storage.py','''
 import json,os,tempfile
 from pathlib import Path
 MAX_CAPTURE_BYTES=8*1024*1024
 def load_capture(path):
     raw=path.read_bytes()
     if len(raw)>MAX_CAPTURE_BYTES:raise ValueError('capture exceeds desk replay limit')
     capture=json.loads(raw)
     if not isinstance(capture,dict):raise ValueError('capture object required')
     return capture
 def write_result(path,result):
     # A browser poll must see the previous artifact or a complete new artifact.
     content=json.dumps(result,ensure_ascii=False,allow_nan=False)
     temporary=None
     try:
         with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.gateway-',delete=False) as output:
             temporary=Path(output.name);output.write(content);output.flush();os.fsync(output.fileno())
         os.replace(temporary,path);temporary=None
     finally:
         if temporary is not None:temporary.unlink(missing_ok=True)
 ''')
 put(root,'gateway/validation.py','''
 ALLOWED_MODES=frozenset(('single','multi_agent'))
 def validate_capture(capture):
     if capture.get('mode','single') not in ALLOWED_MODES:raise ValueError('unsupported replay mode')
     events=capture.get('events')
     if not isinstance(events,list):raise ValueError('ordered event array required')
     if len(events)>50000:raise ValueError('event count exceeds desk replay limit')
     for position,event in enumerate(events):
         if not isinstance(event,dict):raise ValueError('event object required at '+str(position))
         if not isinstance(event.get('type'),str):raise ValueError('event type required at '+str(position))
     # This is envelope validation. The projector owns protocol/terminal semantics.
     return capture
 ''')
 put(root,'gateway/metrics.py','''
 from collections import Counter
 def archive_summary(capture,items):
     kinds=Counter(event['type'] for event in capture['events'])
     item_types=Counter(str(item.get('type','unknown')) for item in items)
     first=capture['events'][0] if capture['events'] else {}
     last=capture['events'][-1] if capture['events'] else {}
     start=first.get('received_at_ms');stop=last.get('received_at_ms')
     elapsed=None
     if type(start) in (int,float) and type(stop) in (int,float) and stop>=start:elapsed=stop-start
     return {'format_version':1,'capture_id':capture.get('capture_id'),
             'event_count':len(capture['events']),'event_types':dict(kinds),
             'item_count':len(items),'item_types':dict(item_types),'capture_elapsed_ms':elapsed}
 ''')
 put(root,'gateway/service.py','''
 from .validation import validate_capture
 from .replay import replay
 from .metrics import archive_summary
 class Gateway:
     def __init__(self):self.accepted=0
     def ingest(self,capture):
         validate_capture(capture)
         bundle=replay(capture)
         bundle['archive']['summary']=archive_summary(capture,bundle['archive']['output_items'])
         self.accepted+=1
         return bundle
 def replay_capture(capture):
     # HTTP integration uses bundle['client']; the full bundle stays in ops storage.
     return Gateway().ingest(capture)
 ''')
 put(root,'gateway/__main__.py','''
 import argparse,json,sys
 from pathlib import Path
 from .service import replay_capture
 from .storage import load_capture,write_result
 def main():
     p=argparse.ArgumentParser(description='Offline support-desk capture replay')
     p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
     try:
         result=replay_capture(load_capture(a.capture));write_result(a.out,result)
     except (ValueError,TypeError,KeyError,OSError) as exc:
         print(json.dumps({'error':str(exc)}));return 2
     print(json.dumps({'written':str(a.out),'status':result['client']['status']}));return 0
 if __name__=='__main__':sys.exit(main())
 ''')
print('gateway integration boundary built')
