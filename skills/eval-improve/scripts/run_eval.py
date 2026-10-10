#!/usr/bin/env python3
"""Provider-neutral, resumable application/grader runner. Plan unless --execute is given."""

import argparse
import concurrent.futures
import copy
import json
import math
import os
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from kernel_common import (SCHEMA, append_json, atomic, canonical, command_spec, file_hashes,
                           finite, in_root, read_bytes, read_json, read_jsonl, regular,
                           safe_dir, sha, unique_ids, write_json, contract_hash)


class RunError(Exception):
    def __init__(self, kind, message, retryable=False, observed=None):
        super().__init__(message)
        self.kind, self.retryable, self.observed = kind, retryable, observed or {}


def positive(value, name, integer=False, maximum=None):
    if not finite(value) or value <= 0 or (integer and type(value) is not int) or (maximum and value > maximum):
        raise ValueError(f"invalid {name}")
    return value


def projection(config, mutable):
    result = copy.deepcopy(config)
    for dotted in mutable:
        if not isinstance(dotted, str) or not dotted or '*' in dotted:
            raise ValueError("mutable_config contains explicit dotted paths, not wildcards")
        node = result
        pieces = dotted.split('.')
        for key in pieces[:-1]:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict):
            node.pop(pieces[-1], None)
    return result


def prepare(card_path, variant, split, reps, selection=None):
    card_path = card_path.resolve()
    base = card_path.parent
    card = read_json(card_path)
    if card.get('schema_version') != SCHEMA:
        raise ValueError('experiment card must use schema_version 2')
    if variant != 'baseline' and not __import__('re').fullmatch(r'v[1-9][0-9]*', variant):
        raise ValueError('variant must be baseline or v1, v2, ...')
    cases = read_jsonl(base / card['cases'])
    by_id = unique_ids(cases)
    for case in cases:
        if set(case) - {'id', 'input', 'tags', 'group'} or 'input' not in case:
            raise ValueError('public cases contain only id/input/tags/group; references stay separate')
        if not isinstance(case.get('tags', []), list) or any(not isinstance(t, str) for t in case.get('tags', [])):
            raise ValueError('tags must be strings')
        if 'group' in case and (not isinstance(case['group'], str) or not case['group']):
            raise ValueError('group must be a nonempty independent-group ID')
    splits = card.get('splits', {})
    seen, groups = set(), {}
    for name in ('train', 'val', 'test'):
        ids = splits.get(name, [])
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in by_id for i in ids):
            raise ValueError(f'{name} contains unknown case IDs')
        if len(ids) != len(set(ids)) or seen.intersection(ids):
            raise ValueError('duplicate or overlapping split IDs')
        seen.update(ids)
        for key in ids:
            group = by_id[key].get('group', key)
            if group in groups and groups[group] != name:
                raise ValueError('related case group crosses split boundary')
            groups[group] = name
    if seen != set(by_id) or not splits.get(split):
        raise ValueError('assign every case exactly once and select a nonempty split')
    references = {}
    if card.get('references'):
        references = unique_ids(read_jsonl(base / card['references']))
        if set(references) != set(by_id):
            raise ValueError('reference IDs must match public case IDs')
    metric_specs = card.get('metrics')
    if not isinstance(metric_specs, list) or not metric_specs:
        raise ValueError('declare at least one metric')
    metric_ids = []
    for metric in metric_specs:
        if not isinstance(metric, dict): raise ValueError('each metric must be an object')
        key = metric.get('id')
        if not isinstance(key, str) or not key or key in metric_ids:
            raise ValueError('metric IDs must be unique nonempty strings')
        if metric.get('better', 'higher') not in ('higher', 'lower'):
            raise ValueError('metric better must be higher/lower')
        for bound in ('min', 'max'):
            if bound in metric and not finite(metric[bound]): raise ValueError('metric bounds must be finite numbers')
        if 'min' in metric and 'max' in metric and metric['min'] > metric['max']:
            raise ValueError('metric minimum exceeds maximum')
        metric_ids.append(key)
    runner = command_spec(card['runner'], base)
    grader = copy.deepcopy(card['grader'])
    if grader.get('kind') == 'command':
        grader.update(command_spec(grader, base))
    elif grader.get('kind') not in ('exact', 'json_fields', 'artifact_checks'):
        raise ValueError('grader kind must be exact/json_fields/artifact_checks/command')
    elif len(metric_ids) != 1:
        raise ValueError('built-in graders produce one declared metric; use a command for multiple metrics')
    if grader.get('kind') != 'command' and not references:
        raise ValueError('built-in graders require separate reference data')
    variants = card.get('variants', {})
    if 'baseline' not in variants or variant not in variants:
        raise ValueError('declare baseline and selected variant')
    mutable = card.get('mutable_config', [])
    if not isinstance(mutable, list):
        raise ValueError('mutable_config must be a list')
    configs = {name: value.get('config', {}) for name, value in variants.items()}
    if any(not isinstance(v, dict) for v in configs.values()):
        raise ValueError('variant config must be an object')
    fixed = projection(configs['baseline'], mutable)
    if any(projection(value, mutable) != fixed for value in configs.values()):
        raise ValueError('variant changes undeclared fixed configuration; declare the treatment axes')
    treatment = variants[variant]
    if not treatment.get('files'):
        raise ValueError('each variant must list actual target files; labels alone are not snapshots')
    target = {'files': file_hashes(base, treatment['files']), 'config': configs[variant],
              'expected_model': treatment.get('expected_model')}
    if target['expected_model'] is not None and (not isinstance(target['expected_model'], str) or not target['expected_model']):
        raise ValueError('expected_model must be a nonempty exact served identity or null')
    workspace = card.get('workspace', {})
    workspace_files = file_hashes(base, workspace.get('files', []))
    for name in workspace_files:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('workspace fixture paths must be relative within the card directory')
    control_files = file_hashes(base, card.get('control_files', []))
    for name in ('dataset_version', 'grader_version', 'task'):
        if not isinstance(card.get(name), str) or not card[name]:
            raise ValueError(f'declare {name}')
    identity = {'dataset': sha(sorted(cases, key=lambda c: c['id'])),
                'references': sha(references), 'dataset_version': card['dataset_version'],
                'grader': grader, 'grader_version': card['grader_version'],
                'runner': runner, 'metrics': metric_specs, 'splits': splits,
                'fixed_config': fixed, 'mutable_config': sorted(mutable),
                'workspace_files': workspace_files, 'control_files': control_files,
                'task': card['task'], 'reps': reps, 'split': split,
                'case_groups': {key: by_id[key].get('group', key) for key in splits[split]},
                'kernel': {p.name: sha(read_bytes(p)) for p in (Path(__file__), Path(__file__).with_name('kernel_common.py'))}}
    limits = {'max_attempts': len(splits[split]) * reps, 'concurrency': 1,
              'timeout_s': 120, 'retries': 0, 'max_output_bytes': 4 * 1024 * 1024,
              'max_total_seconds': 3600, **card.get('limits', {})}
    if set(limits) - {'max_attempts','concurrency','timeout_s','retries','max_output_bytes','max_total_seconds','max_cost_usd','reservation_usd_per_attempt'}:
        raise ValueError('unknown limit field; check the experiment card before executing')
    positive(reps, 'reps', True)
    for name in ('max_attempts', 'concurrency', 'max_output_bytes'):
        positive(limits[name], name, True)
    positive(limits['concurrency'], 'concurrency', True, 32)
    positive(limits['timeout_s'], 'timeout_s')
    positive(limits['max_total_seconds'], 'max_total_seconds')
    if type(limits['retries']) is not int or not 0 <= limits['retries'] <= 10:
        raise ValueError('retries must be 0..10')
    if limits['retries'] and not runner['retry_safe']:
        raise ValueError('retries require runner.retry_safe=true after side-effect/idempotency review')
    if len(splits[split]) * reps > limits['max_attempts']:
        raise ValueError('planned case attempts exceed max_attempts')
    if limits.get('max_cost_usd') is not None:
        positive(limits['max_cost_usd'], 'max_cost_usd')
        positive(limits.get('reservation_usd_per_attempt'), 'reservation_usd_per_attempt')
    manifest = {'schema_version': SCHEMA, 'variant': variant, 'split': split, 'reps': reps,
                'comparison_identity': identity, 'comparison_hash': sha(identity),
                'treatment': target, 'treatment_hash': sha(target), 'limits': limits,
                'isolation': 'separate input/grader channels; filesystem/network isolation not established',
                'status': 'planned', 'results_sha256': None}
    if split == 'test':
        if selection is None: raise ValueError('final test requires --selection from frozen validation evidence')
        from seal_selection import verify
        manifest['selection_certificate_hash'] = verify(selection, manifest)
    return {'card': card, 'base': base, 'cases': by_id, 'references': references,
            'runner': runner, 'grader': grader, 'manifest': manifest,
            'workspace_files': workspace_files, 'selected': splits[split], 'metrics': metric_specs}


def terminate(process):
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def invoke(command, cwd, payload, deadline, byte_limit, workspace):
    """Bound output while reading; never execute a shell or interpolate a prompt into argv."""
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()
    argv = [arg.replace('{workspace}', str(workspace)) for arg in command]
    environment = {**os.environ, 'AMIND_CASE_WORKSPACE': str(workspace)}
    with tempfile.TemporaryFile() as source:
        source.write(canonical(payload).encode('utf-8')); source.seek(0)
        process = subprocess.Popen(argv, cwd=cwd, stdin=source, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=environment, start_new_session=(os.name == 'posix'))
        def drain(stream, index):
            try:
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    remaining = byte_limit - len(buffers[index])
                    buffers[index].extend(chunk[:max(0, remaining)])
                    if len(chunk) > remaining:
                        exceeded.set()
                        break
            finally:
                stream.close()
        readers = [threading.Thread(target=drain, args=(stream, index), daemon=True)
                   for index, stream in enumerate((process.stdout, process.stderr))]
        for reader in readers:
            reader.start()
        failure = None
        try:
            while process.poll() is None or any(reader.is_alive() for reader in readers):
                if exceeded.is_set():
                    failure = RunError('output_limit', 'adapter exceeded its output byte ceiling')
                    break
                if time.monotonic() >= deadline:
                    failure = RunError('timeout', 'case wall-clock ceiling reached', retryable=True)
                    break
                time.sleep(.01)
        except BaseException:
            terminate(process)
            process.wait()
            raise
        if failure:
            terminate(process)
        process.wait()
        for reader in readers:
            reader.join(timeout=1)
        if exceeded.is_set() and not failure:
            failure = RunError('output_limit', 'adapter exceeded its output byte ceiling')
        if failure:
            raise failure
        try:
            result = json.loads(buffers[0].decode('utf-8'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        except (ValueError, UnicodeError):
            raise RunError('protocol', 'adapter must emit one finite JSON object; raw stderr is not exposed')
        if not isinstance(result, dict):
            raise RunError('protocol', 'adapter output must be an object')
        if process.returncode or result.get('error'):
            problem = result.get('error', {})
            if not isinstance(problem, dict): problem = {}
            raise RunError(problem.get('kind', 'adapter_error'), 'adapter reported failure',
                           problem.get('retryable') is True, result)
        return result


def grade_builtin(kind, output, expected, options, workspace, metric):
    if kind == 'exact':
        if options.get('strip') and isinstance(output, str) and isinstance(expected, str):
            output, expected = output.strip(), expected.strip()
        passed = type(output) is type(expected) and output == expected
    elif kind == 'json_fields':
        if isinstance(output, str):
            try: output = json.loads(output)
            except ValueError: output = None
        if not isinstance(expected, dict):
            raise ValueError('json_fields expected is an object mapping dotted paths to values')
        passed = True
        missing = object()
        for dotted, value in expected.items():
            found = output
            for key in dotted.split('.'):
                found = found.get(key, missing) if isinstance(found, dict) else missing
            passed = passed and type(found) is type(value) and found == value
    else:
        if not isinstance(expected, dict) or not isinstance(expected.get('files'), dict):
            raise ValueError('artifact_checks expected contains files: {relative_path: exact_text}')
        passed = True
        for name, value in expected['files'].items():
            try:
                actual = read_bytes(in_root(workspace, name)).decode('utf-8')
                passed = passed and actual == value
            except FileNotFoundError:
                passed = False
        for name in expected.get('absent', []):
            passed = passed and not in_root(workspace, name).exists()
        if 'allowed_files' in expected:
            actual_files = set()
            for path in workspace.rglob('*'):
                if path.is_symlink():
                    raise ValueError('linked workspace artifact')
                if path.is_file(): actual_files.add(path.relative_to(workspace).as_posix())
            passed = passed and actual_files <= set(expected['allowed_files'])
    return {'grade': {metric: int(passed)}}


def validate_grade(result, metrics):
    grade = result.get('grade')
    if not isinstance(grade, dict) or set(grade) != {metric['id'] for metric in metrics}:
        raise RunError('grader_schema', 'grader must return every declared metric and no undeclared metric')
    for metric in metrics:
        value = grade[metric['id']]
        if isinstance(value, bool): value = int(value); grade[metric['id']] = value
        if not finite(value): raise RunError('grader_schema', 'grade must be finite')
        if metric.get('kind') == 'binary' and value not in (0, 1):
            raise RunError('grader_schema', 'binary grade must be 0 or 1')
        if metric.get('min') is not None and value < metric['min']:
            raise RunError('grader_schema', 'grade below declared scale')
        if metric.get('max') is not None and value > metric['max']:
            raise RunError('grader_schema', 'grade above declared scale')
    return grade


def declared_cost(observed):
    value = observed.get('cost_usd')
    if value is None: return None
    if not finite(value) or value < 0: raise RunError('usage_schema', 'cost must be finite, nonnegative or absent')
    return value


def check_files(prepared):
    manifest = prepared['manifest']
    groups = [manifest['treatment']['files'], prepared['workspace_files'],
              manifest['comparison_identity']['control_files'], prepared['runner']['files']]
    if prepared['grader']['kind'] == 'command': groups.append(prepared['grader']['files'])
    for expected in groups:
        if file_hashes(prepared['base'], list(expected)) != expected:
            raise RunError('file_drift', 'target, adapter, grader, control or fixture files changed during run')


def run(prepared, flow, resume=False, retry_errors=False):
    root = safe_dir(flow)
    manifest = prepared['manifest']; variant = manifest['variant']; limits = manifest['limits']
    directory = root / variant
    if directory.is_symlink(): raise ValueError('variant must not be a symlink')
    existed = directory.exists()
    if existed and not resume: raise ValueError('variant exists; use --resume without changing the experiment')
    directory.mkdir(exist_ok=True)
    lock = in_root(directory, '.run.lock')
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.write(fd, canonical({'pid': os.getpid(), 'started_at': time.time()}).encode()); os.close(fd)
    try:
        previous = read_json(directory / 'manifest.json') if existed else None
        if previous:
            for key in ('comparison_hash', 'treatment_hash', 'limits'):
                if previous.get(key) != manifest[key]:
                    raise ValueError(f'cannot resume after {key} changed; use a new variant/flow')
            contract_hash(previous)
        events_path = in_root(directory, 'attempts.jsonl')
        events = read_jsonl(events_path) if events_path.exists() else []
        if previous and previous.get('attempts_sha256') != sha(read_bytes(events_path)):
            raise ValueError('attempt journal changed or export was interrupted; reconcile before resume')
        starts = {e['attempt_id']: e for e in events if e.get('event') == 'started'}
        finishes = {e['attempt_id']: e for e in events if e.get('event') == 'finished'}
        if set(starts) != set(finishes):
            raise ValueError('interrupted attempt has unknown outcome/cost; reconcile it before resume; do not retry side effects blindly')
        if len(events) != len(starts) + len(finishes):
            raise ValueError('duplicate or unknown attempt journal events')
        results_path = in_root(directory, 'results.jsonl')
        rows = read_jsonl(results_path) if results_path.exists() else []
        keys = [(r['prompt_id'], r['rep']) for r in rows]
        if len(keys) != len(set(keys)): raise ValueError('duplicate completed result keys')
        if previous and previous.get('results_sha256') != sha(read_bytes(results_path)):
            raise ValueError('stored results changed since last export')
        failed_keys = {(e['prompt_id'], e['rep']) for e in finishes.values() if e['status'] != 'ok'} - set(keys)
        if failed_keys and not retry_errors: raise ValueError('failed cases exist; --retry-errors explicitly retries within the original budget')
        if failed_keys and retry_errors and not prepared['runner']['retry_safe']:
            raise ValueError('retry-errors requires a reviewed retry_safe adapter')
        state = {'metrics': prepared['metrics'], 'reps': manifest['reps'],
                 **{name + '_ids': prepared['card']['splits'].get(name, []) for name in ('train', 'val', 'test')}}
        state_file = in_root(root, '_state.json')
        if state_file.exists() and read_json(state_file) != state:
            raise ValueError('flow state differs; use a separate flow for a different experiment')
        write_json(root, '_state.json', state)
        if not results_path.exists(): atomic(directory, 'results.jsonl', '')
        if not events_path.exists(): atomic(directory, 'attempts.jsonl', '')
        manifest['status'] = 'running'
        manifest['results_sha256'] = sha(read_bytes(results_path))
        manifest['attempts_sha256'] = sha(read_bytes(events_path))
        manifest['first_started_at'] = previous['first_started_at'] if previous else time.time()
        manifest['deadline_at'] = manifest['first_started_at'] + limits['max_total_seconds']
        write_json(directory, 'manifest.json', manifest)
        guard = threading.RLock(); stopping = threading.Event()
        accounted = [e.get('cost_usd') for e in finishes.values()]
        case_costs = {}
        for event in finishes.values():
            case_costs.setdefault((event['prompt_id'], event['rep']), []).append(event.get('cost_usd'))
        spent = [sum(e.get('known_cost_usd', e.get('cost_usd') or 0.0) for e in finishes.values())]
        unknown = [sum(value is None for value in accounted)]
        reserved = [0.0]; attempted = [len(starts)]; errors = []
        overall_deadline = time.monotonic() + max(0, manifest['deadline_at'] - time.time())
        if limits.get('max_cost_usd') is not None and unknown[0]:
            raise ValueError('unknown historical cost prevents budgeted resume')
        baseline_refs = {}
        if variant != 'baseline':
            reference_path = in_root(root, 'baseline/frozen-outputs.json') if (root / 'baseline').exists() else root / 'baseline/frozen-outputs.json'
            if reference_path.exists():
                baseline_manifest = read_json(in_root(root, 'baseline/manifest.json'))
                if (contract_hash(baseline_manifest) != manifest['comparison_hash']
                        or baseline_manifest.get('status') != 'complete'
                        or baseline_manifest.get('results_sha256') != sha(read_bytes(in_root(root, 'baseline/results.jsonl')))
                        or baseline_manifest.get('frozen_outputs_sha256') != sha(read_bytes(reference_path))):
                    raise ValueError('baseline reference identity/integrity mismatch')
                baseline_refs = read_json(reference_path)
                manifest['baseline_reference_sha256'] = sha(read_bytes(reference_path))
            elif prepared['grader'].get('requires_baseline'):
                raise ValueError('this grader requires frozen baseline outputs')

        def task(case_id, rep):
            case = prepared['cases'][case_id]
            cached_application = None
            task_started = time.monotonic()
            case_deadline = min(overall_deadline, task_started + limits['timeout_s'])
            for retry in range(limits['retries'] + 1):
                with guard:
                    ceiling = limits.get('max_cost_usd')
                    reservation = limits.get('reservation_usd_per_attempt', 0.0)
                    if (stopping.is_set() or time.monotonic() >= case_deadline
                            or attempted[0] >= limits['max_attempts']
                            or (ceiling is not None and spent[0] + reserved[0] + reservation > ceiling)):
                        return
                    attempted[0] += 1; reserved[0] += reservation
                    attempt_id = attempted[0]
                    append_json(directory, 'attempts.jsonl', {'event': 'started', 'attempt_id': attempt_id,
                                'prompt_id': case_id, 'rep': rep, 'reserved_usd': reservation, 'time': time.time()})
                    manifest['attempts_sha256'] = sha(read_bytes(events_path))
                    write_json(directory, 'manifest.json', manifest)
                started = time.monotonic(); deadline = case_deadline
                stem = sha({'case': case_id, 'rep': rep, 'attempt': attempt_id})[:24]
                workspace = directory / 'workspaces' / stem
                observed, judged = {}, {}; failure = None; stage = 'setup'
                reused_application = cached_application is not None
                try:
                    check_files(prepared)
                    # Validate each parent before creating a case workspace.
                    if reused_application:
                        observed, workspace, application_attempt = cached_application
                    else:
                        in_root(directory, f'workspaces/{stem}/.marker', create_parent=True)
                        for relative in prepared['workspace_files']:
                            atomic(workspace, relative, read_bytes(prepared['base'] / relative))
                    payload = {'input': case['input'], 'context': {'case_id': case_id, 'rep': rep,
                               'variant': variant, 'config': manifest['treatment']['config'], 'workspace': str(workspace)}}
                    adapter = prepared['runner']
                    stage = 'application'
                    if not reused_application:
                        observed = invoke(adapter['command'], adapter['cwd'], payload, deadline, limits['max_output_bytes'], workspace)
                        application_attempt = attempt_id
                    if 'output' not in observed: raise RunError('protocol', 'application output field is required')
                    expected_model = manifest['treatment']['expected_model']
                    if expected_model and observed.get('model') != expected_model:
                        raise RunError('serving_substitution', 'served model is absent or differs from the explicit pin')
                    if observed.get('status', 'ok') != 'ok':
                        raise RunError(observed.get('status', 'incomplete'), 'application returned an unscorable status')
                    cached_application = (observed, workspace, application_attempt)
                    grader = prepared['grader']; reference = prepared['references'].get(case_id, {}).get('expected')
                    stage = 'grader'
                    if grader['kind'] == 'command':
                        judged = invoke(grader['command'], grader['cwd'],
                                        {'input': case['input'], 'output': observed['output'], 'reference': reference,
                                         'baseline_output': baseline_refs.get(case_id), 'workspace': str(workspace)},
                                        deadline, limits['max_output_bytes'], workspace)
                    else:
                        judged = grade_builtin(grader['kind'], observed['output'], reference,
                                               grader.get('options', {}), workspace, prepared['metrics'][0]['id'])
                    grades = validate_grade(judged, prepared['metrics'])
                    check_files(prepared)
                    transcript = observed.get('transcript', [{'role': 'user', 'content': case['input']},
                                                           {'role': 'assistant', 'content': observed['output']}])
                    write_json(directory, f'traces/{stem}.json', transcript)
                    row = {'prompt_id': case_id, 'rep': rep, 'status': 'ok', 'grade': grades,
                           'prompt': case['input'], 'tags': case.get('tags', []), 'group': case.get('group', case_id),
                           'output': observed['output'], 'model': observed.get('model'), 'usage': observed.get('usage'),
                           'judge_model': judged.get('model'), 'judge_usage': judged.get('usage'),
                           'latency_s': time.monotonic() - task_started, 'trace_file': f'traces/{stem}.json',
                           'attempt_id': attempt_id, 'explanation': judged.get('explanation'),
                           'meta': {'synthetic': observed.get('synthetic', False), 'application_attempt_id': application_attempt,
                                    'reused_application_for_grading': reused_application}}
                except RunError as exc:
                    failure = exc
                    if exc.observed:
                        if stage == 'grader': judged = exc.observed
                        else: observed = exc.observed
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    failure = RunError('harness_error', type(exc).__name__)
                app_cost, judge_cost = None, None
                try:
                    app_cost = 0.0 if reused_application or stage == 'setup' else declared_cost(observed)
                    judge_cost = (0.0 if prepared['grader']['kind'] != 'command' or stage != 'grader'
                                  else declared_cost(judged))
                    # Deterministic graders cost no model calls; model-graded missing cost remains unknown.
                    cost = app_cost + judge_cost if app_cost is not None and judge_cost is not None else None
                except RunError as exc:
                    failure = exc; cost = None
                with guard:
                    reserved[0] -= reservation
                    if cost is None: unknown[0] += 1
                    known_cost = sum(v for v in (app_cost, judge_cost) if v is not None)
                    spent[0] += known_cost
                    status = failure.kind if failure else 'ok'
                    finish = {'event': 'finished', 'attempt_id': attempt_id, 'prompt_id': case_id,
                              'rep': rep, 'status': status, 'cost_usd': cost, 'time': time.time(),
                              'known_cost_usd': known_cost,
                              'app_cost_usd': app_cost, 'judge_cost_usd': judge_cost, 'stage': stage,
                              'usage': None if reused_application else observed.get('usage'), 'judge_usage': judged.get('usage'),
                              'model': observed.get('model'), 'judge_model': judged.get('model'),
                              'latency_s': time.monotonic() - started}
                    if not failure:
                        costs = case_costs.get((case_id, rep), []) + [cost]
                        row['cost_usd'] = sum(costs) if all(v is not None for v in costs) else None
                        row['attempt_cost_usd'] = cost
                        append_json(directory, 'results.jsonl', row); rows.append(row)
                    else:
                        error = {**finish, 'retryable': failure.retryable, 'error': str(failure)}
                        append_json(directory, 'errors.jsonl', error); errors.append(error)
                    append_json(directory, 'attempts.jsonl', finish)
                    case_costs.setdefault((case_id, rep), []).append(cost)
                    manifest['results_sha256'] = sha(read_bytes(results_path))
                    manifest['attempts_sha256'] = sha(read_bytes(events_path))
                    write_json(directory, 'manifest.json', manifest)
                    if ceiling is not None and (cost is None or cost > reservation or spent[0] > ceiling):
                        stopping.set()
                if not failure or not failure.retryable or retry == limits['retries']:
                    return
                time.sleep(min(.1 * 2 ** retry + random.random() * .05, max(0, case_deadline - time.monotonic())))

        pending = [(key, rep) for key in prepared['selected'] for rep in range(manifest['reps']) if (key, rep) not in set(keys)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=limits['concurrency']) as pool:
            list(pool.map(lambda pair: task(*pair), pending))
        complete = len(rows) == len(prepared['selected']) * manifest['reps'] and not stopping.is_set()
        manifest.update(status='complete' if complete else 'incomplete', results_sha256=sha(read_bytes(results_path)),
                        completed_cases=len(rows), attempts=attempted[0], known_cost_usd=spent[0], unknown_cost_attempts=unknown[0])
        if variant == 'baseline' and complete:
            frozen = {key: next(r['output'] for r in rows if r['prompt_id'] == key and r['rep'] == 0) for key in prepared['selected']}
            frozen_path = in_root(directory, 'frozen-outputs.json')
            if frozen_path.exists() and read_json(frozen_path) != frozen:
                raise ValueError('frozen baseline outputs differ; do not replace the reference')
            write_json(directory, 'frozen-outputs.json', frozen)
            manifest['frozen_outputs_sha256'] = sha(read_bytes(frozen_path))
        manifest['attempts_sha256'] = sha(read_bytes(events_path))
        write_json(directory, 'manifest.json', manifest)
        return {key: manifest[key] for key in ('status', 'completed_cases', 'attempts', 'known_cost_usd', 'unknown_cost_attempts')}
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--flow', type=Path, required=True)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--split', choices=['train', 'val', 'test'], required=True)
    parser.add_argument('--reps', type=int, default=1)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    try:
        prepared = prepare(args.card, args.variant, args.split, args.reps, args.selection)
        if not args.execute:
            print(json.dumps({'mode': 'plan', 'runs': len(prepared['selected']) * args.reps,
                              'manifest': prepared['manifest']}, ensure_ascii=False, indent=2))
            return 0
        result = run(prepared, args.flow, args.resume, args.retry_errors)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'complete' else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
