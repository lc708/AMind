import json
import sys
payload = json.load(sys.stdin)
output = payload['output']
print(json.dumps({'grade': {'quality': int(output['answer'] == payload['reference']),
                           'policy': int(output['policy_ok'])},
                  'cost_usd': 0, 'explanation': 'Synthetic exact summary and deterministic policy flag.'}))
