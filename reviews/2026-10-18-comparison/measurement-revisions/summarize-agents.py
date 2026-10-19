import collections,hashlib,json,re
from pathlib import Path
p=Path('reviews/2026-10-18-comparison'); tmp=Path('.codex-tmp/contrast-2026-10-18')
mainmap=json.loads((tmp/'blind-map.json').read_text()); print('map-shape',str(mainmap)[:180])
rows=[]; thread_ids=[]; itemtypes=collections.Counter(); suspect=[]; warnings=[]
usage=collections.Counter()
for n in range(1,25):
 run=f'R{n:02}'; c=json.loads((p/f'agent-runs/{run}/capture.json').read_text())
 events=[json.loads(l) for l in (p/f'agent-runs/{run}/events.jsonl').read_text().splitlines()]
 for e in events:
  if e.get('type')=='thread.started': thread_ids.append(e['thread_id'])
  item=e.get('item',{}); typ=item.get('type')
  if typ: itemtypes[typ]+=e.get('type')=='item.completed'
  if e.get('type')=='item.completed' and typ=='command_execution':
   cmd=item.get('command','')
   hits=[x for x in ['~/.codex/sessions','/.codex/sessions','/.codex/skills','/Work/AMind','/worktrees/','/control/','curl ','wget ','http.client','urlopen','requests.get','cua','mcp'] if x in cmd]
   other_runs=re.findall(r'/R(\d\d)(?:/|\b)',cmd)
   if hits or any(int(z)!=n for z in other_runs): suspect.append({'run':run,'command':cmd,'flags':hits,'other_runs':other_runs})
  if e.get('type')=='item.completed' and typ=='error': warnings.append({'run':run,'message':item.get('message','')})
 for u in c.get('usage',[]):
  for k,v in u.items():
   if isinstance(v,(int,float)): usage[k]+=v
 rows.append({k:c[k] for k in ['run_id','case_id','arm','status','returncode','elapsed_seconds','grader_canary_denied','skill_unchanged','actual_served_model_verified']})
result={'target_cli_executions_planned':24,'captured':sum(r['status']=='captured' for r in rows),'unique_threads':len(set(thread_ids)),'all_canaries_denied':all(r['grader_canary_denied'] for r in rows),'all_sources_unchanged':all(r['skill_unchanged'] for r in rows),'requested_model':'gpt-6.1-sol','requested_reasoning_effort':'ultra','actual_served_model_verified':False,'native_cumulative_usage':dict(usage),'dollar_cost_usd':None,'dollar_cost_reason':'Subscription Codex runtime; native token counters are retained but invoice/rate identity unavailable. Zero not asserted.','sum_task_wall_seconds':round(sum(r['elapsed_seconds'] for r in rows),3),'completed_item_types':dict(itemtypes),'command_trace_flags':suspect,'native_error_items':warnings,'runtime_limits':['One execution per arm/task; no statistical population claim','No full host read allowlist; native command traces cannot prove absence of all history leakage','Native web/apps/plugins disabled; outbound inference not OS egress restricted','No verified served model identity; requested configuration only'],'runs':rows}
(p/'agent-execution-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['runs','native_error_items']},ensure_ascii=False,indent=2))
