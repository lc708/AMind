"""Account finished calls once; missing billable evidence remains unknown."""
import math

SCOPE = {'provider', 'interface', 'model', 'service_tier', 'region'}

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def exact_scope(value):
    return isinstance(value, dict) and set(value) == SCOPE and all(isinstance(v, str) and v for v in value.values())


def price(event, rates):
    if 'cost_usd' in event:
        value = event['cost_usd']
        return value if number(value) else 0.0
    scope = event.get('billing_identity')
    matches = [r for r in rates.get('rates', []) if r.get('identity', {}).get('model') == (scope or {}).get('model')]
    if not matches:
        return None
    rate, usage = matches[0], event.get('usage')
    if not isinstance(usage, dict):
        return None
    if rate.get('mode') == 'input_only':
        if set(usage) != {'input_tokens'}:
            return None
        fields = [('input_tokens', 'input_per_million')]
        return sum(usage[a] * rate[b] / 1e6 for a, b in fields) if all(number(usage.get(a)) and number(rate.get(b)) for a, b in fields) else None
    if rate.get('mode') != 'text':
        return None
    required = ('input_tokens', 'cached_input_tokens', 'output_tokens')
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in required):
        return None
    incoming, cached, outgoing = (usage[k] for k in required)
    reasoning = usage.get('reasoning_tokens', 0)
    if type(reasoning) is not int or not 0 <= reasoning <= outgoing or cached > incoming:
        return None
    if not all(number(rate.get(k)) for k in ('input_per_million', 'cached_per_million', 'output_per_million')):
        return None
    return ((incoming - cached) * rate['input_per_million'] + cached * rate['cached_per_million'] + outgoing * rate['output_per_million']) / 1e6


def account(events, rates):
    starts, finishes, issues = {}, {}, []
    for e in events:
        kind, key = e.get('event'), e.get('attempt_id')
        if kind not in ('started', 'finished') or not isinstance(key, str) or not key:
            issues.append('invalid_attempt_event'); continue
        bucket = starts if kind == 'started' else finishes
        if key in bucket:
            pass  # exporter retries may repeat a write
        if kind == 'finished':
            prior = starts.get(key)
            if prior is None or any(prior.get(k) != e.get(k) for k in ('case_id', 'rep')):
                issues.append('unmatched_finished')
        bucket[key] = e
    known, unknown = 0.0, 0
    for e in finishes.values():
        if e.get('status') != 'ok':
            continue
        cost = price(e, rates)
        if cost is None:
            unknown += 1
        else:
            known += cost
    attempts = {'started': len(starts), 'finished': len(finishes),
                'interrupted': len(set(starts) - set(finishes)),
                'failed': sum(e.get('status') != 'ok' for e in finishes.values())}
    costs = {'known_usd': known, 'total_usd': None if unknown else known, 'unknown_attempts': unknown}
    return attempts, costs, issues
