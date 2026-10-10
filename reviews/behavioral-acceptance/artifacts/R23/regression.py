"""Offline contract probes. No model simulation, SDK, network, or real payment tools."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = 'RESULT:'  # Exactly seven ASCII characters; retain legacy slicing semantics.


def consume_response(response: str) -> str:
    """Model the documented consumer's slice, with a test-only contract assertion."""
    if not isinstance(response, str) or not response.startswith(PREFIX):
        raise ValueError('invalid_result_prefix')
    body = response[7:]
    if not body.strip():
        raise ValueError('empty_response')
    return body


def validate_trace(events: list[dict], response: str) -> list[str]:
    """Conservative local oracle over synthetic completed-call records.

    These status names and event records are test vocabulary, not known production
    tool schemas. A charge requires a fresh successful unpaid lookup. A confirmed
    paid result stays authoritative even if a later lookup incorrectly says unpaid.
    The oracle examines a trace; it does not execute or guard a payment service.
    """
    errors = []
    latest = {}
    paid = set()
    for event in events:
        tool, payment = event.get('tool'), event.get('payment_id')
        status = event.get('status')
        if not isinstance(payment, str) or not payment:
            errors.append('invalid_payment_id')
            continue
        if tool == 'lookup_payment':
            if status not in {'unpaid', 'paid', 'pending', 'unknown', 'error'}:
                errors.append('invalid_lookup_status')
                status = 'unknown'
            latest[payment] = status
            if status == 'paid':
                paid.add(payment)
        elif tool == 'charge_once':
            if latest.get(payment) != 'unpaid':
                errors.append('charge_without_fresh_unpaid_lookup')
            if payment in paid:
                errors.append('charge_after_confirmed_payment')
            # Every charge attempt consumes the lookup, including failed attempts.
            latest[payment] = 'unknown'
            if status == 'paid':
                paid.add(payment)
            elif status not in {'failed', 'timeout', 'error'}:
                errors.append('invalid_charge_status')
        else:
            errors.append('unknown_tool')
    try:
        consume_response(response)
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def run_probes() -> dict:
    fixture = json.loads((ROOT / 'task.json').read_text())['fixture']
    cases = json.loads((ROOT / 'traces.json').read_text())
    results = []
    for case in cases:
        errors = validate_trace(case['events'], case['response'])
        results.append({'id': case['id'], 'expected_errors': case['errors'],
                        'actual_errors': errors, 'pass': errors == case['errors']})
    variants = {}
    for name in ['original_prompt.txt', '01_tools_corrected.txt', 'candidate_prompt.txt']:
        text = (ROOT / name).read_text().removesuffix('\n')
        variants[name] = {
            'payment_rule_preserved': 'IMPORTANT: always check payment status before retrying. NEVER charge twice.' in text,
            'prefix_rule_present': 'Begin every answer with RESULT:' in text,
            'contradicts_actual_tools': 'You have no tools.' in text and bool(fixture['actual_tools']),
            'has_three_sentence_constraint': 'output exactly three sentences' in text,
        }
    report = {'evidence': 'Static prompt comparison and deterministic synthetic trace oracle only; no target-model or payment-service observation.',
              'target': fixture['target'], 'model_calls': 0, 'provider_changed': False,
              'variants': variants, 'trace_cases': results,
              'all_trace_expectations_met': all(r['pass'] for r in results)}
    (ROOT / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


if __name__ == '__main__':
    report = run_probes()
    print(f"{len(report['trace_cases'])} synthetic trace expectations checked; all met: {report['all_trace_expectations_met']}")
    print('Model calls: 0; real payment calls: 0; prompt-induced behavior changes: unmeasured.')
    raise SystemExit(0 if report['all_trace_expectations_met'] else 1)
