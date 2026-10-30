#!/usr/bin/env python3
"""Offline OpenAI usage normalization and explicit cache-prefix scenarios.

Checked against official Responses caching and Decisions docs on 2026-10-30.
No tokenization, cache-hit prediction, network request or live price lookup.
"""
import argparse
import copy
import json
import sys
from pathlib import Path
from kernel_common import read_json
from price_usage import billing_identity, nonnegative

SOURCES = {
    'responses': 'https://developers.openai.com/api/docs/guides/prompt-caching',
    'decisions': 'https://developers.openai.com/api/reference/resources/decisions/methods/create',
}
POLICIES = {'responses': 'openai_30m_12h_v1', 'decisions': 'openai_decisions_30m_v1'}
TTLS = {'30m': 30, '12h': 720}


def normalize_response(response, identity, *, all_billable_usage_included=False):
    """Bind actual native counters to an exact endpoint/rate-card identity.

    Missing or unsupported counters raise ValueError; callers must retain an
    unknown-cost event instead of treating a failed normalization as zero.
    """
    identity = copy.deepcopy(billing_identity(identity))
    endpoint = identity['interface']
    if identity['provider'] != 'openai' or endpoint not in SOURCES:
        raise ValueError('normalizer supports openai responses/decisions only')
    if identity.get('cache_policy', POLICIES[endpoint]) != POLICIES[endpoint]:
        raise ValueError('cache_policy conflicts with endpoint normalization')
    identity['cache_policy'] = POLICIES[endpoint]
    if not isinstance(response, dict) or response.get('model') != identity['model']:
        raise ValueError('served model must match billing_identity exactly')
    if 'service_tier' in response and response['service_tier'] != identity['service_tier']:
        raise ValueError('served service_tier differs from billing_identity')
    usage = response.get('usage')
    keys = {'input_tokens', 'input_tokens_details', 'output_tokens', 'output_tokens_details', 'total_tokens'}
    if not isinstance(usage, dict) or set(usage) - keys:
        raise ValueError('missing or unadapted native usage; cost remains unknown')
    for key in ('input_tokens', 'output_tokens'):
        if key not in usage: raise ValueError('missing native ' + key)
        nonnegative(usage[key], key, True)
    if 'total_tokens' in usage:
        nonnegative(usage['total_tokens'], 'total_tokens', True)
        if usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
            raise ValueError('native total_tokens contradicts input/output totals')
    details = usage.get('input_tokens_details')
    allowed = {'cached_tokens', 'cache_write_tokens', 'cache_write_tokens_details'}
    if endpoint == 'decisions': allowed.remove('cache_write_tokens_details')
    if not isinstance(details, dict) or set(details) - allowed:
        raise ValueError('missing or unadapted input token details')
    for key in ('cached_tokens', 'cache_write_tokens'):
        if key not in details: raise ValueError('missing native ' + key)
        nonnegative(details[key], key, True)
    if endpoint == 'responses':
        split = details.get('cache_write_tokens_details')
        if not isinstance(split, dict) or set(split) != {'ttl_30m_tokens', 'ttl_12h_tokens'}:
            raise ValueError('Responses requires both native cache write lifetime counters')
        for key, value in split.items(): nonnegative(value, key, True)
        writes = {'30m': split['ttl_30m_tokens'], '12h': split['ttl_12h_tokens']}
    else:
        # Decisions currently supports only request-level 30m; do not infer
        # its schema from the Responses API's 12h/breakpoint overrides.
        writes = {'30m': details['cache_write_tokens'], '12h': 0}
    if sum(writes.values()) != details['cache_write_tokens']:
        raise ValueError('native cache write lifetime counters contradict aggregate')
    if details['cached_tokens'] + sum(writes.values()) > usage['input_tokens']:
        raise ValueError('native cached/write subsets exceed input total')
    output_details = usage.get('output_tokens_details', {})
    if not isinstance(output_details, dict) or set(output_details) - {'reasoning_tokens'}:
        raise ValueError('unadapted output details')
    reasoning = nonnegative(output_details.get('reasoning_tokens', 0), 'reasoning tokens', True)
    if reasoning > usage['output_tokens']: raise ValueError('reasoning exceeds output total')
    normalized = {'input_tokens': usage['input_tokens'], 'cached_input_tokens': details['cached_tokens'],
                  'cache_write_input_tokens_by_ttl': writes}
    if endpoint == 'responses':
        normalized.update(output_tokens=usage['output_tokens'], reasoning_tokens=reasoning)
    if type(all_billable_usage_included) is not bool:
        raise ValueError('all_billable_usage_included must be an explicit boolean')
    return {'billing_identity': identity, 'usage_adapter': 'cache_text_v1' if endpoint == 'responses' else 'cache_input_v1',
            'usage': normalized, 'native_usage': copy.deepcopy(usage),
            'normalization': {'schema': 'openai-cache-usage-v1', 'source': SOURCES[endpoint], 'checked_at': '2026-10-30'},
            'all_billable_usage_included': all_billable_usage_included}


def plan_cache_prefixes(input_tokens, breakpoints, available_prefixes):
    """Scenario for caller-supplied eligible boundaries and valid matching cache.

    available_prefixes are explicitly valid, same-prefix, eligible cache entries,
    not guessed from prompt text. This result must never replace native usage.
    """
    nonnegative(input_tokens, 'input_tokens', True)
    if not isinstance(breakpoints, list) or len(breakpoints) > 4:
        raise ValueError('provide at most four selected cache breakpoints')
    if not isinstance(available_prefixes, list): raise ValueError('available_prefixes must be a list')
    for kind, entries in [('breakpoint', breakpoints), ('available prefix', available_prefixes)]:
        for item in entries:
            if not isinstance(item, dict) or set(item) != {'end_tokens', 'ttl'} or item.get('ttl') not in TTLS:
                raise ValueError(kind + ' requires end_tokens and 30m/12h ttl')
            end = nonnegative(item['end_tokens'], kind + ' end_tokens', True)
            if end == 0 or end > input_tokens: raise ValueError(kind + ' endpoint outside input')
    ends = [p['end_tokens'] for p in breakpoints]
    if len(set(ends)) != len(ends): raise ValueError('duplicate selected breakpoint endpoint')
    result = {'input_tokens': input_tokens, 'ordinary_input_tokens': input_tokens,
              'cached_input_tokens': 0, 'cache_write_input_tokens_by_ttl': {'30m': 0, '12h': 0},
              'basis': 'offline scenario; explicit eligible matching prefixes, not measured provider usage'}
    if not breakpoints: return result
    stop = max(ends)
    boundaries = sorted({0, stop, *ends, *(min(stop, p['end_tokens']) for p in available_prefixes)})
    for left, right in zip(boundaries, boundaries[1:]):
        length = right - left
        required = max(TTLS[p['ttl']] for p in breakpoints if p['end_tokens'] >= right)
        available = max((TTLS[p['ttl']] for p in available_prefixes if p['end_tokens'] >= right), default=0)
        if available >= required: result['cached_input_tokens'] += length
        else: result['cache_write_input_tokens_by_ttl']['12h' if required == 720 else '30m'] += length
    result['ordinary_input_tokens'] = input_tokens - stop
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['normalize', 'plan-cache'])
    parser.add_argument('input', type=Path, help='JSON containing response/billing_identity, or scenario arguments')
    args = parser.parse_args()
    try:
        data = read_json(args.input)
        if args.mode == 'normalize':
            if set(data) - {'response', 'billing_identity', 'all_billable_usage_included'}:
                raise ValueError('unknown normalization envelope fields')
            result = normalize_response(data['response'], data['billing_identity'],
                all_billable_usage_included=data.get('all_billable_usage_included', False))
        else: result = plan_cache_prefixes(**data)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'unknown', 'cost_usd': None, 'error': str(error)})); return 2


if __name__ == '__main__': sys.exit(main())
