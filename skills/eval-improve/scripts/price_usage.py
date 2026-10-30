#!/usr/bin/env python3
"""Price explicit normalized usage in its exact billing scope; missing is never free."""
import argparse
import json
import sys
from pathlib import Path
from kernel_common import finite, read_json, read_jsonl, sha

IDENTITY_FIELDS = ('provider', 'interface', 'model', 'service_tier', 'region')
ADAPTERS = {'text_tokens_v1', 'input_only_v1', 'units_v1', 'cache_text_v1', 'cache_input_v1'}
OPTIONAL_SCOPE_FIELDS = ('context_band', 'cache_policy')


def nonnegative(value, name, integer=False):
    if not finite(value) or value < 0 or (integer and type(value) is not int):
        raise ValueError('invalid ' + name)
    return value


def billing_identity(value):
    if not isinstance(value, dict) or set(value) - set(IDENTITY_FIELDS) - set(OPTIONAL_SCOPE_FIELDS):
        raise ValueError('billing_identity requires exact provider/interface/model/service_tier/region and optional context_band/cache_policy')
    if any(not isinstance(value.get(k), str) or not value[k] for k in IDENTITY_FIELDS):
        raise ValueError('billing_identity requires exact provider/interface/model/service_tier/region')
    for key in OPTIONAL_SCOPE_FIELDS:
        if key in value and (not isinstance(value[key], str) or not value[key]):
            raise ValueError(key + ' must be a nonempty exact rate scope')
    return value


def check_flat_scope(record, identity):
    for key in (*IDENTITY_FIELDS, *OPTIONAL_SCOPE_FIELDS):
        if key in record and record[key] != identity.get(key):
            raise ValueError(key + ' differs from billing_identity')


def unknown(reason):
    return {'status': 'unknown', 'cost_usd': None, 'reason': reason}


def select_rate(event, card):
    identity = event.get('billing_identity')
    if identity is None:
        # Historical three-rate text cards cannot price a newly declared endpoint,
        # tier, region or context band by matching only its model name.
        if any(k in event for k in (*IDENTITY_FIELDS, *OPTIONAL_SCOPE_FIELDS) if k != 'model') or 'usage_adapter' in event:
            return None, None, 'explicit billing scope requires billing_identity and rates[]'
        return card.get('models', {}).get(event.get('model')), 'text_tokens_v1', None
    billing_identity(identity)
    check_flat_scope(event, identity)
    rates = card.get('rates', [])
    if not isinstance(rates, list): raise ValueError('rates must be a list')
    seen = set(); matches = []
    for entry in rates:
        scope = billing_identity(entry.get('billing_identity'))
        check_flat_scope(entry, scope)
        key = sha(scope)
        if key in seen: raise ValueError('duplicate billing_identity rate')
        seen.add(key)
        if scope == identity: matches.append(entry)
    if not matches: return None, None, 'no exact billing_identity rate; endpoints/tiers/regions/context bands are not interchangeable'
    rate = matches[0]; adapter = rate.get('usage_adapter')
    if adapter not in ADAPTERS or event.get('usage_adapter') != adapter:
        return None, None, 'unsupported or mismatched normalized usage_adapter'
    return rate, adapter, None


def unit_parts(usage, rate):
    units = usage.get('units', {})
    if not isinstance(units, dict): raise ValueError('normalized units must be an object')
    rates = rate.get('unit_rates', {})
    if not isinstance(rates, dict): raise ValueError('unit_rates must be an object')
    parts = {}
    for key, count in units.items():
        nonnegative(count, 'unit ' + key)
        if key not in rates: return None
        spec = rates[key]
        if not isinstance(spec, dict) or set(spec) != {'usd', 'per'}:
            raise ValueError('unit rate requires usd and per')
        nonnegative(spec['usd'], 'unit rate'); nonnegative(spec['per'], 'unit divisor')
        if not spec['per']: raise ValueError('unit divisor must be positive')
        parts['unit:' + key] = count * spec['usd'] / spec['per']
    return parts


def cached_parts(usage, rate, adapter, identity):
    """Price disjoint reads/writes; write rates are total rates, never surcharges."""
    if not identity or not identity.get('cache_policy'):
        return None, 'cache adapters require an exact cache_policy billing scope'
    allowed = {'input_tokens', 'cached_input_tokens', 'cache_write_input_tokens_by_ttl', 'units'}
    if adapter == 'cache_text_v1': allowed |= {'output_tokens', 'reasoning_tokens'}
    if set(usage) - allowed: return None, 'unadapted cache usage fields'
    required = {'input_tokens', 'cached_input_tokens', 'cache_write_input_tokens_by_ttl'}
    if adapter == 'cache_text_v1': required.add('output_tokens')
    if not required <= set(usage): return None, 'missing explicit cache/input/output counters'
    incoming = nonnegative(usage['input_tokens'], 'input tokens', True)
    reads = nonnegative(usage['cached_input_tokens'], 'cached input tokens', True)
    writes = usage['cache_write_input_tokens_by_ttl']
    if not isinstance(writes, dict) or set(writes) != {'30m', '12h'}:
        raise ValueError('cache write counters require disjoint 30m and 12h buckets')
    for ttl, count in writes.items(): nonnegative(count, ttl + ' write tokens', True)
    if reads + sum(writes.values()) > incoming:
        raise ValueError('cache reads/writes exceed input total')
    for key in ('input_per_million', 'cached_input_per_million'):
        if key not in rate: return None, 'missing cache/input rate'
        nonnegative(rate[key], key)
    write_rates = rate.get('cache_write_input_per_million_by_ttl', {})
    if not isinstance(write_rates, dict) or set(write_rates) - {'30m', '12h'}:
        raise ValueError('cache write rates support only 30m and 12h')
    parts = {'uncached_input': (incoming - reads - sum(writes.values())) * rate['input_per_million'] / 1e6,
             'cached_input': reads * rate['cached_input_per_million'] / 1e6}
    for ttl, count in writes.items():
        if ttl in write_rates: nonnegative(write_rates[ttl], ttl + ' write rate')
        elif count: return None, 'cache write rate missing for ' + ttl
        if count: parts['cache_write_input:' + ttl] = count * write_rates[ttl] / 1e6
    if adapter == 'cache_text_v1':
        output = nonnegative(usage['output_tokens'], 'output tokens', True)
        reasoning = nonnegative(usage.get('reasoning_tokens', 0), 'reasoning tokens', True)
        if reasoning > output: raise ValueError('reasoning subset exceeds output total')
        if 'output_per_million' not in rate: return None, 'missing output rate'
        parts['output_including_reasoning'] = output * nonnegative(rate['output_per_million'], 'output rate') / 1e6
    return parts, None


def price(event, card):
    if event.get('billing_identity') is not None:
        billing_identity(event['billing_identity'])
        check_flat_scope(event, event['billing_identity'])
    if event.get('cost_usd') is not None:
        return {'status': 'reported', 'cost_usd': nonnegative(event['cost_usd'], 'reported cost'),
                'billing_identity': event.get('billing_identity'),
                'basis': event.get('cost_source', 'adapter report; not independently reconciled')}
    rate, adapter, reason = select_rate(event, card)
    usage = event.get('usage')
    if rate is None or not isinstance(usage, dict): return unknown(reason or 'missing rate or usage')
    allowed = {'input_tokens', 'output_tokens', 'cached_input_tokens', 'input_tokens_details',
               'reasoning_tokens', 'output_tokens_details', 'cache_write_input_tokens',
               'cache_write_input_tokens_by_ttl', 'units'}
    if set(usage) - allowed: return unknown('unadapted usage fields; preserve native usage and normalize explicitly')
    parts = {}
    if adapter in {'cache_text_v1', 'cache_input_v1'}:
        parts, reason = cached_parts(usage, rate, adapter, event.get('billing_identity'))
        if parts is None: return unknown(reason)
    elif 'cache_write_input_tokens_by_ttl' in usage:
        return unknown('TTL-partitioned writes require a cache adapter')
    elif adapter == 'units_v1':
        if set(usage) != {'units'}: return unknown('units_v1 accepts only explicit normalized units')
    else:
        if 'input_tokens' not in usage: return unknown('missing input token total')
        incoming = nonnegative(usage['input_tokens'], 'input tokens', True)
        if adapter == 'input_only_v1':
            if set(usage) - {'input_tokens', 'units'}:
                return unknown('input_only_v1 does not accept output/cache counters')
            nonnegative(rate['input_per_million'], 'input_per_million')
            parts['input'] = incoming * rate['input_per_million'] / 1e6
        else:
            if 'output_tokens' not in usage: return unknown('missing token totals')
            outgoing = nonnegative(usage['output_tokens'], 'output tokens', True)
            incoming_details = usage.get('input_tokens_details', {})
            outgoing_details = usage.get('output_tokens_details', {})
            if not isinstance(incoming_details, dict) or not isinstance(outgoing_details, dict):
                raise ValueError('token details must be objects')
            if set(incoming_details) - {'cached_tokens'} or set(outgoing_details) - {'reasoning_tokens'}:
                return unknown('modality or other detail counters require a dedicated normalization adapter')
            cached = usage.get('cached_input_tokens', incoming_details.get('cached_tokens'))
            if cached is None: return unknown('cache counter missing; normalize explicitly')
            cached = nonnegative(cached, 'cached input tokens', True)
            if 'cached_tokens' in incoming_details and incoming_details['cached_tokens'] != cached:
                raise ValueError('conflicting normalized cache counters')
            if 'cached_tokens' in incoming_details: nonnegative(incoming_details['cached_tokens'], 'detail cached tokens', True)
            reasoning = usage.get('reasoning_tokens', outgoing_details.get('reasoning_tokens', 0))
            nonnegative(reasoning, 'reasoning tokens', True)
            if 'reasoning_tokens' in outgoing_details and outgoing_details['reasoning_tokens'] != reasoning:
                raise ValueError('conflicting normalized reasoning counters')
            if 'reasoning_tokens' in outgoing_details: nonnegative(outgoing_details['reasoning_tokens'], 'detail reasoning tokens', True)
            writes = nonnegative(usage.get('cache_write_input_tokens', 0), 'cache write input tokens', True)
            if 'cache_write_input_tokens' in usage and rate.get('cache_write_accounting') not in {'input_subset', 'separate'}:
                return unknown('declare cache_write_accounting as input_subset or separate')
            write_subset = writes if rate.get('cache_write_accounting') == 'input_subset' else 0
            if cached + write_subset > incoming or reasoning > outgoing:
                raise ValueError('cached/cache-write subsets exceed input or reasoning subset exceeds output totals')
            for field in ('input_per_million', 'cached_input_per_million', 'output_per_million'):
                nonnegative(rate[field], field)
            parts = {'uncached_input': (incoming - cached - write_subset) * rate['input_per_million'] / 1e6,
                     'cached_input': cached * rate['cached_input_per_million'] / 1e6,
                     'output_including_reasoning': outgoing * rate['output_per_million'] / 1e6}
            if writes:
                if 'cache_write_input_per_million' not in rate: return unknown('cache write rate missing')
                parts['cache_write_input'] = writes * nonnegative(rate['cache_write_input_per_million'], 'cache write rate') / 1e6
    extra = unit_parts(usage, rate)
    if extra is None: return unknown('unpriced normalized extra unit')
    parts.update(extra)
    extras = event.get('external_charges_usd', [])
    if not isinstance(extras, list): raise ValueError('external_charges_usd must be a list')
    parts['external_known'] = sum(nonnegative(x, 'external charge') for x in extras)
    complete = event.get('all_billable_usage_included') is True
    return {'status': 'estimated_complete' if complete else 'estimated_partial', 'cost_usd': sum(parts.values()),
            'components': parts, 'billing_identity': event.get('billing_identity'), 'usage_adapter': adapter,
            'identity_status': 'exact' if event.get('billing_identity') else 'legacy_model_only',
            'rate_card_version': card['version'], 'rate_card_sha256': sha(card),
            'warning': None if complete else 'Tools, storage, sandbox, retries or other charges may be absent; not total task cost'}


def profile(events, card):
    if any(not isinstance(card.get(key), str) or not card[key] for key in ('version', 'effective_date', 'source')):
        raise ValueError('rate card requires version, effective_date and source')
    rows = [{'id': e.get('id'), 'stage': e.get('stage'), 'model': e.get('model'), **price(e, card)} for e in events]
    unknown_count = sum(r['status'] == 'unknown' for r in rows)
    partial = sum(r['status'] == 'estimated_partial' for r in rows)
    known = sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None)
    return {'rows': rows, 'known_or_estimated_subtotal_usd': known, 'unknown_events': unknown_count, 'partial_events': partial,
            'total_cost_usd': known if not unknown_count and not partial else None,
            'basis': 'per-event exact billing scope, or legacy text scope; normalized adapters are not provider SDK field mappings'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events', type=Path, required=True); p.add_argument('--rates', type=Path, required=True)
    a = p.parse_args()
    try: print(json.dumps(profile(read_jsonl(a.events), read_json(a.rates)), ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError, KeyError, TypeError) as e: print(json.dumps({'error': str(e)})); return 2
if __name__ == '__main__': sys.exit(main())
