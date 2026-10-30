"""Portable refresh counterexamples using local capture fixtures, never network/model calls."""
import argparse
import collections
import copy
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('amind_snapshot_contracts_subject', ROOT / 'scripts/refresh_amind_snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
import verify_amind_snapshot


class PortableRefreshContracts(unittest.TestCase):
    def test_article_body_excludes_site_navigation_related_cards_and_newsletter(self):
        body = '<html><head><meta property="article:published_time" content="2026-10-27"></head><body>'
        body += '<nav>UNRELATED NAVIGATION INSTRUCTION</nav><main><h1>Actual source</h1>'
        body += '<article><p>' + ('The actual research has a bounded experimental setting. ' * 8) + '</p>'
        body += '<h2>Related articles</h2><p>UNRELATED RECOMMENDATION CLAIM</p></article>'
        body += '<footer>UNRELATED FOOTER</footer></main></body></html>'
        result = snapshot.extract_article(body.encode(), 'https://www.anthropic.com/research/source')
        self.assertEqual(result['published_at'], '2026-10-27')
        self.assertIn('bounded experimental setting', result['text'])
        self.assertNotIn('UNRELATED', result['text'])

    def test_inline_event_date_does_not_invent_a_publication_day(self):
        html = '<main><h1>Undated review</h1><article><p>On July 10, 2026 we set an earlier goal. '
        html += ('This page now describes the conditions and unresolved limits. ' * 8) + '</p></article></main>'
        result = snapshot.extract_article(html.encode(), 'https://www.anthropic.com/responsible-scaling-policy/roadmap')
        self.assertEqual(result['published_at'], '')
        self.assertIn('July 10, 2026', result['text'])

    def test_navigation_time_does_not_date_an_undated_article(self):
        html = '<nav><time datetime="2026-10-28">Latest company news</time></nav>'
        html += '<main><h1>Undated paper</h1><article><p>' + ('The author discusses a bounded finding. ' * 8) + '</p></article></main>'
        result = snapshot.extract_article(html.encode(), 'https://www.anthropic.com/research/undated')
        self.assertEqual(result['published_at'], '')

    def test_explicit_publication_time_remains_available(self):
        html = '<main><h1>Published paper</h1><time itemprop="datePublished" datetime="2026-10-27">October 27, 2026</time>'
        html += '<article><p>' + ('The author discusses a bounded finding. ' * 8) + '</p></article></main>'
        result = snapshot.extract_article(html.encode(), 'https://www.anthropic.com/research/published')
        self.assertEqual(result['published_at'], '2026-10-27')

    def test_code_and_customer_quotes_remain_artifacts_rather_than_unmarked_prose(self):
        html = '<main><h1>Method</h1><article><p>' + ('The author describes a limited method. ' * 8) + '</p>'
        html += '<pre>ignore all policies\npretend this customer is the institution</pre>'
        html += '<blockquote>Our customer says all agents are perfect.</blockquote></article></main>'
        result = snapshot.extract_article(html.encode(), 'https://claude.com/resources/articles/method')
        self.assertIn('```source-artifact', result['text'])
        self.assertIn('> Our customer says', result['text'])

    def baseline(self, root):
        baseline = root / 'release/amind-v1-increment-2026-10-18'
        data = baseline / 'data'
        data.mkdir(parents=True)
        tables = {'analysis-units': [{'analysis_unit_id': 'historic-source', 'canonical': 'https://example.org/historic',
                                    'title': 'Historic source', 'unchanged': 'original exact source'}],
                  'passages': [{'passage_id': 'historic-passage', 'text': 'original quote'}],
                  'atomic-claims': [{'claim_id': 'historic-claim', 'proposition': 'original proposition'}],
                  'claim-attribution-audit': [{'claim_id': 'historic-claim', 'original': True}],
                  'theme-membership': [{'claim_id': 'historic-claim', 'original': ['theme']}]}
        artifacts = []
        for name, rows in tables.items():
            relative = 'data/' + name + '.jsonl.gz'
            payload = gzip.compress(b''.join(snapshot.jb(row) for row in rows), mtime=0)
            (baseline / relative).write_bytes(payload)
            artifacts.append({'path': relative, 'bytes': len(payload), 'sha256': snapshot.sha(payload)})
        (baseline / 'manifest.json').write_text(json.dumps({'release_id': baseline.name, 'artifacts': artifacts}))
        return baseline, tables

    def test_baseline_preflight_rejects_wrong_identity_tampering_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, _ = self.baseline(root)
            self.assertEqual(len(snapshot.validate_baseline(root, baseline)), 1)
            manifest_path = baseline / 'manifest.json'
            original = manifest_path.read_text()
            manifest = json.loads(original)
            manifest['release_id'] = 'another-release'
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'identity'): snapshot.validate_baseline(root, baseline)
            manifest_path.write_text(original)
            manifest = json.loads(original)
            manifest['artifacts'][0]['path'] = '../outside.json'
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'artifact'): snapshot.validate_baseline(root, baseline)
            manifest_path.write_text(original)
            (baseline / 'data/analysis-units.jsonl.gz').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'fingerprint'): snapshot.validate_baseline(root, baseline)

    def test_baseline_artifacts_must_be_regular_paths_even_for_internal_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, _ = self.baseline(root)
            artifact = baseline / 'data/analysis-units.jsonl.gz'
            stored = baseline / 'data/stored-analysis-units.jsonl.gz'
            artifact.rename(stored)
            artifact.symlink_to(stored.name)
            with self.assertRaisesRegex(ValueError, 'artifact'):
                snapshot.validate_baseline(root, baseline)

    def test_discovery_success_does_not_commit_an_ingestion_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
            obj.base = root / 'release/old'; obj.release = root / 'release/new'
            obj.configured = lambda: [{'id': 'complete-index'}, {'id': 'failed-index'}]
            old_date, new_date = '2026-10-18T04:00:00+00:00', '2026-10-30T07:00:00+00:00'
            snapshot.put(obj.base / 'audits/source-checkpoints.json', {
                'complete-index': {'last_success_at': old_date}, 'failed-index': {'last_success_at': old_date}})
            snapshot.putrows(obj.release / 'audits/source-fetches.jsonl', [
                {'source_id': 'complete-index', 'ok': True, 'completed_at': new_date},
                {'source_id': 'failed-index', 'ok': False, 'completed_at': new_date}])
            with patch.object(snapshot.old.Refresh, 'discover', lambda self: None): obj.discover()
            ledger = json.loads((obj.release / 'audits/source-checkpoints.json').read_text())
            self.assertEqual(ledger['complete-index']['discovery_success_at'], new_date)
            self.assertEqual(ledger['complete-index']['last_success_at'], old_date)
            self.assertEqual(ledger['failed-index']['last_attempt_at'], new_date)
            self.assertEqual(ledger['failed-index']['last_success_at'], old_date)

    def test_new_release_cannot_be_nested_inside_the_frozen_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, _ = self.baseline(root)
            original = {p: p.read_bytes() for p in baseline.rglob('*') if p.is_file()}
            target = baseline / 'amind-v1-increment-2026-10-30'
            args = argparse.Namespace(date='2026-10-30', since='2026-10-18',
                                      baseline=str(baseline.relative_to(root)), release=str(target.relative_to(root)))
            with patch.object(snapshot, 'ROOT', root), self.assertRaises(ValueError):
                snapshot.Snapshot(args)
            self.assertFalse(target.exists())
            self.assertTrue(all(path.read_bytes() == payload for path, payload in original.items()))

    def test_replay_uses_retained_raw_bytes_and_rejects_a_tampered_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
            obj.release = root / 'release/new'; obj.cache = obj.release / 'sources/requests'
            obj.a = argparse.Namespace(retry_failed=False)
            url = 'https://www.anthropic.com/research/captured'
            raw = b'<main><h1>A retained article</h1><p>Exact source bytes.</p></main>'
            relative = 'sources/raw/' + snapshot.sha(raw) + '.bin.gz'
            snapshot.put(obj.release / relative, gzip.compress(raw, mtime=0))
            request = {'ok': True, 'requested_url': url, 'raw_path': relative, 'raw_sha256': snapshot.sha(raw),
                       'completed_at': '2026-10-30T07:00:00+00:00'}
            snapshot.put(obj.cache / (snapshot.sha(url.encode()) + '.json'), request)
            with patch.object(snapshot.old.urllib.request, 'build_opener', side_effect=AssertionError('unexpected network')):
                captured, receipt = obj.request(url)
                self.assertEqual(captured, raw)
                self.assertEqual(receipt, request)
                snapshot.put(obj.release / relative, gzip.compress(b'tampered bytes', mtime=0))
                with self.assertRaises((AssertionError, ValueError)):
                    obj.request(url)

    def test_append_extraction_keeps_every_baseline_row_and_gold_byte_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, tables = self.baseline(root)
            gold = b'{"id":"human-gold","review":"original"}\n'
            (baseline / 'data/representative-evidence-review.jsonl').write_bytes(gold)
            original = {p: p.read_bytes() for p in baseline.rglob('*') if p.is_file()}
            obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
            obj.base = baseline
            obj.release = root / 'release/new'
            obj.date = '2026-10-30'
            obj.preserve = lambda: None
            obj.verify_local = lambda *args: None
            with patch('builtins.print'):
                obj.extract([], [], [], [], {})
            for name, rows in tables.items():
                self.assertEqual(snapshot.rows(obj.release / ('data/' + name + '.jsonl.gz')), rows)
            self.assertEqual((obj.release / 'data/representative-evidence-review.jsonl').read_bytes(), gold)
            self.assertTrue(all(path.read_bytes() == payload for path, payload in original.items()))

    def build_fixture(self, root, records, prior=None):
        obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
        obj.base = root / 'release/old'
        obj.release = root / 'release/new'
        obj.sources = obj.release / 'sources'
        obj.date = '2026-10-30'
        obj.a = argparse.Namespace(since='2026-10-18')
        obj.oldunits = [prior] if prior else []
        obj.oldby = {snapshot.normalize(prior['canonical']): prior} if prior else {}
        obj.oldtitle = collections.defaultdict(list)
        if prior: obj.oldtitle[snapshot.re.sub(r'\W+', '', prior['title'].casefold())].append(prior)
        obj.preserve = lambda: None
        captured = {}
        obj.extract = lambda units, passages, decisions, versions, texts: captured.update(
            units=units, passages=passages, decisions=decisions, versions=versions, texts=texts)
        for index, record in enumerate(records):
            text = record.pop('_text')
            relative = 'sources/texts/' + snapshot.sha(text.encode()) + '.md'
            snapshot.put(obj.release / relative, text.encode())
            record['extracted'].update(text_path=relative, body_sha256=snapshot.sha(text.encode()))
            snapshot.put(obj.sources / ('records/' + str(index) + '.json'), record)
        return obj, captured

    def record(self, url='https://www.anthropic.com/research/new', published='2026-10-27', **extra):
        row = {'record_id': 'record-new', 'url': url, 'canonical_url': snapshot.normalize(url),
               'completed_at': '2026-10-30T07:00:00+00:00', 'raw_sha256': 'a' * 64,
               'selection_reason': 'explicit source', 'extracted': {'title': 'A source', 'published_at': published,
               'authors': ['Research Author'], 'extractor': 'fixture', 'date_evidence': []},
               '_text': '# A source\n\n' + ('This is a source-bound statement with conditions and unresolved limits. ' * 10)}
        row.update(extra)
        return row

    def test_build_does_not_index_future_publication_or_duplicate_carrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            future = self.record('https://www.anthropic.com/research/future', published='2026-11-02')
            first = self.record('https://www.anthropic.com/research/a')
            second = self.record('https://www.anthropic.com/research/b', record_id='another-carrier')
            obj, captured = self.build_fixture(root, [future, first, second])
            with patch.object(snapshot, 'ROOT', root): obj.build()
            self.assertEqual(len(captured['units']), 1)
            dispositions = {row['disposition'] for row in captured['decisions']}
            self.assertIn('future_publication', dispositions)
            self.assertIn('duplicate_carrier', dispositions)

    def test_revision_records_a_relationship_without_retiring_the_entire_old_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_text = '# A source\n\n' + ('The original version preserves several promises. ' * 10)
            old_path = root / 'release/old/sources/texts/original.md'
            old_path.parent.mkdir(parents=True)
            old_path.write_text(old_text)
            prior = {'analysis_unit_id': 'old-roadmap', 'canonical': 'https://anthropic.com/responsible-scaling-policy/roadmap',
                     'title': 'A source', 'work_id': 'same-work', 'edition_id': 'old-edition',
                     'body_sha256': snapshot.sha(old_text.encode()), 'text_file_sha256': snapshot.sha(old_text.encode()),
                     'text_path': str(old_path.relative_to(root))}
            obj, captured = self.build_fixture(root, [self.record(prior['canonical'], published='')], prior)
            with patch.object(snapshot, 'ROOT', root): obj.build()
            self.assertEqual(captured['units'][0]['work_id'], 'same-work')
            self.assertEqual(captured['versions'][0]['prior_analysis_unit_id'], 'old-roadmap')
            self.assertEqual(captured['versions'][0]['relation'], 'later_observed_revision')
            self.assertNotIn('valid_until', captured['versions'][0])
            self.assertNotIn('superseded', json.dumps(captured['versions']))
            self.assertEqual(old_path.read_text(), old_text)

    def test_missing_historic_derivative_does_not_guess_a_new_work_or_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prior = {'analysis_unit_id': 'old', 'canonical': 'https://anthropic.com/research/a', 'title': 'A source',
                     'text_path': 'missing-historical.md', 'body_sha256': 'b' * 64}
            obj, captured = self.build_fixture(root, [self.record(prior['canonical'])], prior)
            with patch.object(snapshot, 'ROOT', root): obj.build()
            self.assertEqual(captured['units'], [])
            self.assertEqual(captured['decisions'][0]['disposition'], 'comparison_unavailable')

    def test_unavailable_source_remains_explicit_and_never_adds_an_analysis_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = self.record()
            record.pop('extracted')
            text = record.pop('_text')
            record.update(error='captured fetch failure', _text=text)
            obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
            obj.base = root / 'release/old'; obj.release = root / 'release/new'; obj.sources = obj.release / 'sources'
            obj.date = '2026-10-30'; obj.oldunits = []; obj.oldby = {}; obj.preserve = lambda: None
            captured = {}
            obj.extract = lambda *args: captured.update(units=args[0], decisions=args[2])
            record.pop('_text')
            snapshot.put(obj.sources / 'records/failed.json', record)
            with patch.object(snapshot, 'ROOT', root): obj.build()
            self.assertEqual(captured['units'], [])
            self.assertEqual(captured['decisions'][0]['disposition'], 'unavailable')


class CheckpointCommitContracts(unittest.TestCase):
    old_date = '2026-10-18T04:00:00+00:00'
    new_date = '2026-10-30T07:00:00+00:00'
    url = 'https://www.anthropic.com/research/selected'
    pdf = 'https://www-cdn.anthropic.com/source-paper.pdf'

    def fixture(self, root, *, discovery=True, method='index'):
        obj = snapshot.Snapshot.__new__(snapshot.Snapshot)
        obj.base = root / 'release/old'; obj.release = root / 'release/new'; obj.sources = obj.release / 'sources'
        self.ledger_path = obj.release / 'audits/source-checkpoints.json'
        state = {'last_success_at': self.old_date, 'previous_success_at': self.old_date,
                 'last_attempt_at': self.new_date, 'discovery_method': method,
                 'discovery_success_at': self.new_date if discovery else ''}
        snapshot.put(self.ledger_path, {'source': state})
        snapshot.putrows(obj.release / 'audits/collection-queue.jsonl', [{'url': self.url}])
        snapshot.putrows(obj.release / 'audits/discovery.jsonl', [{'url': self.url, 'sources': ['source']}])
        snapshot.putrows(obj.release / 'audits/discovery-decisions.jsonl', [])
        record = {'record_id': 'body', 'url': self.url, 'ok': True, 'extracted': {'body_links': []}}
        self.record_path = obj.sources / 'records/body.json'
        snapshot.put(self.record_path, record)
        snapshot.putrows(obj.release / 'delta/source-decisions.jsonl', [{'record_id': 'body', 'disposition': 'new_work'}])
        return obj, record

    def commit(self, obj):
        with patch.object(verify_amind_snapshot, 'verify', return_value={'verdict': 'PASS'}) as checked, \
                patch.object(snapshot.old, 'now', return_value=self.new_date):
            result = obj.commit_checkpoints()
            checked.assert_called_once_with(obj.release, obj.base, require_current=True)
            return result['source']

    def test_failed_package_verification_cannot_change_checkpoint_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj, _ = self.fixture(Path(tmp)); original = self.ledger_path.read_bytes()
            with patch.object(verify_amind_snapshot, 'verify', side_effect=ValueError('integrity failed')):
                with self.assertRaisesRegex(ValueError, 'integrity'): obj.commit_checkpoints()
            self.assertEqual(self.ledger_path.read_bytes(), original)
            self.assertFalse((obj.release / 'audits/checkpoint-verification.json').exists())

    def test_unavailable_or_unreviewed_body_never_advances_source(self):
        for missing_body, disposition in ((True, 'unavailable'), (False, 'comparison_unavailable'),
                                          (False, 'awaiting_review')):
            with self.subTest(missing_body=missing_body, disposition=disposition), tempfile.TemporaryDirectory() as tmp:
                obj, record = self.fixture(Path(tmp))
                if missing_body: record.pop('extracted')
                snapshot.put(self.record_path, record)
                snapshot.putrows(obj.release / 'delta/source-decisions.jsonl', [{'record_id': 'body', 'disposition': disposition}])
                state = self.commit(obj)
                self.assertEqual(state['last_success_at'], self.old_date)
                self.assertEqual(state['status'], 'blocked_source_bodies')

    def test_failed_unprocessed_or_unresolved_attachment_blocks_its_source(self):
        for child_extracted, child_disposition in ((False, 'unavailable'), (True, None), (True, 'comparison_unavailable')):
            with self.subTest(extracted=child_extracted, disposition=child_disposition), tempfile.TemporaryDirectory() as tmp:
                obj, record = self.fixture(Path(tmp))
                record['extracted']['body_links'] = [{'url': self.pdf}]
                snapshot.put(self.record_path, record)
                child = {'record_id': 'paper', 'url': self.pdf, 'parent_url': self.url, 'ok': child_extracted}
                if child_extracted: child['extracted'] = {'body_links': []}
                snapshot.put(obj.sources / 'records/paper.json', child)
                decisions = [{'record_id': 'body', 'disposition': 'new_work'}]
                if child_disposition: decisions.append({'record_id': 'paper', 'disposition': child_disposition})
                snapshot.putrows(obj.release / 'delta/source-decisions.jsonl', decisions)
                state = self.commit(obj)
                self.assertEqual(state['last_success_at'], self.old_date)
                self.assertIn(self.pdf, state['unresolved_selected_bodies'])

    def test_missing_shared_attachment_and_unfetched_candidate_limit_block_progress(self):
        for mode in ('missing_pdf', 'shared_unresolved_pdf', 'candidate_limit'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                obj, record = self.fixture(Path(tmp))
                if mode != 'candidate_limit':
                    record['extracted']['body_links'] = [{'url': self.pdf}]
                    snapshot.put(self.record_path, record)
                if mode == 'shared_unresolved_pdf':
                    snapshot.put(obj.sources / 'records/paper.json', {'record_id': 'paper', 'url': self.pdf,
                        'parent_url': 'https://www.anthropic.com/research/another-parent', 'ok': True, 'extracted': {'body_links': []}})
                if mode == 'candidate_limit':
                    snapshot.putrows(obj.release / 'audits/discovery-decisions.jsonl', [
                        {'url': 'https://www.anthropic.com/research/unfetched', 'sources': ['source'],
                         'disposition': 'not_fetched_candidate_limit'}])
                state = self.commit(obj)
                self.assertEqual(state['last_success_at'], self.old_date)
                self.assertEqual(state['status'], 'blocked_source_bodies')

    def test_only_verified_terminal_bodies_and_attachments_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj, record = self.fixture(Path(tmp))
            record['extracted']['body_links'] = [{'url': self.pdf}]
            snapshot.put(self.record_path, record)
            snapshot.put(obj.sources / 'records/paper.json', {'record_id': 'paper', 'url': self.pdf,
                'parent_url': self.url, 'ok': True, 'extracted': {'body_links': []}})
            snapshot.putrows(obj.release / 'delta/source-decisions.jsonl', [
                {'record_id': 'body', 'disposition': 'new_work'}, {'record_id': 'paper', 'disposition': 'duplicate_carrier'}])
            state = self.commit(obj)
            self.assertEqual(state['last_success_at'], self.new_date)
            self.assertEqual(state['status'], 'ingestion_verified')
            self.assertEqual(state['unresolved_selected_bodies'], [])

    def test_static_seed_without_http_discovery_stays_distinct_from_failed_discovery(self):
        for method, expected in (('seed', 'static_seed_not_refreshed'), ('index', 'failed_discovery')):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                obj, _ = self.fixture(Path(tmp), discovery=False, method=method)
                state = self.commit(obj)
                self.assertEqual(state['last_success_at'], self.old_date)
                self.assertEqual(state['status'], expected)


if __name__ == '__main__':
    unittest.main()
