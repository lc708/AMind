#!/usr/bin/env python3
"""Capture bounded, frozen skill trials; grading stays outside target access."""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,shutil,signal,subprocess,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reviews/2026-10-19-workplace'
TEMP=ROOT/'.codex-tmp/workplace-2026-10-19'
LOCK=threading.Lock()
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.git')

def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(p):return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc' and f.name!='.DS_Store' and '.git' not in f.parts}
def protected_paths(base,rid):
    home=Path('/Users/damonalbarn/.codex')
    paths=[str(ROOT),'/Users/damonalbarn/Work',str(home/'worktrees'),str(home/'skills'),str(home/'plugins'),str(base/'control'),'/private/tmp/amind-paired-20261018-16krdfbb']
    paths += [str(home/x) for x in ['sessions','archived_sessions','memories','memory','history.jsonl','shell_snapshots','logs']]
    paths += [str(p) for p in home.glob('*.sqlite*')]
    paths += [str(base/f'U{i:03d}') for i in range(1,5) if f'U{i:03d}'!=rid]
    paths += [str(base/f'W{i:03d}') for i in range(1,49) if f'W{i:03d}'!=rid]
    return paths

def make_policy(base,rid,grading=False):
    work=base/rid
    s='(version 1)\n(allow default)\n'
    for p in protected_paths(base,rid):s+='(deny file-read* file-write* (subpath '+json.dumps(p)+'))\n'
    for p in [work/'skills',work/'task.json',work/'repo/tests']:
        s+='(deny file-write* (subpath '+json.dumps(str(p))+'))\n'
    s+='(deny file-write* (literal "/Users/damonalbarn/.codex/config.toml") (literal "/Users/damonalbarn/.codex/auth.json"))\n'
    if grading:
        s+='(deny network*)\n'
        for p in [work/'skills',work/'repo',work/'output']:
            s+='(deny file-read* file-write* (subpath '+json.dumps(str(p))+'))\n'
    dest=base/'control'/(rid+('-grade' if grading else '')+'.sb');dest.write_text(s);return dest

def preflight():
    meta=read(TEMP/'runtime.json');base=Path(meta['root']);pol=make_policy(base,'W001')
    own=base/'W001/public.txt';own.write_text('PUBLIC')
    program='''import json,pathlib
out={}
for p in PATHS:
 try:out[p]=pathlib.Path(p).read_text()[:80]
 except OSError:out[p]='DENIED'
for key,p in WRITES.items():
 try:pathlib.Path(p).write_text('probe');out[key]='ALLOWED'
 except OSError:out[key]='DENIED'
print(json.dumps(out))'''
    paths=[str(own),str(base/'control/canary.txt'),str(base/'W002/canary.txt'),str(ROOT/'README.md')]
    program='PATHS='+repr(paths)+'\nWRITES='+repr({'own_write':str(base/'W001/write.txt'),'sibling_write':str(base/'W002/write.txt')})+'\n'+program
    a=subprocess.run(['/usr/bin/sandbox-exec','-f',str(pol),'python3','-c',program],capture_output=True,text=True,timeout=10,cwd=base/'W001')
    assert a.returncode==0,a.stderr
    result=json.loads(a.stdout);assert result[paths[0]]=='PUBLIC' and all(result[x]=='DENIED' for x in paths[1:]) and result['sibling_write']=='DENIED' and result['own_write']=='ALLOWED'
    dry=subprocess.run(['/usr/bin/sandbox-exec','-f',str(pol),meta['native_cli'],'--no-daemon','--profile',meta['profile_name'],'debug','prompt-input','Offline preflight; no model call.'],cwd=base/'W001',capture_output=True,text=True,timeout=30)
    assert dry.returncode==0,dry.stderr
    meta['os_preflight']={'returncode':a.returncode,'canary':result,'protected_prompt_dryrun':{'returncode':dry.returncode,'stdout_bytes':len(dry.stdout.encode()),'stderr':dry.stderr},'model_called':False}
    write(TEMP/'runtime.json',meta);write(OUT/'runtime-isolation.json',meta)
    print(json.dumps(meta['os_preflight'],ensure_ascii=False))

def setup(protocol):
    meta=read(TEMP/'runtime.json');base=Path(meta['root']);runs=[]
    # Balanced deterministic arm order; replicas are not independent task families.
    for rep in range(3):
        tasks=protocol['tasks']
        if rep%2:tasks=list(reversed(tasks))
        for task in tasks:
            arms=['citation-before','citation-docs','citation-current'] if task['skill']=='amind' else ['old','current']
            rotate=(rep+int(hashlib.sha256(task['id'].encode()).hexdigest()[:2],16))%len(arms);arms=arms[rotate:]+arms[:rotate]
            for arm in arms:
                rid=f'W{len(runs)+1:03d}';work=base/rid
                assert not (work/'skills').exists(),rid
                packages=['amind'] if task['skill']=='amind' else ['amind-engineering','eval-improve']
                for name in packages:shutil.copytree(TEMP/arm/'skills'/name,work/'skills'/name,ignore=IGNORE)
                if task.get('repo'):shutil.copytree(Path(task['repo']),work/'repo',ignore=IGNORE)
                (work/'output').mkdir(exist_ok=True);write(work/'task.json',{'id':task['id'],'prompt':task['prompt']})
                runs.append({'run_id':rid,'task_id':task['id'],'axis':task['axis'],'rep':rep,'arm':arm,'skill':task['skill'],'workspace':str(work),'skill_files':inventory(work/'skills'),'public_tests':inventory(work/'repo/tests') if (work/'repo/tests').exists() else {},'starter_files':inventory(work/'repo') if (work/'repo').exists() else {},'task_sha256':sha(work/'task.json')})
    assert len(runs)==42
    plan={'runs':runs,'root':str(base),'profile_name':meta['profile_name'],'protocol_sha256':sha(OUT/'protocol.json'),'runner_sha256':sha(Path(__file__))}
    write(OUT/'main-plan.json',plan);print(json.dumps({'prepared':len(runs),'model_called':False}))

def capture(run,plan,protocol):
    rid=run['run_id'];base=Path(plan['root']);work=Path(run['workspace']);dest=OUT/'runs'/rid
    if dest.exists():raise ValueError('Refusing overwrite '+rid)
    dest.mkdir(parents=True)
    assert sha(work/'task.json')==run['task_sha256']
    assert inventory(work/'skills')==run['skill_files']
    pol=make_policy(base,rid)
    canary=subprocess.run(['/usr/bin/sandbox-exec','-f',str(pol),'/bin/cat',str(base/'control/canary.txt')],capture_output=True,timeout=5)
    assert canary.returncode!=0,'private grading canary readable'
    task=read(work/'task.json')
    text=('这是本地工作交付对照。先读 skills/'+run['skill']+'/SKILL.md 并按需使用所分配的参考与工具；应用技能所需的另一套技能也在 skills/。只使用本目录输入与技能，不读其他运行、主机历史、外部技能或评测材料。不联网、不调用下游模型、不创建子agent。不得改 skills/、task.json 或已有 repo/tests/；应用题实际项目在 repo/，先进入该目录；可修改 repo/ 源码并在 output/ 增补诊断或自己的测试，真正运行公开入口验证。交付 repo 应能独立运行，不依赖本机 skills/ 或绝对路径；可将所需标准库实现纳入 repo 并标注来源。评分依据独立的应用行为，最终自述不算完成证据。引用题只写 output/answer.json，并在最终回答重复完整JSON。所有应用副作用使用本地fixture，禁止写入本目录以外位置。保留用户指定模型，限时8分钟，完成后简短说明做了什么及验证结果。\n\n'+task['prompt'])
    meta=read(TEMP/'runtime.json')
    command=['/usr/bin/sandbox-exec','-f',str(pol),meta['native_cli'],'--no-daemon','--profile',plan['profile_name'],'-a','never','exec','--json','--ephemeral','--sandbox','danger-full-access','--skip-git-repo-check','--color','never','--cd',str(work),'--output-last-message',str(work/'output/final.txt'),'-']
    with LOCK:
        bp=OUT/'budget.json'
        if bp.exists():budget=read(bp)
        else:
            now=time.time();budget={'started_at_epoch':now,'deadline_epoch':now+protocol['max_wall_seconds'],'max_target_executions':48,'admitted':[]}
        if time.time()>=budget['deadline_epoch'] or len(budget['admitted'])>=48:
            result={'run_id':rid,'task_id':run['task_id'],'arm':run['arm'],'rep':run['rep'],'status':'budget_not_launched','model_launched':False,'usage':None}
            write(dest/'capture.json',result);return result
        assert rid not in budget['admitted'];budget['admitted'].append(rid);write(bp,budget)
    started=time.monotonic();reason=None
    with (dest/'events.jsonl').open('wb') as stdout,(dest/'stderr.txt').open('wb') as stderr:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,cwd=work,start_new_session=True)
        process.stdin.write(text.encode());process.stdin.close()
        deadline=min(time.monotonic()+protocol['timeout_seconds'],time.monotonic()+max(0,budget['deadline_epoch']-time.time()))
        while process.poll() is None:
            if time.monotonic()>=deadline:reason='timeout'
            if (dest/'events.jsonl').stat().st_size>64*1024*1024:reason='output_ceiling'
            if reason:os.killpg(process.pid,signal.SIGKILL);break
            time.sleep(.25)
        process.wait()
    events=[];bad=[]
    for line in (dest/'events.jsonl').read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:bad.append(line[:200])
    turns=[e for e in events if e.get('type')=='turn.completed'];errors=[e for e in events if e.get('type') in ['error','turn.failed']]
    final=(work/'output/final.txt').read_text() if (work/'output/final.txt').exists() else ''
    skill_ok=inventory(work/'skills')==run['skill_files'];tests_ok=inventory(work/'repo/tests')==run['public_tests'] if (work/'repo/tests').exists() else not run['public_tests']
    status=reason or ('runtime_error' if process.returncode or errors else 'incomplete' if len(turns)!=1 or not final.strip() or bad else 'captured')
    if not skill_ok or not tests_ok:status='protected_source_modified'
    result={'run_id':rid,'task_id':run['task_id'],'axis':run['axis'],'rep':run['rep'],'arm':run['arm'],'status':status,'model_launched':True,'returncode':process.returncode,'elapsed_seconds':round(time.monotonic()-started,3),'requested_model':protocol['requested_model'],'requested_effort':protocol['requested_effort'],'actual_served_model_verified':False,'usage':[t.get('usage') for t in turns] or None,'errors':errors,'malformed_events':bad,'skill_unchanged':skill_ok,'public_tests_unchanged':tests_ok,'grader_canary_denied':True,'final':final,'command':command,'grade':None}
    shutil.copytree(work/'output',dest/'output',dirs_exist_ok=True,ignore=IGNORE)
    if (work/'repo').exists():shutil.copytree(work/'repo',dest/'repo',ignore=IGNORE)
    (dest/'prompt.txt').write_text(text);write(dest/'capture.json',result)
    with LOCK:
        with (OUT/'execution-ledger.jsonl').open('a') as f:f.write(json.dumps({k:v for k,v in result.items() if k not in ['final','command']},ensure_ascii=False)+'\n')
        print(json.dumps({k:result[k] for k in ['run_id','task_id','rep','arm','status','elapsed_seconds']},ensure_ascii=False),flush=True)
    return result

def execute(plan_name,only=None,remaining=False):
    protocol=read(OUT/'protocol.json');assert sha(OUT/'protocol.json')==read(OUT/'protocol-fingerprint.json')['sha256']
    plan=read(OUT/plan_name);assert plan['runner_sha256']==sha(Path(__file__)),'Runner changed; version and explain before execution'
    selected=[x for x in plan['runs'] if (only is None or x['run_id'] in only) and (not remaining or not (OUT/'runs'/x['run_id']).exists())]
    if not selected:raise ValueError('No unexecuted selected runs')
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(capture,x,plan,protocol) for x in selected]
        for future in concurrent.futures.as_completed(futures):results.append(future.result())
    write(OUT/('batch-'+selected[0]['run_id']+'-'+selected[-1]['run_id']+'-capture-summary.json'),{'selected_run_ids':[x['run_id'] for x in selected],'results':results,'captured':sum(x['status']=='captured' for x in results),'planned_in_batch':len(selected),'full_plan':len(plan['runs']),'graded':False})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['preflight','setup','execute']);p.add_argument('--plan',default='main-plan.json');p.add_argument('--only',nargs='+');p.add_argument('--remaining',action='store_true');a=p.parse_args()
    if a.stage=='preflight':preflight()
    elif a.stage=='setup':setup(read(OUT/'protocol.json'))
    else:execute(a.plan,a.only,a.remaining)
