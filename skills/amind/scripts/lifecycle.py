"""Dated current-answer eligibility; historical evidence is never rewritten."""
from __future__ import annotations

import datetime as dt
import calendar
import hashlib
import json
from pathlib import Path

KINDS = {'corrected', 'superseded', 'historical_only', 'effective_window', 'publication_window'}


def publication_bounds(value):
    """Preserve month precision without manufacturing a publication day."""
    precise = day(value)
    if precise:
        return precise, precise, 'day'
    value = str(value or '').strip()
    month = None
    if len(value) == 7 and value[4:5] == '-':
        try:
            month = dt.date.fromisoformat(value + '-01')
        except ValueError:
            pass
    else:
        for number, name in enumerate(calendar.month_name):
            if number and value.startswith(name + ' '):
                try:
                    month = dt.date(int(value[len(name) + 1:]), number, 1)
                except ValueError:
                    pass
                break
    if month:
        end = month.replace(day=calendar.monthrange(month.year, month.month)[1])
        return month, end, 'month'
    return None, None, 'unknown'


def day(value):
    """Only a precise ISO day is a date; a sitemap/month is not a publication day."""
    if not value:
        return None
    value = str(value)
    try:
        return dt.date.fromisoformat(value[:10]) if len(value) >= 10 else None
    except ValueError:
        return None


def as_of_date(manifest, requested=None):
    value = requested or manifest.get('source_observation_cutoff') or '2026-08-17'
    parsed = day(value)
    if not parsed or (requested and parsed.isoformat() != requested):
        raise ValueError('as-of must be a valid YYYY-MM-DD date')
    return parsed.isoformat()


def validate_records(records):
    seen = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('current-status decision must be an object')
        identity = row.get('status_id')
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError('missing or duplicate current-status identity')
        seen.add(identity)
        if row.get('kind') not in KINDS:
            raise ValueError(f'unknown current-status kind: {identity}')
        targets = []
        for field in ('target_claim_ids', 'target_analysis_unit_ids'):
            values = row.get(field, [])
            if not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values) or len(set(values)) != len(values):
                raise ValueError(f'invalid current-status targets: {identity}')
            targets.extend(values)
        if not targets or not row.get('reason') or not str(row.get('source_canonical', '')).startswith('https://'):
            raise ValueError(f'unbound current-status decision: {identity}')
        for field in ('valid_from', 'valid_until'):
            if row.get(field) and (not day(row[field]) or day(row[field]).isoformat() != row[field]):
                raise ValueError(f'invalid {field}: {identity}')
        start, end = day(row.get('valid_from')), day(row.get('valid_until'))
        if start and end and start >= end:
            raise ValueError(f'empty current-status window: {identity}')
        if row['kind'] == 'publication_window':
            first, last, precision = publication_bounds(row.get('publication_month'))
            if precision != 'month' or start != first or end:
                raise ValueError(f'invalid publication month window: {identity}')
        if row['kind'] not in {'effective_window', 'publication_window'} and not end:
            raise ValueError(f'current-status correction needs valid_until: {identity}')
    return records


def load_records(data_root, manifest):
    artifact = next((a for a in manifest.get('artifacts', []) if a.get('path') == 'current-status.jsonl'), None)
    if artifact is None:
        if manifest.get('current_status_bundled'):
            raise ValueError('missing declared current-status artifact')
        return []
    payload = (Path(data_root) / 'current-status.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != artifact.get('sha256') or len(payload) != artifact.get('bytes'):
        raise ValueError('current-status artifact fingerprint mismatch')
    records = [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
    if len(records) != artifact.get('rows'):
        raise ValueError('current-status artifact population mismatch')
    return validate_records(records)


def assess(row, records, as_of, cutoff):
    when = day(as_of)
    reasons, applicable = [], []
    first, last, precision = publication_bounds(row.get('source_published_at'))
    for rule in records:
        if (row.get('claim_id') not in rule.get('target_claim_ids', [])
                and row.get('analysis_unit_id') not in rule.get('target_analysis_unit_ids', [])):
            continue
        applicable.append(rule)
        start, end = day(rule.get('valid_from')), day(rule.get('valid_until'))
        if rule['kind'] == 'publication_window':
            first, last, precision = publication_bounds(rule['publication_month'])
        elif rule['kind'] == 'effective_window':
            if start and when < start:
                reasons.append('not_yet_effective')
            if end and when >= end:
                reasons.append('no_longer_effective')
        elif end and when >= end:
            reasons.append(rule['kind'])
    if first and when < first:
        reasons.append('not_yet_published')
    elif precision == 'month' and when < last:
        # The source could have appeared later in this month. Retain it in show
        # and history, but do not certify it as available on the requested day.
        reasons.append('publication_day_unconfirmed')
    # Backward compatibility for packages without dated lifecycle decisions.
    if row.get('later_observed_revision') and not any(rule['kind'] != 'publication_window' for rule in applicable):
        reasons.append('later_observed_revision')
    return {
        'eligible': not reasons, 'as_of': as_of, 'reasons': sorted(set(reasons)),
        'publication_day_known': precision == 'day',
        'publication_date_precision': precision,
        'publication_earliest_possible': first.isoformat() if first else None,
        'publication_latest_possible': last.isoformat() if last else None,
        'publication_availability': ('not_yet_published' if 'not_yet_published' in reasons else
            'uncertain' if 'publication_day_unconfirmed' in reasons else
            'unknown' if precision == 'unknown' else 'available'),
        'decisions': applicable, 'source_observation_cutoff': cutoff,
        'verification_required': bool(day(cutoff) and when > day(cutoff)),
        'scope': 'known public evidence at the recorded observation cutoff; not a live policy or model registry',
    }
