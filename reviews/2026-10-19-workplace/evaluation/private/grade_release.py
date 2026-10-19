#!/usr/bin/env python3
import copy
import json
from fixtures import release, IDENTITY
from grader_common import evaluate


def probes():
    rows = []
    def add(key, domain, state, expected): rows.append((key, domain, state, expected))
    s = release()
    add('release-clean', 'population', s, {'planned_observations': 2, 'scored_observations': 2, 'metrics.quality.mean': .9, 'decision': 'ready', 'cost.total_usd': .4})
    m, r, e, rates = release(); m['repetitions'] = 2
    for row in copy.deepcopy(r):
        row['rep'] = 1; row['result_identity']['rep'] = 1; r.append(row)
    r.pop()
    add('planned-repeat-gap', 'population', (m, r, e, rates), {'planned_observations': 4, 'scored_observations': 3, 'missing': [{'case_id': 'account-lock', 'rep': 1}], 'decision': 'hold'})
    m, r, e, rates = release(); m['case_ids'].append('refund-escalation')
    e += [{'event': 'started', 'attempt_id': 'failed-c', 'case_id': 'refund-escalation', 'rep': 0}, {'event': 'finished', 'attempt_id': 'failed-c', 'case_id': 'refund-escalation', 'rep': 0, 'status': 'timeout', 'cost_usd': .05}]
    add('failed-case-retained', 'population', (m, r, e, rates), {'planned_observations': 3, 'scored_observations': 2, 'attempts.failed': 1, 'cost.total_usd': .45, 'decision': 'hold'})
    m, r, e, rates = release(); r[-1]['billing_identity'] = {**r[-1]['billing_identity'], 'service_tier': 'flex'}
    add('served-tier', 'identity', (m, r, e, rates), {'integrity.status': 'invalid', 'scored_observations': 1, 'decision': 'hold'})
    m, r, e, rates = release(); r[-1]['result_identity']['treatment_hash'] = 'another-prompt'
    add('foreign-result', 'identity', (m, r, e, rates), {'integrity.status': 'invalid', 'scored_observations': 1, 'decision': 'hold'})
    m, r, e, rates = release(); r.append(copy.deepcopy(r[0]))
    add('duplicate-result', 'identity', (m, r, e, rates), {'integrity.status': 'invalid', 'scored_observations': 2, 'decision': 'hold'})
    m, r, e, rates = release(); e.append({'event': 'started', 'attempt_id': 'interrupted-judge', 'case_id': 'refund', 'rep': 0})
    add('unknown-interrupted', 'recovery_cost', (m, r, e, rates), {'cost.known_usd': .4, 'cost.total_usd': None, 'cost.unknown_attempts': 1, 'attempts.started': 3, 'attempts.interrupted': 1, 'decision': 'hold'})
    m, r, e, rates = release(); e += [{'event': 'started', 'attempt_id': 'retry-failed', 'case_id': 'refund', 'rep': 0}, {'event': 'finished', 'attempt_id': 'retry-failed', 'case_id': 'refund', 'rep': 0, 'status': 'rate_limit', 'cost_usd': .05}]
    add('retry-spend', 'recovery_cost', (m, r, e, rates), {'cost.total_usd': .45, 'attempts.failed': 1, 'attempts.finished': 3})
    m, r, e, rates = release()
    for x in e:
        if x['event'] == 'finished': x['cost_usd'] = 0
    add('audited-zero', 'recovery_cost', (m, r, e, rates), {'cost.total_usd': 0.0, 'cost.unknown_attempts': 0, 'decision': 'ready'})
    m, r, e, rates = release(); x = e[-1]; x.pop('cost_usd'); x.update(billing_identity=IDENTITY, all_billable_usage_included=True, usage={'input_tokens': 100, 'cached_input_tokens': 0, 'output_tokens': 3, 'audio_tokens': 40})
    add('native-extra-unknown', 'rate_scope', (m, r, e, rates), {'cost.total_usd': None, 'cost.unknown_attempts': 1, 'decision': 'hold'})
    m, r, e, rates = release(); a, b = e[1], e[3]
    for x in (a, b): x.pop('cost_usd'); x['all_billable_usage_included'] = True
    a.update(billing_identity=IDENTITY, usage={'input_tokens': 1000000, 'cached_input_tokens': 200000, 'output_tokens': 100000, 'reasoning_tokens': 30000})
    b.update(billing_identity={**IDENTITY, 'interface': 'decisions'}, usage={'input_tokens': 1000000})
    add('endpoint-and-subsets', 'rate_scope', (m, r, e, rates), {'cost.total_usd': 12.2, 'cost.unknown_attempts': 0})
    m, r, e, rates = release(); x = e[-1]; x.pop('cost_usd'); x.update(billing_identity={**IDENTITY, 'region': 'eu-unpriced'}, all_billable_usage_included=True, usage={'input_tokens': 100, 'cached_input_tokens': 0, 'output_tokens': 3})
    add('unpriced-region', 'rate_scope', (m, r, e, rates), {'cost.total_usd': None, 'cost.unknown_attempts': 1, 'cost.known_usd': .2})
    m, r, e, rates = release(); e.append(copy.deepcopy(e[1]))
    add('duplicate-journal', 'workflow_integrity', (m, r, e, rates), {'integrity.status': 'invalid', 'attempts.finished': 2, 'cost.total_usd': .4, 'decision': 'hold'})
    m, r, e, rates = release(); stage = r[-1]['coverage']['stages'][0]; stage.update(total=2, counts={'succeeded': 2})
    add('worker-population', 'workflow_integrity', (m, r, e, rates), {'coverage.status': 'incomplete', 'decision': 'hold'})
    return rows


if __name__ == '__main__':
    print(json.dumps(evaluate('V-RELEASE', 'releaseboard', probes(), ['population', 'identity', 'recovery_cost', 'rate_scope', 'workflow_integrity'],
                              {'no_foreign_evidence': ['foreign-result', 'served-tier'], 'unknown_is_not_free': ['unknown-interrupted'], 'full_population_required': ['failed-case-retained']}), allow_nan=False))
