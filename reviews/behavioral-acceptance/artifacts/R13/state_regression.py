"""Offline state-contract repair for task G03. No SDK, transport, or tool I/O.

The fixture's wire format is retained. This is a local contract checker, not
an implementation or validation of a remote provider's complete API schema.
"""
from copy import deepcopy
import json
from pathlib import Path


class StateError(ValueError):
    pass


def pending_calls(previous):
    calls = {}
    for item in previous['output']:
        if item.get('type') == 'function_call':
            call_id = item.get('call_id')
            if not isinstance(call_id, str) or not call_id:
                raise StateError('MISSING_CALL_ID')
            if call_id in calls:
                raise StateError('DUPLICATE_CALL_ID: ' + call_id)
            calls[call_id] = item
    return calls


def check_results(previous, results):
    """Require exactly one result per pending call; never repair IDs by position."""
    pending = pending_calls(previous)
    seen = set()
    for result in results:
        if result.get('type') != 'function_call_output':
            raise StateError('NOT_A_TOOL_RESULT')
        call_id = result.get('call_id')
        if call_id not in pending:
            raise StateError('UNKNOWN_CALL_ID: ' + str(call_id))
        if call_id in seen:
            raise StateError('DUPLICATE_RESULT: ' + call_id)
        if 'output' not in result:
            raise StateError('MISSING_RESULT_OUTPUT: ' + call_id)
        seen.add(call_id)
    missing = set(pending) - seen
    if missing:
        raise StateError('MISSING_RESULTS: ' + ', '.join(sorted(missing)))


def build_stateful(previous, results, *, new_input=()):
    """Reference previous state; include only completed tools and NEW input.

    Caller must classify historical versus new user input. No text-based
    deduplication occurs. This helper cannot determine that provenance.
    """
    check_results(previous, results)
    if not previous.get('id'):
        raise StateError('MISSING_RESPONSE_ID')
    return {
        'previous_response_id': previous['id'],
        'input': deepcopy(list(results) + list(new_input)),
    }


def append_response(history, response):
    """Losslessly preserve every output item, field, phase, and opaque payload."""
    return deepcopy(list(history) + response['output'])


def build_manual(prior_history, previous, results, *, new_input=()):
    """Replay explicitly supplied full history without a server-state pointer."""
    check_results(previous, results)
    history = append_response(prior_history, previous)
    return {'input': history + deepcopy(list(results) + list(new_input))}


def diagnose(previous, request, *, prior_history=None):
    """Return fixture-level findings. Replay matching diagnoses, never deletes."""
    findings = []
    def add(code, location, detail):
        findings.append({'code': code, 'location': location, 'detail': detail})
    items = request['input']
    reference_mode = 'previous_response_id' in request
    if reference_mode and request['previous_response_id'] != previous['id']:
        add('WRONG_RESPONSE_ID', 'previous_response_id', 'Reference does not name the supplied response.')
    prior_output = previous['output']
    for index, item in enumerate(items):
        for old in prior_output:
            same_message = (
                old.get('type') == 'message' and item.get('type') == 'message'
                and old.get('role') == item.get('role') == 'assistant'
                and old.get('content') == item.get('content')
            )
            if same_message and old.get('phase') != item.get('phase'):
                add('PHASE_CHANGED_OR_LOST', f'input[{index}].phase',
                    f"Expected original phase {old.get('phase')!r}; got {item.get('phase')!r}.")
            if reference_mode and (old == item or same_message):
                add('REPLAY_WITH_REFERENCE', f'input[{index}]',
                    'Prior output appears again alongside its state reference; use one ownership mode.')
                break
    results = [item for item in items if item.get('type') == 'function_call_output']
    pending = pending_calls(previous)
    seen = set()
    for index, result in enumerate(results):
        call_id = result.get('call_id')
        if call_id not in pending:
            add('UNKNOWN_CALL_ID', f'tool_results[{index}].call_id', f'{call_id!r} has no matching pending call.')
        elif call_id in seen:
            add('DUPLICATE_RESULT', f'tool_results[{index}]', f'{call_id!r} is already resolved.')
        else:
            seen.add(call_id)
        if 'output' not in result:
            add('MISSING_RESULT_OUTPUT', f'tool_results[{index}]', 'Tool result has no output field.')
    for call_id in sorted(set(pending) - seen):
        add('MISSING_RESULT', 'input', f'Pending call {call_id!r} has no matching result.')
    if not reference_mode:
        if prior_history is None:
            add('HISTORY_REQUIRED', 'input', 'Manual replay validation requires the known prior history.')
        else:
            expected = append_response(prior_history, previous)
            if items[:len(expected)] != expected:
                add('HISTORY_NOT_PRESERVED', 'input', 'Full original history and response output must remain ordered and unchanged.')
    return findings


def mock_read(call, fixed_output):
    """Fixture-only tool dispatcher. Never reads a file or executes a command."""
    if call.get('name') != 'read' or json.loads(call['arguments']) != {}:
        raise StateError('UNSUPPORTED_MOCK_CALL')
    return {'type': 'function_call_output', 'call_id': call['call_id'],
            'output': deepcopy(fixed_output)}


def run_demo(task):
    fixture = task['fixture']
    previous = fixture['previous_response']
    broken = fixture['next_request']
    findings = diagnose(previous, broken)
    # This is an explicit fixture assumption, not automatic history inference.
    prior_history = [deepcopy(broken['input'][0])]
    fixed_output = broken['input'][2]['output']
    results = [mock_read(call, fixed_output) for call in pending_calls(previous).values()]
    stateful = build_stateful(previous, results)
    manual = build_manual(prior_history, previous, results)
    # Also exhibit the other interpretation without silently dropping user input.
    fresh_user_variant = build_stateful(previous, results, new_input=prior_history)
    compacted_response = {'output': [deepcopy(fixture['later_compaction'])]}
    later_history = append_response(manual['input'], compacted_response)
    roundtrip = json.loads(json.dumps(later_history, ensure_ascii=False))
    assert roundtrip == later_history
    assert roundtrip[-1] == fixture['later_compaction']
    after = {
        'stateful': diagnose(previous, stateful),
        'manual': diagnose(previous, manual, prior_history=prior_history),
        'fresh_user_variant': diagnose(previous, fresh_user_variant),
    }
    assert all(not issues for issues in after.values())
    return {
        'evidence_type': 'local fixed fixture; no API requests or model behavior measured',
        'assumption': 'Find invoice is the initial turn already represented by r1. If it is new, use fresh_user_variant.',
        'tool_output_provenance': 'Rebound by a local mock execution of call c1 with fixed output invoice. The corrupted wrong result is rejected, not auto-renamed.',
        'before_findings': findings,
        'after_findings': after,
        'stateful': stateful,
        'manual': manual,
        'fresh_user_variant': fresh_user_variant,
        'later_history_with_compaction': roundtrip,
    }


if __name__ == '__main__':
    directory = Path(__file__).resolve().parent
    task = json.loads((directory / 'task.json').read_text())
    report = run_demo(task)
    (directory / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Offline reproduction: ' + ', '.join(item['code'] for item in report['before_findings']))
    print('Fixed requests: 0 local contract findings; opaque compaction round-trip preserved.')
    print('Wrote verification.json; no network or SDK clients are present.')
