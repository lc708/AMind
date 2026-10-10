"""Provider-neutral process adapter; no network/SDK or credential reads."""
import copy
import json
from pathlib import Path
import sys
from fixture_tools import FixtureTools, fresh_state
from mock_app import handle_ticket


def run(payload):
    ticket = payload['input']
    if set(ticket) != {'ticket', 'customer'} or not isinstance(ticket['ticket'], str):
        raise ValueError('only public ticket and customer may reach the application')
    context = payload['context']
    workspace = Path(context['workspace'])
    state = fresh_state(ticket['customer'])
    initial = copy.deepcopy(state)
    tools = FixtureTools(state)
    base = {'synthetic': True, 'model': 'synthetic-local-contract-v1', 'cost_usd': 0,
            'usage': {'input_tokens': 0, 'output_tokens': 0}}
    if context.get('config', {}).get('simulate_timeout_customer') == ticket['customer']:
        # Classified, deterministic service-failure fixture; not elapsed-time measurement.
        return {**base, 'error': {'kind': 'timeout', 'retryable': False}}
    output = handle_ticket(copy.deepcopy(ticket), tools, state)
    receipt = {'initial_state': initial, 'events': tools.events, 'final_state': state}
    (workspace / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return {**base, 'status': 'ok', 'output': output,
            'transcript': [{'role':'user','content':ticket},
                           {'role':'tool','content':receipt},
                           {'role':'assistant','content':output}]}


if __name__ == '__main__':
    print(json.dumps(run(json.load(sys.stdin))))
