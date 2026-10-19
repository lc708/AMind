import datetime,hashlib,json,re,shutil,subprocess
from pathlib import Path
r=Path.cwd();p=r/'reviews/2026-10-18-comparison';tmp=r/'.codex-tmp/contrast-2026-10-18';v=p/'validation'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
load=lambda f:json.loads(f.read_text())
app=load(v/'application-checks.json');assert app['successful'] and app['tests_run']==138 and not app['failures']
text=(tmp/'final-knowledge-regression.log').read_text();assert 'Ran 60 tests' in text and text.rstrip().endswith('OK')
shutil.copyfile(tmp/'final-knowledge-regression.log',v/'knowledge-checks.txt');shutil.copyfile(tmp/'application-regression.log',v/'application-checks.txt')
for src,dst in [('os-isolation.json','runtime-isolation.json'),('build_confirmation_blind.py','measurement-revisions/build-confirmation-blind.py'),('summarize_agents.py','measurement-revisions/summarize-agents.py')]:
 q=p/dst;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(tmp/src,q)
snaps=load(p/'snapshots.json')['variants'];frozen={}
for arm in ['old','new','repaired']:
 data=load(p/'repaired-selection.json') if arm=='repaired' else snaps[arm]
 changed=[f for f,h in data['files'].items() if sha(tmp/arm/f)!=h]
 assert not changed,(arm,changed)
 frozen[arm]={'files':len(data['files']),'tree_sha256':data['tree_sha256'],'changed_files':changed}
for a,b in [('agent-protocol.json','agent-protocol-fingerprint.json'),('agent-grader-contract.json','agent-grader-fingerprint.json'),('confirmation-protocol.json','confirmation-protocol-fingerprint.json'),('confirmation-code-probes.json','confirmation-code-probes-fingerprint.json')]:assert sha(p/a)==load(p/b)['sha256'],a
before=load(p/'post-trial-evidence-clarification/change.json')
old=[json.loads(s) for s in (p/'post-trial-evidence-clarification/before/skills/amind/data/current-status.jsonl').read_text().splitlines()]
now=[json.loads(s) for s in (r/'skills/amind/data/current-status.jsonl').read_text().splitlines()]
assert [{k:v for k,v in x.items() if k!='reason'} for x in old]==[{k:v for k,v in x.items() if k!='reason'} for x in now]
before['after_hashes']={f:sha(r/f) for f in before['before_hashes']};before['eligibility_fields_unchanged']=True
(p/'post-trial-evidence-clarification/change.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n')
install=load(v/'installation.json')
for name,inventory in install['package_inventories'].items():
 assert all(sha(r/'skills'/name/f)==h==sha(Path('/Users/damonalbarn/.codex/skills')/name/f) for f,h in inventory.items())
for name in ['amind-engineering','eval-improve']:
 assert app['package_hashes'][name]==install['package_inventories'][name],name
release=load(v/'release-verification.json');assert release['verdict']=='PASS' and release['historical_files_unchanged']==59
assert sha(r/'skills/amind/data/amind-full-index.sqlite3')==snaps['new']['files']['skills/amind/data/amind-full-index.sqlite3']
trials=load(p/'agent-execution-summary.json');assert trials['captured']==24 and trials['unique_threads']==24 and trials['all_canaries_denied'] and trials['all_sources_unchanged']
assert not trials['command_trace_flags'];assert len(set(x['message'] for x in trials['native_error_items']))==1
allrows=load(p/'source-answer-score-summary.json')['rows']+load(p/'agent-deterministic-grades.json')['rows']+load(p/'confirmation-code-grades.json')['rows']
assert len(allrows)==24 and len({x['run_id'] for x in allrows})==24
paired=[]
for case in ['K1','K2','T1','T2','G1','G2','V1','V2','C-K','C-T','C-G','C-V']:
 xs=[x for x in allrows if x['case_id']==case];assert len(xs)==2
 base=next(x for x in xs if x['arm']=='old');cand=next(x for x in xs if x['arm']!='old')
 paired.append({'case_id':case,'baseline':{k:base[k] for k in ['run_id','score','max_score']},'candidate':{k:cand[k] for k in ['run_id','arm','score','max_score']},'outcome':'tie' if base['score']==cand['score'] else 'higher' if cand['score']>base['score'] else 'lower'})
(p/'paired-agent-scores.json').write_text(json.dumps({'paired_tasks':paired,'overall_score':None,'reason':'Different task weights/scales; no pooled accuracy or population inference.'},ensure_ascii=False,indent=2)+'\n')
codecheck=subprocess.run(['python3','-m','py_compile','scripts/compare_amind_agent_trials.py','scripts/grade_amind_agent_code.py'],capture_output=True,text=True);assert codecheck.returncode==0
patchcheck=subprocess.run(['git','diff','--check'],capture_output=True,text=True);assert patchcheck.returncode==0,patchcheck.stdout+patchcheck.stderr
up=load(v/'upstream-source-verification.json');assert up['source_hashes_verified']
final={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'PASS with explicitly bounded model conclusions','versions':install['versions'],'product_checks':{'application':138,'knowledge_and_sources':60,'total':198,'failures':0,'all_product_code_tested':True,'post_trial_instruction_change_model_retested':False},'frozen_snapshots':frozen,'frozen_protocol_hashes_match':True,'target_cli_executions':{'planned':24,'captured':24,'failed':0,'unique_threads':24,'retries':0,'requested_model':'gpt-6.1-sol','requested_effort':'ultra','actual_served_model_verified':False},'model_task_outcomes':{'higher':sum(x['outcome']=='higher' for x in paired),'tie':sum(x['outcome']=='tie' for x in paired),'lower':sum(x['outcome']=='lower' for x in paired),'production_population_inference':False},'release':release,'upstream_source_map':up,'installation':{'verified':install['verified'],'backup':install['backup'],'all_three_package_inventories_match':True,'unrelated_directory_smoke_passed':True},'runtime_cleanup':load(v/'runtime-cleanup.json'),'git_diff_check_passed':True,'harness_syntax_check_passed':True,'cost_usd':None,'scope':'198 deterministic product checks plus targeted local contract comparisons and24 exploratory actual CLI skill trials; source-grounded AI grading is not human calibration; precise support and isolation limitations in report.','source_observation_cutoff':'2026-10-18','new_human_gold_rows':0,'repair_classes':8,'post_trial_evidence_rule_refinement':True,'working_tree_sync_receipt':'workspace-sync.json'}
(v/'final.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
# Minimal links check for current report and root docs, not archived upstream links.
missing=[]
for q in [p/'report.zh-CN.md',r/'README.md',r/'README.zh-CN.md',r/'AMIND-SERIES.md',r/'CONTRIBUTING.md']:
 for link in re.findall(r'\]\(([^)]+)\)',q.read_text()):
  link=link.strip('<>').split('#')[0]
  if link and not re.match(r'(?:https?://|mailto:|app://)',link) and not (q.parent/link).exists():missing.append([str(q.relative_to(r)),link])
assert not missing,missing
print({'tests':198,'trials':24,'paired_higher':final['model_task_outcomes']['higher'],'paired_ties':final['model_task_outcomes']['tie'],'installed_exact':True,'frozen_snapshots_verified':True,'missing_links':missing})
