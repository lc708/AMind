"""Synthetic local support workflow used only to exercise the real eval runner."""
import json
import os
from pathlib import Path
import sys
import time

payload = json.load(sys.stdin)
context, case = payload['context'], payload['input']
home = Path(__file__).resolve().parent
marker = home / ('seen-' + context['variant'] + '-' + context['case_id'])
if context['variant'] == 'baseline' and case.get('pause_once') and not marker.exists():
    marker.write_text('attempt dispatched; no completed result or cost receipt')
    (home / 'paused-worker.json').write_text(json.dumps({'pid': os.getpid(), 'case_id': context['case_id']}))
    time.sleep(60)
answer = case['requested_summary']
if context['config']['uppercase']:
    answer = answer.upper()
print(json.dumps({'output': {'answer': answer, 'policy_ok': context['config']['policy_ok']},
                  'cost_usd': .05, 'synthetic': True, 'model': 'offline-support-fixture'}))
