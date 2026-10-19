import json,sys
from pathlib import Path
p=json.load(sys.stdin)
i,c=p['input'],p['context']
log=Path(__file__).with_name('calls.jsonl')
with log.open('a') as f:f.write(json.dumps({'case':c['case_id'],'input':i})+'\n')
if i.get('failure'):
 print(json.dumps({'error':{'kind':'synthetic_service_failure','retryable':True},'cost_usd':.02,'synthetic':True}));sys.exit(1)
out=i.get('text','ok')
if c['config'].get('uppercase'):out=out.upper()
r={'output':out,'model':i.get('served_model','same-model'),'cost_usd':.02,'synthetic':True,'billing_identity':{'provider':'fixture','interface':'responses','model':'same-model','service_tier':i.get('served_tier','standard'),'region':'global'}}
if 'coverage' in i:r['coverage']=i['coverage']
print(json.dumps(r))
