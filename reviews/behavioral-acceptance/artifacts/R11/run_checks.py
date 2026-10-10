"""Replay offline tests, original evidence audit, complete mock run, and timeout probe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SKILL = Path('/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/sources/P/eval-improve')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='evidence')
    args = parser.parse_args()
    out = (ROOT/args.out).resolve()
    if not out.is_relative_to(ROOT):
        raise ValueError('output must stay in task directory')
    out.mkdir(exist_ok=True, parents=True)
    commands = [[sys.executable,'-B','-m','unittest','-v','test_evaluation.py'],
                [sys.executable,'-B','audit.py']]
    for card, suffix in [('experiment.json','contract-val'),('timeout-experiment.json','timeout-val')]:
        flow = out/suffix
        runner = [sys.executable,'-B',str(SKILL/'scripts/run_eval.py'),'--card',card,
                  '--flow',str(flow),'--variant','baseline','--split','val']
        commands.append(runner)
        commands.append(runner+['--execute']+(['--resume'] if (flow/'baseline/manifest.json').exists() else []))
        commands.append([sys.executable,'-B',str(SKILL/'scripts/report_eval.py'),str(flow)])
    records=[]
    for index, command in enumerate(commands):
        result = subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        record={'argv':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        records.append(record)
        (out/'checks.json').write_text(json.dumps(records,indent=2)+'\n')
        (out/f'check-{index:02d}.log').write_text(result.stdout+result.stderr)
        print(f'check {index}: exit {result.returncode} : '+ ' '.join(command),flush=True)
        # An incomplete fixture probe is expected; verify its evidence below.
        if result.returncode and '--execute' not in command:
            raise RuntimeError(result.stderr or result.stdout)
    summary={}
    for suffix in ('contract-val','timeout-val'):
        folder=out/suffix/'baseline'
        rows=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
        attempts=[json.loads(line) for line in (folder/'attempts.jsonl').read_text().splitlines()]
        finishes=[a for a in attempts if a['event']=='finished']
        summary[suffix]={'planned':3,'scored':len(rows),'coverage':len(rows)/3,
                         'finished_attempts':len(finishes),
                         'failures':[a['status'] for a in finishes if a['status']!='ok'],
                         'quality_scored_only':sum(r['grade']['quality'] for r in rows)/len(rows),
                         'confirmed_success_over_planned':sum(r['grade']['quality'] for r in rows)/3,
                         'known_api_cost_usd':sum(a['cost_usd'] for a in finishes),
                         'synthetic':True,'migration_eligible':False}
    assert summary['contract-val']['scored']==3
    assert summary['timeout-val']['scored']==2
    assert summary['timeout-val']['failures']==['timeout']
    assert summary['timeout-val']['finished_attempts']==3
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
