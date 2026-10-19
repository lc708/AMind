import gzip,hashlib,json,re,sqlite3,zlib
from pathlib import Path
root=Path.cwd(); out=root/'reviews/2026-10-18-comparison'; temp=root/'.codex-tmp/contrast-2026-10-18'
protocol=json.loads((out/'confirmation-protocol.json').read_text()); tasks={x['id']:x for x in protocol['tasks']}
packets=[]; private={}; supplements=[]
for i in range(17,21):
 run=f'R{i:02}'; c=json.loads((out/f'agent-runs/{run}/capture.json').read_text()); a=c['final']
 bid='Q'+hashlib.sha256(('confirmation-neutral-'+run).encode()).hexdigest()[:10]
 private[bid]={'run_id':run,'arm':c['arm'],'case_id':c['case_id']}
 home=temp/c['arm']/'skills/amind/data'; conn=sqlite3.connect(home/'amind-full-index.sqlite3')
 vals=[]; need={}
 for cid in sorted(set(re.findall(r'nuwa1-claim-[0-9a-f]+',a))):
  row=conn.execute('select c.payload_zlib,s.payload_zlib,s.canonical,s.title,s.published_at,v.name,v.organization,v.voice_type from claims c join sources s on c.source_id=s.id join voices v on v.id=c.voice_id where c.claim_id=?',(cid,)).fetchone()
  if not row: vals.append({'claim_id':cid,'exists':False}); continue
  cp,sp=[json.loads(zlib.decompress(x)) for x in row[:2]]
  v={'claim_id':cid,'exists':True,'claim':cp,'source_metadata':sp,'canonical_url':row[2],'source_title':row[3],'published_at':row[4],'voice_name':row[5],'organization':row[6],'voice_type':row[7]}
  vals.append(v); need.setdefault(cp['passage_id'],[]).append(v)
 if need:
  with gzip.open(home/'passages.jsonl.gz','rt') as f:
   for line in f:
    p=json.loads(line)
    for v in need.get(p['passage_id'],[]): v['bound_passage']=p; v['exact_quote_in_passage']=v['claim']['exact_quote'] in p['text']
 statuses=[]; reg=home/'current-status.jsonl'
 for line in reg.read_text().splitlines() if reg.exists() else []:
  s=json.loads(line)
  if any(v['claim_id'] in s.get('target_claim_ids',[]) or v.get('bound_passage',{}).get('analysis_unit_id') in s.get('target_analysis_unit_ids',[]) for v in vals): statuses.append(s)
 packets.append({'blind_id':bid,'case_id':c['case_id'],'public_task':tasks[c['case_id']]['prompt'],'answer':a,'status':c['status'],'citation_validation':vals})
 supplements.append({'blind_id':bid,'case_id':c['case_id'],'runtime_has_registry':reg.exists(),'machine_status_records':statuses,'evidence_role':'Actual assigned-runtime curation records, not independent primary source proof; same validation channel supplied for every answer.'})
packets.sort(key=lambda x:x['blind_id']); supplements.sort(key=lambda x:x['blind_id'])
for name,value in [('confirmation-blind-inputs.json',packets),('confirmation-blind-status-supplement.json',supplements)]: (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
(temp/'confirmation-blind-map.json').write_text(json.dumps(private,indent=2)+'\n')
print({'packets':len(packets),'citations':sum(len(p['citation_validation']) for p in packets),'all_citations_exist':all(v['exists'] for p in packets for v in p['citation_validation'])})
