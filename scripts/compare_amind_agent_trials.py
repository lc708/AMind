#!/usr/bin/env python3
"""Bounded same-runtime skill trials with protected grader/source paths on macOS.

This captures real CLI executions, not scores. OS policy protects references and
other runs; it is not a general network or host write allowlist.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reviews/2026-10-18-comparison'
SNAP=ROOT/'.codex-tmp/contrast-2026-10-18'
LOCK=threading.Lock()
GLOBAL_DEADLINE=None


def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(p):return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}


def prepare():
    if (OUT/'agent-protocol.json').exists():raise ValueError('Protocol already frozen; do not overwrite')
    eng=read(OUT/'engineering/agent-tasks.json')['tasks']
    eva=read(OUT/'evaluation/agent-prompts.json')
    tasks=[
      {'id':'K1','axis':'knowledge','skill':'amind','prompt':'只用分配给你的本地 AMind 资料：有人说《Claude-shaped science》证明 Anthropic 已官方拥有 BootLoops，且 Claude 可取代完整科学方法。请给 JSON {verdict,attribution,limits,sources}，sources 每项含 claim_id 与 URL。若本地资料不足，明确报告 unknown 和缺失项，不编造来源。'},
      {'id':'K2','axis':'knowledge','skill':'amind','prompt':'只用分配给你的本地资料：RL alignment auditor 拿到高分，就能用 concerningness 单点奖励替代人工安全审计吗？输出 JSON {recommendation,evidence,conditions,sources}，sources 每项含 claim_id 与 URL。若资料不足请明确 unknown，不把一般经验当作本地来源。'},
      {'id':'T1','axis':'timeliness','skill':'amind','prompt':'只用分配给你的本地资料判断：截至2026-10-18，10月8日公布的新 Usage Policy 是否已经生效？11月12日会如何？给 JSON {as_of,current_rule,future_rule,verification_limit,sources}，sources 每项含 claim_id 与 URL。不可联网；本地证据不足就明确 unknown，不把未来日期当已实时核验。'},
      {'id':'T2','axis':'timeliness','skill':'amind','prompt':'只用分配给你的本地资料判断：截至2026-10-18，七月网络事故的“模型认为自己在模拟中”是否仍应作为现行解释？输出 JSON {historical,current_assessment,remaining_uncertainty,sources}，sources 含 claim_id 与 URL。区分已知与未知，不可联网补资料。'},
    ]
    for tid,t in zip(['G1','G2'],eng[:2]):
        prompt=t['prompt'].replace('execute a tool, or modify files','perform external actions or modify files')
        tasks.append({'id':tid,'axis':'engineering','skill':'amind-engineering','prompt':prompt})
    for tid,t in zip(['V1','V2'],eva):tasks.append({'id':tid,'axis':'evaluation','skill':'eval-improve','prompt':t['prompt']})
    protocol={'schema_version':1,'purpose':'Exploratory same-model paired skill-use comparison; not production-distribution or universal quality proof',
      'phase':'diagnostic','requested_model':'gpt-6.1-sol','requested_effort':'ultra','model_basis':'unchanged user configured values',
      'timeout_seconds':360,'max_total_model_invocations':24,'main_invocations':16,'reserved_confirmation_invocations':8,
      'max_concurrency':3,'max_wall_seconds':5400,'retries':0,'seed':'amind-2026-10-18-paired-v1','tasks':tasks,
      'decision_rule':'Report each axis separately. A four-axis superiority claim requires positive evidence in every axis and no new hard failure. Unknown/unsupported is separate from incorrect. No significance claim from eight independent tasks.',
      'scoring':'Objective JSON/arithmetic and source-ID checks plus source-grounded AI adjudication; no human calibrated subjective judge. Rubrics frozen separately before outputs.',
      'snapshot_fingerprints':{k:v['tree_sha256'] for k,v in read(OUT/'snapshots.json')['variants'].items()},
      'isolation':'Per-run copied skills. Seatbelt denies repo/grader/installed skills and sibling runs; local canary verifies. Native web/apps/plugins/hooks/multiagent disabled identically. OS outbound inference and unrelated host files remain accessible; traces audited.',
      'trial_scope':'Knowledge retrieval and bounded offline engineering/evaluation decisions; executable helper capability tested separately by independent lanes.'}
    write(OUT/'agent-protocol.json',protocol)
    write(OUT/'agent-protocol-fingerprint.json',{'sha256':sha(OUT/'agent-protocol.json'),'frozen_before_target_execution':True})
    return protocol


def setup_runs(protocol,phase):
    isolation=read(SNAP/'os-isolation.json');base=Path(isolation['root'])
    plan_path=OUT/f'agent-{phase}-plan.json'
    if plan_path.exists():return read(plan_path)
    if phase=='diagnostic':tasks=protocol['tasks'];source={'old':SNAP/'old','new':SNAP/'new'};offset=0
    else:
        tasks=read(OUT/'confirmation-protocol.json')['tasks'];source={'old':SNAP/'old','repaired':SNAP/'repaired'};offset=16
    runs=[]
    for task in tasks:
        arms=list(source)
        if int(hashlib.sha256((protocol['seed']+task['id']).encode()).hexdigest(),16)%2:arms.reverse()
        for arm in arms:
            rid=f'R{offset+len(runs)+1:02d}';workspace=base/rid
            # R01/R02 contain only pre-model canary files from the envelope check.
            workspace.mkdir(exist_ok=True);skills=workspace/'skills'
            if skills.exists():raise ValueError('Run sources already exist: '+rid)
            selected=['amind'] if task['skill']=='amind' else ['amind-engineering','eval-improve']
            for name in selected:shutil.copytree(source[arm]/'skills'/name,skills/name)
            (workspace/'output').mkdir(exist_ok=True)
            write(workspace/'task.json',{'id':task['id'],'prompt':task['prompt']})
            runs.append({'run_id':rid,'case_id':task['id'],'axis':task['axis'],'arm':arm,'workspace':str(workspace),
              'skill':task['skill'],'skill_files':inventory(skills),'task_sha256':sha(workspace/'task.json')})
    plan={'phase':phase,'protocol_sha256':sha(OUT/'agent-protocol.json'),'runs':runs,'profile_name':isolation['profile_name'],'root':str(base)}
    write(plan_path,plan);return plan


def capture(run,plan,protocol):
    rid=run['run_id'];base=Path(plan['root']);workspace=Path(run['workspace']);dest=OUT/'agent-runs'/rid
    if dest.exists():raise ValueError('Refusing overwrite: '+rid)
    dest.mkdir(parents=True)
    if GLOBAL_DEADLINE is not None and time.time()>=GLOBAL_DEADLINE:
        result={'run_id':rid,'case_id':run['case_id'],'arm':run['arm'],'axis':run['axis'],
                'status':'global_budget_exhausted','model_launched':False,'usage':[],
                'elapsed_seconds':0,'grade':None}
        write(dest/'capture.json',result)
        with LOCK:
            with (OUT/'agent-execution-ledger.jsonl').open('a') as h:h.write(json.dumps(result)+'\n')
        return result
    protected=[str(ROOT),'/Users/damonalbarn/Work/AMind','/Users/damonalbarn/.codex/skills','/Users/damonalbarn/.codex/plugins',str(base/'control')]
    protected += [str(base/f'R{x:02d}') for x in range(1,25) if f'R{x:02d}'!=rid]
    policy='(version 1)\n(allow default)\n'+''.join('(deny file-read* file-write* (subpath '+json.dumps(p)+'))\n' for p in protected)
    policy+='(deny file-write* (subpath '+json.dumps(str(workspace/'skills'))+'))\n'
    policy+='(deny file-write* (literal "/Users/damonalbarn/.codex/config.toml") (literal "/Users/damonalbarn/.codex/auth.json"))\n'
    policy_path=base/'control'/(rid+'.sb');policy_path.write_text(policy)
    canary=subprocess.run(['/usr/bin/sandbox-exec','-f',str(policy_path),'/bin/cat',str(base/'control/canary.txt')],cwd=workspace,text=True,capture_output=True,timeout=5)
    if canary.returncode==0:raise ValueError('Grader canary readable')
    task=read(workspace/'task.json')
    prompt=('你在一个固定输入的技能对照任务中。先阅读本目录 skills/'+run['skill']+'/SKILL.md，按其中指导读取所需参考与本地证据。只能使用本目录的分配版本和本题输入。不得读取其他目录的技能、评测答案或其他执行结果，不得联网、调用下游模型、创建子agent或写入本目录以外文件。所有副作用仅限 output/。任务中“禁止工具”不禁止读取 assigned skill 与所需本地证据。若资料不足，明确unknown。输出以本题要求JSON为准；可以写 output/answer.json，并在最终回答重复完整JSON。时间上限6分钟，不要求扩写报告。\n\n'+task['prompt'])
    command=['/usr/bin/sandbox-exec','-f',str(policy_path),'/Users/damonalbarn/.local/bin/codex','--no-daemon','--profile',plan['profile_name'],'-a','never','exec','--json','--ephemeral','--sandbox','danger-full-access','--skip-git-repo-check','--color','never','--cd',str(workspace),'--output-last-message',str(workspace/'output/final.txt'),'-']
    started=time.monotonic();timed_out=False
    with (dest/'events.jsonl').open('wb') as stdout,(dest/'stderr.txt').open('wb') as stderr:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,cwd=workspace,start_new_session=True)
        remaining=protocol['timeout_seconds'] if GLOBAL_DEADLINE is None else min(protocol['timeout_seconds'],max(.01,GLOBAL_DEADLINE-time.time()))
        try:process.communicate(prompt.encode(),timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGKILL);process.communicate()
    events=[];bad=[]
    for line in (dest/'events.jsonl').read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:bad.append(line[:300])
    completed=[e for e in events if e.get('type')=='turn.completed'];errors=[e for e in events if e.get('type') in {'error','turn.failed'}]
    final=workspace/'output/final.txt';output=final.read_text() if final.exists() else ''
    unchanged=inventory(workspace/'skills')==run['skill_files']
    status='timeout' if timed_out else 'runtime_error' if process.returncode or errors else 'incomplete' if not output.strip() or len(completed)!=1 or bad else 'captured'
    if not unchanged:status='target_source_modified'
    result={'run_id':rid,'case_id':run['case_id'],'arm':run['arm'],'axis':run['axis'],'status':status,'returncode':process.returncode,'elapsed_seconds':round(time.monotonic()-started,3),'requested_model':protocol['requested_model'],'requested_effort':protocol['requested_effort'],'actual_served_model_verified':False,'usage':[e.get('usage') for e in completed],'errors':errors,'malformed_events':bad,'skill_unchanged':unchanged,'grader_canary_denied':True,'final':output,'command':command,'grade':None}
    shutil.copytree(workspace/'output',dest/'output',dirs_exist_ok=True);(dest/'prompt.txt').write_text(prompt);write(dest/'capture.json',result)
    with LOCK:
        with (OUT/'agent-execution-ledger.jsonl').open('a') as h:h.write(json.dumps({k:v for k,v in result.items() if k not in ['final','command']},ensure_ascii=False)+'\n')
        print(json.dumps({'run':rid,'case':run['case_id'],'arm':run['arm'],'status':status,'seconds':result['elapsed_seconds']},ensure_ascii=False),flush=True)
    return result


def execute(phase):
    global GLOBAL_DEADLINE
    protocol=read(OUT/'agent-protocol.json');plan=setup_runs(protocol,phase)
    GLOBAL_DEADLINE=(OUT/'agent-protocol.json').stat().st_mtime+protocol['max_wall_seconds']
    prior=list((OUT/'agent-runs').glob('*/capture.json')) if (OUT/'agent-runs').exists() else []
    if len(prior)+len(plan['runs'])>protocol['max_total_model_invocations']:raise ValueError('Invocation cap exceeded')
    started=time.monotonic();results=[]
    with concurrent.futures.ThreadPoolExecutor(protocol['max_concurrency']) as pool:
        futures=[pool.submit(capture,r,plan,protocol) for r in plan['runs']]
        for f in concurrent.futures.as_completed(futures):results.append(f.result())
    write(OUT/f'agent-{phase}-capture-summary.json',{'runs':len(results),'captured':sum(r['status']=='captured' for r in results),'elapsed_seconds':round(time.monotonic()-started,3),'graded':False,'results':[{'run_id':r['run_id'],'case_id':r['case_id'],'arm':r['arm'],'status':r['status']} for r in sorted(results,key=lambda r:r['run_id'])]})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','diagnostic','confirmation']);a=p.parse_args()
    if a.stage=='prepare':prepare();print('Frozen eight-task protocol; no model invocation.')
    else:execute(a.stage)
