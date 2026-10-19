#!/usr/bin/env python3
"""Audit all frozen target captures only after the full registered phase ends."""
import argparse,collections,hashlib,json,re,time
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def read(p):return json.loads(p.read_text())
def main(plan_name):
 plan=read(OUT/plan_name);missing=[x['run_id'] for x in plan['runs'] if not (OUT/'runs'/x['run_id']/'capture.json').exists()]
 if missing:raise RuntimeError('No partial-phase content audit: missing '+','.join(missing))
 rows=[];usage=collections.Counter();threads=[];types=collections.Counter();flags=[];warnings=[];skill_reads=[]
 for run in plan['runs']:
  rid=run['run_id'];dest=OUT/'runs'/rid;c=read(dest/'capture.json');items=[]
  if (dest/'events.jsonl').exists():
   for line in (dest/'events.jsonl').read_text().splitlines():
    try:items.append(json.loads(line))
    except ValueError:pass
  reads={'run_id':rid,'assigned_skill_terms':[],'helper_script_terms':[]}
  for e in items:
   if e.get('type')=='thread.started':threads.append(e['thread_id'])
   item=e.get('item',{})
   if e.get('type')!='item.completed':continue
   types[item.get('type','unknown')]+=1
   if item.get('type')=='error':warnings.append({'run_id':rid,'message':item.get('message','')})
   if item.get('type')!='command_execution':continue
   cmd=item.get('command','');hits=[x for x in ['/.codex/sessions','/.codex/archived_sessions','/.codex/skills','/Users/damonalbarn/Work','/worktrees/','/control/','/U001','/U002','/U003','/U004','curl ','wget ','urlopen','requests.get','http.client'] if x in cmd]
   other=re.findall(r'/W(\d{3})(?:/|\b)',cmd)
   if hits or any('W'+z!=rid for z in other):flags.append({'run_id':rid,'command':cmd,'flags':hits,'other_runs':other,'exit_code':item.get('exit_code'),'note':'Manual review needed; a trace term is not proof of successful access.'})
   for name in ['amind','amind-engineering','eval-improve']:
    if 'skills/'+name+'/' in cmd:reads['assigned_skill_terms'].append(name)
   reads['helper_script_terms']+=re.findall(r'([a-z_]+\.py)',cmd)
  reads['assigned_skill_terms']=sorted(set(reads['assigned_skill_terms']));reads['helper_script_terms']=sorted(set(reads['helper_script_terms']));skill_reads.append(reads)
  for u in c.get('usage') or []:
   for k,v in (u or {}).items():
    if isinstance(v,(int,float)) and not isinstance(v,bool):usage[k]+=v
  rows.append({k:c.get(k) for k in ['run_id','task_id','axis','arm','rep','status','model_launched','elapsed_seconds','skill_unchanged','public_tests_unchanged','grader_canary_denied']})
 summary={'planned':len(plan['runs']),'captured':sum(x['status']=='captured' for x in rows),'statuses':dict(collections.Counter(x['status'] for x in rows)),'all_assigned_skills_unchanged':all(x['skill_unchanged'] for x in rows),'all_public_tests_unchanged':all(x['public_tests_unchanged'] for x in rows),'all_canaries_denied':all(x['grader_canary_denied'] for x in rows),'native_unique_threads':len(set(threads)),'requested_model':'gpt-6.1-sol','requested_effort':'ultra','actual_served_model_verified':False,'native_cumulative_usage':dict(usage),'missing_usage_runs':[x['run_id'] for x in plan['runs'] if not read(OUT/'runs'/x['run_id']/'capture.json').get('usage')],'sum_task_wall_seconds':round(sum(x['elapsed_seconds'] or 0 for x in rows),3),'dollar_cost_usd':None,'cost_note':'Native subscription counters, unknown invoice/rate scope. Cached/reasoning counters are subsets and not added twice. Analytical agents not included in target capture counters.','completed_item_types':dict(types),'native_error_items':warnings,'trace_flags':flags,'skill_use_trace_terms':skill_reads,'rows':rows,'limits':['Only declared phase complete; no production-distribution claim.','Path-deny isolation and trace term scan do not prove absence of every possible leak.','Skill/helper trace terms are evidence of command mentions, not full cognitive mechanism.']}
 (OUT/(Path(plan_name).stem+'-capture-audit.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:summary[k] for k in ['planned','captured','statuses','native_unique_threads','all_assigned_skills_unchanged','all_public_tests_unchanged','sum_task_wall_seconds']}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',default='main-plan.json');a=p.parse_args();main(a.plan)
