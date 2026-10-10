"""Identical local follow-up of available-usage retention; not a new agent run."""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENTS = [
    {'type': 'response.in_progress', 'response': {'usage': {'output_tokens': 17}}},
    {'type': 'response.output_text.delta', 'delta': 'partial'},
]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def usage_evidence(value):
    found = []
    if isinstance(value, dict):
        if isinstance(value.get('usage'), dict):
            found.append(value['usage'])
        for child in value.values():
            found.extend(usage_evidence(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(usage_evidence(child))
    return found


def main():
    functions = {
        'R09': load('r09_contract', 'artifacts/R09/response_contract.py').terminal_stream,
        'R17': load('r17_contract', 'artifacts/R17/result_contract.py').judge_stream,
    }
    outcomes = {}
    for run, evaluate in functions.items():
        result = evaluate(EVENTS)
        outcomes[run] = {'output': result, 'retained_available_usage':
                         {'output_tokens': 17} in usage_evidence(result)}
    print(json.dumps({'scope': 'Root-authored local probe, same input on original artifacts; partial usage is evidence, not a final bill',
                      'input': EVENTS, 'outcomes': outcomes}, indent=2))


if __name__ == '__main__':
    main()
