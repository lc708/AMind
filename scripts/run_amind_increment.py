#!/usr/bin/env python3
"""Run the one-off 2026-09-08 source update without mutating the v1 vault.

All network observations and progress live under corpus/increments/<batch>.
This command has no scheduler or automatic publication side effects.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collect_pages as collector
import discover as discovery

BATCH_ID = '2026-09-08'
BATCH = ROOT / 'corpus/increments' / BATCH_ID
THROTTLE = collector.HostThrottle(0.5)
LOCK = threading.Lock()
URL_LOCKS: dict[str, threading.Lock] = {}
NETWORK_FETCH = collector.fetch_with_retries


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    collector.atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n', BATCH)


def write_jsonl(path, rows):
    collector.atomic_write_text(path, ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows), BATCH)


def rows_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def normalize(url):
    return discovery.normalize_url(url) or url


def preserve_baseline():
    path = BATCH / 'baseline.json'
    if path.exists():
        baseline = read_json(path)
        for name, expected in baseline['fingerprints'].items():
            if digest((ROOT / name).read_bytes()) != expected['sha256']:
                raise RuntimeError(f'frozen baseline changed: {name}')
        return baseline
    paths = [ROOT / name for name in (
        'config/sources.json', 'config/person-expansion-sources.json', 'config/spoken-sources.json',
        'corpus/manifest.csv', 'corpus/article-candidates.csv',
        'corpus/nuwa-v1-analysis-units.jsonl', 'scripts/discover.py', 'scripts/collect_pages.py',
    )]
    paths.extend(p for p in (ROOT / 'release/amind-v1').rglob('*') if p.is_file())
    fingerprints = {p.relative_to(ROOT).as_posix(): {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size} for p in sorted(paths)}
    baseline = {'batch_id': BATCH_ID, 'base_release': 'amind-v1', 'source_enumeration_cutoff': '2026-08-17',
                'started_at': now(), 'timezone': 'Asia/Singapore', 'fingerprints': fingerprints}
    write_json(path, baseline)
    return baseline


def request(url, retries=1, max_bytes=16*1024*1024, retry_failed=False):
    key = digest(url.encode())
    with LOCK:
        gate = URL_LOCKS.setdefault(key, threading.Lock())
    with gate:
        metadata_path = BATCH / 'requests' / (key + '.json')
        if metadata_path.exists():
            result = read_json(metadata_path)
            if result.get('ok'):
                payload = (ROOT / result['raw_path']).read_bytes()
                if digest(payload) != result['raw_sha256']:
                    raise RuntimeError(f'cached response hash mismatch: {url}')
                return payload, result['final_url'], result['content_type'], str(result['http_status'])
            if not retry_failed:
                raise RuntimeError(result.get('error', 'previous request failed'))
            history_path = BATCH / 'request-history' / (key + '-' + digest(metadata_path.read_bytes())[:12] + '.json')
            write_json(history_path, result)
        started = now()
        result, attempts = NETWORK_FETCH(url, 25, max_bytes, THROTTLE, retries)
        payload = result.pop('data', b'')
        result.update({'started_at': started, 'completed_at': now(), 'attempts': attempts})
        if result.get('ok'):
            sha = digest(payload)
            raw_path = BATCH / 'raw' / (sha + '.bin')
            if not raw_path.exists():
                collector.atomic_write_bytes(raw_path, payload, BATCH)
            result.update({'raw_sha256': sha, 'raw_path': raw_path.relative_to(ROOT).as_posix(), 'bytes': len(payload)})
        write_json(metadata_path, result)
        if not result.get('ok'):
            raise RuntimeError(result.get('error', 'request failed'))
        return payload, result['final_url'], result['content_type'], str(result['http_status'])


def configured_sources():
    sources = []
    for source in read_json(ROOT / 'config/sources.json')['sources']:
        if source['method'].startswith('wayback'):
            continue
        sources.append({**source, 'lane': 'main'})
    for person in read_json(ROOT / 'config/person-expansion-sources.json')['people']:
        for source in person['sources']:
            if source['method'] not in {'index', 'feed', 'sitemap'}:
                continue
            source = dict(source)
            if 'export.arxiv.org/api/query' in source.get('url', ''):
                source['url'] += '&sortBy=lastUpdatedDate&sortOrder=descending'
            sources.append({**source, 'publisher': person['canonical_name'],
                            'surface': 'core-person-curated-index', 'link_policy': 'all_http',
                            'lane': 'person', 'required': True})
    for surface in read_json(ROOT / 'config/spoken-sources.json')['official_surfaces']:
        for index, url in enumerate(surface['entrypoints']):
            sources.append({'id': surface['surface_id'] + '-' + str(index), 'url': url,
                            'method': 'feed' if '/feeds/' in url else 'index',
                            'publisher': 'Anthropic', 'surface': 'official-spoken-index',
                            'link_policy': 'same_host', 'lane': 'spoken', 'required': True})
    return sources


def collect_source(source):
    occurrences, fetches = [], []
    method = source['method']
    if method == 'sitemap':
        discovery.parse_sitemap(source, source['url'], occurrences, fetches, set())
    elif method == 'feed':
        discovery.parse_feed(source, occurrences, fetches)
    elif method == 'index':
        discovery.parse_index(source, occurrences, fetches)
    elif method == 'seed':
        discovery.parse_seed(source, occurrences, fetches)
    return occurrences, fetches


def known_urls():
    known = {normalize(r['url']): r for r in rows_csv(ROOT / 'corpus/manifest.csv')}
    for name in ('person-expansion-decisions.jsonl', 'supplemental-unified-source-urls.jsonl'):
        for row in read_jsonl(ROOT / 'corpus' / name):
            url = row.get('url') or row.get('normalized_url')
            if url:
                known.setdefault(normalize(url), {**row, 'known_in': name})
    for row in rows_csv(ROOT / 'corpus/spoken-discovery-manifest.csv'):
        url = row.get('url') or row.get('canonical_url') or row.get('source_url')
        if url:
            known.setdefault(normalize(url), row)
    return known


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def discover_batch():
    preserve_baseline()
    discovery.INDEX_DIR = BATCH / 'indexes'
    discovery.fetch = request
    sources = configured_sources()
    write_json(BATCH / 'sources.json', sources)
    occurrences, fetches = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(collect_source, s): s for s in sources}
        for future in as_completed(futures):
            source = futures[future]
            found, observations = future.result()
            occurrences.extend(found)
            fetches.extend(observations)
            failed = sum(not o.ok for o in observations)
            print(f"{source['id']}: {len(found)} links; {failed} failed observations", flush=True)
    rows = discovery.aggregate_occurrences(occurrences)
    known = known_urls()
    delta = []
    for row in rows:
        previous = known.get(normalize(row['url']))
        delta.append({**row, 'discovery_change': 'new_url' if previous is None else 'known_url',
                      'previous_record_id': (previous or {}).get('record_id', ''),
                      'previous_lastmod': (previous or {}).get('lastmod', ''),
                      'lastmod_changed': previous is not None and row['lastmod'] != previous.get('lastmod', '')})
    write_jsonl(BATCH / 'occurrences.jsonl', [dataclasses.asdict(r) for r in sorted(occurrences, key=lambda r: (r.source_id, r.url))])
    write_jsonl(BATCH / 'source-fetches.jsonl', [dataclasses.asdict(r) for r in sorted(fetches, key=lambda r: (r.source_id, r.requested_url, not r.ok))])
    write_jsonl(BATCH / 'discovery.jsonl', delta)
    summary = {'completed_at': now(), 'configured_sources': len(sources), 'urls': len(rows),
               'new_urls': sum(r['discovery_change'] == 'new_url' for r in delta),
               'new_classes': dict(Counter(r['candidate_class'] for r in delta if r['discovery_change'] == 'new_url')),
               'failed_sources': sorted({r.source_id for r in fetches if not r.ok}),
               'archive_reenumeration': 'not repeated; historical recovery is targeted to failed required works'}
    write_json(BATCH / 'discovery-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def timestamp(value):
    values = []
    for item in value.split(' | '):
        try:
            parsed = datetime.fromisoformat(item.replace('Z', '+00:00'))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(item)
            except (ValueError, TypeError):
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        values.append(parsed.timestamp())
    return max(values, default=0)


def select_collection():
    cutoff = timestamp('2026-08-17T08:31:04+00:00')
    units = read_jsonl(ROOT / 'corpus/nuwa-v1-analysis-units.jsonl')
    baseline_urls = {normalize(u['canonical']) for u in units}
    selection = []
    for row in read_jsonl(BATCH / 'discovery.jsonl'):
        new = row['discovery_change'] == 'new_url'
        host, path = row['host'], row['path']
        reason = ''
        if row['language'] != 'en':
            reason = 'translation retained in discovery; original-English scope'
        elif row['scope_status'] == 'exclude':
            reason = 'discovery classification excludes non-work navigation or artifacts'
        elif new and row['scope_status'] == 'include':
            reason = 'collect:new first-party written candidate'
        elif new and host == 'anthropic.com' and path in {'/beneficial-deployments', '/claude-fable-and-mythos-5-1', '/company/leadership'}:
            reason = 'collect:new substantive official page or attribution evidence'
        elif new and row['candidate_class'] == 'document-attachment' and (host.endswith('.anthropic.com') or host == 'anthropic.com'):
            reason = 'collect:new official attachment'
        elif new and host == 'arxiv.org' and timestamp(row['lastmod']) >= timestamp('2026-08-10'):
            reason = 'collect:recent author-index candidate; attribution needs review'
        elif new and host in {'alextamkin.com', 'jan.leike.name', 'aligned.substack.com', 'benjmann.net', 'evhub.github.io', 'dganguli.github.io', 'ethanperez.net'} and path not in {'/', '/home', '/photography', '/ceramics', '/essays'}:
            reason = 'collect:new person-controlled written candidate'
        elif host == 'platform.claude.com' and '/release-notes/system-prompts' in path and '/login' not in path:
            reason = 'collect:official system-prompt version surface'
        elif not new and (row['scope_status'] == 'include' or normalize(row['url']) in baseline_urls):
            if timestamp(row['lastmod']) > cutoff or not timestamp(row['lastmod']) or row['candidate_class'] == 'institutional-material':
                reason = 'collect:existing work revision check'
            else:
                reason = 'retained:dated source index reports no post-baseline modification'
        else:
            reason = 'retained:discovery or supplemental metadata; not a new qualifying written work'
        selection.append({**row, 'collection_reason': reason})
    write_jsonl(BATCH / 'collection-decisions.jsonl', selection)
    selected = [r for r in selection if r['collection_reason'].startswith('collect:')]
    fields = list(selected[0]) if selected else ['record_id', 'url']
    discovery.write_csv(BATCH / 'collection-queue.csv', fields, selected)
    print(json.dumps({'selected': len(selected), 'reasons': dict(Counter(r['collection_reason'] for r in selection))}, ensure_ascii=False, indent=2), flush=True)
    return selected


def cached_fetch(url, timeout, max_bytes, throttle, retries, response_guard=None):
    try:
        data, final_url, content_type, status = request(url, retries)
        observation = read_json(BATCH / 'requests' / (digest(url.encode()) + '.json'))
        if response_guard is not None:
            refusal = response_guard(final_url, observation.get('headers', {}))
            if refusal:
                raise RuntimeError(str(refusal))
        return {**observation, 'data': data}, observation['attempts']
    except RuntimeError as error:
        path = BATCH / 'requests' / (digest(url.encode()) + '.json')
        observation = read_json(path) if path.exists() else {'ok': False, 'error': str(error)}
        return observation, observation.get('attempts', [])


def collect_batch():
    preserve_baseline()
    selected = select_collection()
    collector.fetch_with_retries = cached_fetch
    args = argparse.Namespace(records_dir=BATCH/'records', texts_dir=BATCH/'texts', blobs_dir=BATCH/'blobs',
                              max_bytes=16*1024*1024, refresh=False, timeout=18, retries=1,
                              archive_fallback=False, snapshot_date=BATCH_ID, workers=8, host_delay=0.5)
    collector.validate_output_roots(args.records_dir, args.texts_dir, args.blobs_dir)
    collector.collect_selected_rows(args, selected)


def recover_batch():
    preserve_baseline()
    selected = rows_csv(BATCH / 'collection-queue.csv')
    recovery = []
    for row in selected:
        path = BATCH / 'records' / (row['record_id'] + '.json')
        record = read_json(path) if path.exists() else {}
        if 'content_too_large' in str(record.get('resolved', {}).get('error', '')):
            recovery.append(row)
    children = []
    for row in selected:
        if row['discovery_change'] != 'new_url':
            continue
        path = BATCH / 'records' / (row['record_id'] + '.json')
        record = read_json(path) if path.exists() else {}
        for link in record.get('extracted', {}).get('body_links', []):
            url, anchor = link.get('url', ''), link.get('anchor_text', '')
            if not urlsplit(url).hostname or not urlsplit(url).hostname.endswith('anthropic.com'):
                continue
            if '.pdf' not in url.lower():
                continue
            if anchor.casefold() not in {'paper', 'appendix', 'august risk report', 'risk report appendix 2.25'}:
                continue
            child = dict(row)
            child.update({'url': url, 'record_id': 'am-inc-' + digest(normalize(url).encode())[:12],
                          'host': urlsplit(url).hostname, 'path': urlsplit(url).path,
                          'candidate_class': 'document-attachment', 'discovered_from': row['url'],
                          'discovery_change': 'one_hop_attachment', 'collection_reason': 'collect:explicit first-party paper or appendix'})
            children.append(child)
    unique = {normalize(row['url']): row for row in recovery + children}
    recovery = list(unique.values())
    write_jsonl(BATCH / 'recovery-queue.jsonl', recovery)
    for row in recovery:
        try:
            request(row['url'], 1, 96*1024*1024, retry_failed=True)
            print('recovery captured', row['record_id'], row['url'], flush=True)
        except RuntimeError as error:
            print('recovery failed', row['record_id'], str(error), flush=True)
    collector.fetch_with_retries = cached_fetch
    args = argparse.Namespace(records_dir=BATCH/'records', texts_dir=BATCH/'texts', blobs_dir=BATCH/'blobs',
                              max_bytes=96*1024*1024, refresh=False, timeout=25, retries=1,
                              archive_fallback=False, snapshot_date=BATCH_ID, workers=3, host_delay=0.5)
    collector.collect_selected_rows(args, recovery)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['discover', 'collect', 'recover'])
    args = parser.parse_args()
    BATCH.mkdir(parents=True, exist_ok=True)
    if args.stage == 'discover':
        discover_batch()
    elif args.stage == 'collect':
        collect_batch()
    elif args.stage == 'recover':
        recover_batch()


if __name__ == '__main__':
    main()
