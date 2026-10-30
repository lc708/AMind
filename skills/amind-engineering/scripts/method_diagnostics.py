#!/usr/bin/env python3
"""Audit adapter-normalized architecture, review and oversight evidence; no requests or writes."""
import argparse
import json
import math
import re
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def names(values, label, allow_empty=False):
    require(isinstance(values, list), label + ' must be a list')
    require(all(isinstance(x, str) and x.strip() for x in values), label + ' needs nonempty strings')
    require(len(set(values)) == len(values), label + ' contains duplicates')
    require(allow_empty or bool(values), label + ' cannot be empty')
    return values


def number(value, label, integer=False):
    require(type(value) in ((int,) if integer else (int, float)), label + ' must be numeric')
    require(math.isfinite(value) and value >= 0, label + ' must be finite and nonnegative')
    return value


def evidence(row):
    return isinstance(row.get('evidence'), str) and bool(row['evidence'].strip())


def indexed(rows, population, label, key='case_id'):
    require(isinstance(rows, list), label + ' must be a list')
    result = {}
    for row in rows:
        require(isinstance(row, dict), label + ' needs objects')
        identity = row.get(key)
        require(isinstance(identity, str) and identity in population, label + ' has an unknown identity')
        require(identity not in result, label + ' contains a duplicate identity')
        result[identity] = row
    return result


def architecture(capture):
    """Structural suggestions and descriptive, complete-pair migration evidence."""
    require(isinstance(capture, dict), 'capture object required')
    components = capture.get('components', [])
    require(isinstance(components, list), 'components must be a list')
    ids = names([c.get('id') for c in components if isinstance(c, dict)], 'component ids', True)
    require(len(ids) == len(components), 'components need objects')
    suggestions = []
    facts = ('independent_verification', 'separate_permissions', 'parallel_work',
             'context_pressure_observed', 'talks_to_user', 'coupling_observed', 'deterministic')
    for component in components:
        role = component.get('role')
        require(role in {'router', 'planner', 'domain', 'verifier', 'data', 'other'}, 'unknown component role')
        for field in facts:
            if field in component:
                require(type(component[field]) is bool, field + ' must be boolean')
        peers = names(component.get('shares_context_with', []), 'shares_context_with', True)
        require(set(peers) <= set(ids) - {component['id']}, 'unknown/self shared-context component')
        action, reason = 'investigate', 'record structural observations before choosing a migration'
        if evidence(component) and all(field in component for field in facts):
            retained = any(component[field] for field in facts[:4])
            if retained:
                action = 'keep' if component['talks_to_user'] else 'as-tool'
                reason = 'retain the observed isolation, verification, parallel or context benefit'
            elif component['deterministic']:
                action, reason = 'as-tool', 'a deterministic operation does not need a separate model loop'
            elif peers and component['coupling_observed']:
                action, reason = 'merge', 'shared context and observed coupling justify a paired merge experiment'
            elif role in {'router', 'planner', 'domain'} and component['coupling_observed']:
                action, reason = 'fold', 'test procedure as a skill and live operations as guarded tools'
        suggestions.append({'id': component['id'], 'suggested_action': action,
                            'reason': reason, 'evidence': component.get('evidence')})
    result = {'suggestions': suggestions, 'comparison': {'status': 'not_measured'},
              'scope': 'suggestions are hypotheses, not automatic rewrites or proof of model quality'}
    comparison = capture.get('comparison')
    if comparison is None:
        return result
    require(isinstance(comparison, dict), 'comparison must be an object')
    for field in ('dataset_id', 'grader_id', 'baseline_id', 'candidate_id'):
        require(isinstance(comparison.get(field), str) and comparison[field].strip(), field + ' required')
    require(comparison['baseline_id'] != comparison['candidate_id'], 'different treatment identities required')
    population = names(comparison.get('required_case_ids'), 'required_case_ids')
    required_paths = names(comparison.get('required_path_ids'), 'required_path_ids')
    arms = {}
    missing_paths = {}
    for arm in ('baseline', 'candidate'):
        block = comparison.get(arm)
        require(isinstance(block, dict), arm + ' must be an object')
        require(evidence(block), arm + ' requires a captured evidence reference')
        covered = names(block.get('covered_path_ids'), arm + ' covered paths', True)
        require(set(covered) <= set(required_paths), 'undeclared production path')
        missing_paths[arm] = sorted(set(required_paths) - set(covered))
        arms[arm] = indexed(block.get('cases'), population, arm)
        for row in arms[arm].values():
            require(type(row.get('success')) is bool, 'case success must be boolean')
            number(row.get('constraint_violations'), 'constraint_violations', True)
            for field in ('cost_usd', 'latency_ms'):
                if row.get(field) is not None:
                    number(row[field], field)
    pairs = [key for key in population if all(key in arms[arm] for arm in arms)]
    missing = {arm: [key for key in population if key not in arms[arm]] for arm in arms}
    improved = [key for key in pairs if not arms['baseline'][key]['success'] and arms['candidate'][key]['success']]
    regressed = [key for key in pairs if arms['baseline'][key]['success'] and not arms['candidate'][key]['success']]
    violations = [key for key in pairs if arms['candidate'][key]['constraint_violations'] > arms['baseline'][key]['constraint_violations']]
    complete = len(pairs) == len(population) and not any(missing_paths.values())
    deltas = {}
    for field in ('cost_usd', 'latency_ms'):
        known = complete and all(arms[arm][key].get(field) is not None for arm in arms for key in population)
        deltas[field] = (sum(arms['candidate'][key][field] - arms['baseline'][key][field]
                             for key in population) / len(population)) if known else None
    result['comparison'] = {
        'status': 'regressed' if regressed or violations else ('observed' if complete else 'inconclusive'),
        'required_cases': len(population), 'paired_cases': len(pairs), 'coverage': len(pairs) / len(population),
        'missing_cases': missing, 'missing_paths': missing_paths, 'improved_case_ids': improved,
        'regressed_case_ids': regressed, 'increased_violation_case_ids': violations,
        'mean_candidate_minus_baseline': deltas,
        'scope': 'descriptive case pairs; no significance, independent sampling or live execution is certified'}
    return result


def review(capture):
    """Track explicit finding resolution across bounded patch-specific review rounds."""
    require(isinstance(capture, dict), 'capture object required')
    maximum = number(capture.get('max_rounds'), 'max_rounds', True)
    require(maximum > 0, 'max_rounds must be positive')
    checks = names(capture.get('required_check_ids'), 'required_check_ids')
    rounds = capture.get('rounds', [])
    require(isinstance(rounds, list) and len(rounds) <= maximum, 'review round budget exceeded')
    ledger, history = {}, []
    for round_index, row in enumerate(rounds, 1):
        require(isinstance(row, dict), 'round must be an object')
        require(re.fullmatch('[0-9a-f]{64}', row.get('patch_sha256', '')) is not None, 'patch_sha256 required')
        paths = names(row.get('changed_paths'), 'changed_paths', True)
        inspected = names(row.get('checked_paths'), 'checked_paths', True)
        statuses = indexed(row.get('checks'), checks, 'checks', 'id')
        for status in statuses.values():
            require(status.get('status') in {'passed', 'failed', 'unknown'}, 'invalid check status')
            require(status.get('patch_sha256') == row['patch_sha256'], 'check belongs to another patch')
        findings = row.get('findings', [])
        require(isinstance(findings, list), 'findings must be a list')
        seen, new = set(), []
        for finding in findings:
            require(isinstance(finding, dict), 'finding must be an object')
            key = finding.get('key')
            require(isinstance(key, str) and key.strip() and key not in seen, 'unique stable finding keys required per round')
            seen.add(key)
            for field in ('path', 'contract'):
                require(isinstance(finding.get(field), str) and finding[field].strip(), 'finding ' + field + ' required')
            require(type(finding.get('blocking')) is bool, 'finding blocking must be boolean')
            require(finding.get('status') in {'open', 'resolved', 'dismissed'}, 'invalid finding status')
            require(evidence(finding), 'finding evidence required, including resolution/dismissal evidence')
            if key in ledger:
                require(all(ledger[key][field] == finding[field] for field in ('path', 'contract')), 'finding key reused for another contract')
            elif finding['status'] == 'open':
                new.append(key)
            ledger[key] = dict(finding)
        missing = [key for key in checks if key not in statuses or statuses[key]['status'] != 'passed' or not evidence(statuses[key])]
        uncovered = sorted(set(paths) - set(inspected))
        history.append({'round': round_index, 'patch_sha256': row['patch_sha256'],
                        'new_finding_keys': new, 'missing_or_unpassed_checks': missing, 'uncovered_paths': uncovered})
    open_blocking = sorted(key for key, row in ledger.items() if row['status'] == 'open' and row['blocking'])
    if not rounds:
        status = 'not_measured'
    elif not open_blocking and not history[-1]['new_finding_keys'] and not history[-1]['missing_or_unpassed_checks'] and not history[-1]['uncovered_paths']:
        status = 'converged'
    elif len(rounds) == maximum:
        status = 'round_limit'
    else:
        status = 'needs_follow_up'
    return {'status': status, 'rounds_used': len(rounds), 'max_rounds': maximum,
            'open_blocking_finding_keys': open_blocking, 'findings': ledger, 'rounds': history,
            'scope': 'patch-specific review evidence; convergence is not merge approval or proof of bug absence'}


def oversight(capture):
    """Describe preference following; approval cannot establish judgment independence."""
    require(isinstance(capture, dict), 'capture object required')
    population = names(capture.get('required_case_ids'), 'required_case_ids')
    observations = indexed(capture.get('observations', []), population, 'observations')
    measured, randomized, balanced, prior = [], [], [], []
    reviewers = set()
    for key, row in observations.items():
        for field in ('agent_preference', 'final_choice', 'reviewer_id'):
            require(isinstance(row.get(field), str) and row[field].strip(), field + ' required')
        require(row.get('preference_assignment') in {'randomized', 'natural', 'unknown'}, 'preference_assignment required')
        for field in ('balanced_alternatives', 'prior_recorded_before_advice'):
            require(type(row.get(field)) is bool, field + ' must be boolean')
        if row.get('prior_choice') is not None:
            require(isinstance(row['prior_choice'], str) and row['prior_choice'].strip(), 'prior_choice must be nonempty')
        require(not row['prior_recorded_before_advice'] or row.get('prior_choice') is not None, 'a pre-advice record needs its choice')
        if not evidence(row):
            continue
        measured.append(key)
        reviewers.add(row['reviewer_id'])
        if row['preference_assignment'] == 'randomized':
            randomized.append(key)
        if row['balanced_alternatives']:
            balanced.append(key)
        if row['prior_recorded_before_advice']:
            prior.append(key)
    followed = [key for key in measured if observations[key]['agent_preference'] == observations[key]['final_choice']]
    prior_disagreement = [key for key in prior if observations[key]['prior_choice'] != observations[key]['agent_preference']]
    switched = [key for key in prior_disagreement if key in followed]
    return {'status': 'observed' if len(measured) == len(population) else ('inconclusive' if measured else 'not_measured'),
            'required_decisions': len(population), 'measured_decisions': len(measured),
            'missing_evidence_ids': [key for key in population if key not in measured],
            'distinct_reviewers': len(reviewers), 'followed_agent_count': len(followed),
            'followed_agent_rate': len(followed) / len(measured) if measured else None,
            'prior_disagreement_count': len(prior_disagreement), 'switched_toward_agent_count': len(switched),
            'randomized_assignment_count': len(randomized), 'balanced_alternative_count': len(balanced),
            'judgment_independence': 'not_established',
            'scope': 'descriptive decision counts, not an error rate, causal estimate or independent-review certification'}


def handoff(capture):
    """Check captured authorization provenance, state binding and monitor coverage."""
    require(isinstance(capture, dict), 'capture object required')
    population = names(capture.get('required_handoff_ids'), 'required_handoff_ids')
    observations = indexed(capture.get('handoffs', []), population, 'handoffs', 'id')
    findings, unmeasured = [], []
    approval, dispatch = capture.get('approval'), capture.get('dispatch')
    for label, row in (('approval', approval), ('dispatch', dispatch)):
        require(isinstance(row, dict), label + ' object required')
        require(re.fullmatch('[0-9a-f]{64}', row.get('action_sha256', '')) is not None, label + ' action_sha256 required')
        require(isinstance(row.get('resource_version'), str) and row['resource_version'].strip(), label + ' resource_version required')
    if approval.get('authority_origin') != 'trusted_control_plane':
        findings.append('approval_not_from_trusted_control_plane')
    if approval['action_sha256'] != dispatch['action_sha256']:
        findings.append('action_changed_after_approval')
    if approval['resource_version'] != dispatch['resource_version']:
        findings.append('resource_changed_after_approval')
    if not evidence(approval) or not evidence(dispatch):
        unmeasured.append('approval_dispatch_evidence')
    for key in population:
        row = observations.get(key)
        if row is None:
            unmeasured.append(key)
            continue
        require(row.get('kind') in {'compaction', 'agent_handoff', 'shared_file', 'tool_result'}, 'invalid handoff kind')
        require(type(row.get('monitor_applied')) is bool and type(row.get('claims_authorization')) is bool, 'handoff facts must be boolean')
        require(row.get('authority_origin') in {'trusted_control_plane', 'untrusted_content', 'none', 'unknown'}, 'invalid authority_origin')
        if row['claims_authorization'] and row['authority_origin'] != 'trusted_control_plane':
            findings.append(key + ':untrusted_authorization_claim')
        if not row['monitor_applied'] or not evidence(row):
            unmeasured.append(key)
        if row['kind'] == 'shared_file':
            for field in ('expected_sha256', 'observed_sha256'):
                require(re.fullmatch('[0-9a-f]{64}', row.get(field, '')) is not None, 'shared_file ' + field + ' required')
            if row['expected_sha256'] != row['observed_sha256']:
                findings.append(key + ':shared_file_changed')
    return {'status': 'failed' if findings else ('inconclusive' if unmeasured else 'observed'),
            'findings': findings, 'unmeasured': unmeasured, 'required_handoffs': len(population),
            'scope': 'trusted application instrumentation must supply these facts; no signatures, policy or remote outcomes are verified here'}


def claude_api(capture):
    """Check selected Messages removals for one explicit API version, never mutate a request."""
    require(isinstance(capture, dict), 'capture object required')
    if capture.get('provider') != 'anthropic' or capture.get('api_version') != '2026-10-21':
        return {'status': 'out_of_scope', 'findings': [], 'scope': 'only Anthropic API version 2026-10-21 is checked'}
    request = capture.get('request')
    require(isinstance(request, dict), 'request object required')
    findings = [field + ':removed_sampling_parameter' for field in ('temperature', 'top_p', 'top_k') if field in request]
    messages = request.get('messages', [])
    require(isinstance(messages, list), 'messages must be a list')

    def user_texts(value, path):
        if isinstance(value, dict):
            if value.get('type') == 'text' and value.get('citations'):
                findings.append(path + ':nonempty_user_text_citations')
            for field, nested in value.items():
                if field == 'content':
                    user_texts(nested, path + '.content')
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                user_texts(nested, path + '[' + str(index) + ']')

    for index, message in enumerate(messages):
        require(isinstance(message, dict), 'message must be an object')
        content = message.get('content', [])
        if message.get('role') == 'assistant' and isinstance(content, list):
            for block_index, block in enumerate(content):
                if isinstance(block, dict) and block.get('type') == 'document':
                    findings.append('messages[' + str(index) + '].content[' + str(block_index) + ']:direct_assistant_document')
        if message.get('role') == 'user':
            user_texts(content, 'messages[' + str(index) + '].content')
    return {'status': 'needs_migration' if findings else 'checked', 'findings': findings,
            'scope': 'selected request removals only; not SDK, authentication, full schema or live API compatibility validation'}


MODES = {'architecture': architecture, 'review': review, 'oversight': oversight,
         'handoff': handoff, 'claude-api': claude_api}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    try:
        capture = json.loads(args.capture.read_text())
        require(isinstance(capture, dict), 'capture object required')
        print(json.dumps(MODES[args.mode](capture), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
