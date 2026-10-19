import json,os
def perform(context,path):
    # Simulated external receiver. Every invocation is observable, even on crash.
    payload=context.get('payload') or {};stage=context['stage']
    outcome={'status':'failed' if payload.get(stage)=='fail' else 'succeeded','output':{'item':context['item'],'stage':stage}}
    receipt={**context,'outcome':outcome}
    with path.open('a') as f:
        f.write(json.dumps(receipt)+'\n');f.flush();os.fsync(f.fileno())
    if payload.get('crash_after_effect')==stage:os._exit(17)
    return outcome
