"""Offline input contracts for source replay; never rebuild locked release data."""
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_amind_sources as refresh


class ReplayInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'baseline'
        self.release = self.root / 'release'
        self.vault = self.root / 'corpus'
        self.unit = {'analysis_unit_id': 'old-unit', 'canonical': 'https://example.org/old',
                     'title': 'Old', 'source_seed_record_ids': ['old-record'],
                     'text_path': 'corpus/texts/old.md'}
        (self.base / 'data').mkdir(parents=True)
        (self.base / 'data/analysis-units.jsonl.gz').write_bytes(
            gzip.compress((json.dumps(self.unit) + '\n').encode(), mtime=0))
        (self.release / 'data').mkdir(parents=True)
        (self.release / 'data/locked.bin').write_bytes(b'frozen data\x00')

    def fingerprints(self):
        return {str(p.relative_to(self.release)): p.read_bytes()
                for p in self.release.rglob('*') if p.is_file()}

    def args(self, stage='build', vault=None):
        return types.SimpleNamespace(stage=stage, baseline=str(self.base), release=str(self.release),
            vault=vault, date='2026-10-18', since='2026-09-08T01:03:42+08:00')

    def fixture_vault(self, record=None):
        self.vault.mkdir()
        (self.vault / 'manifest.csv').write_text('url\nhttps://example.org/old\n')
        (self.vault / 'increments/2026-09-08').mkdir(parents=True)
        (self.vault / 'increments/2026-09-08/discovery.jsonl').write_text(
            '{"url":"https://example.org/old"}\n')
        (self.vault / 'records').mkdir()
        if record is not None:
            (self.vault / 'records/old-record.json').write_text(json.dumps(record))

    def object(self):
        obj = refresh.Refresh.__new__(refresh.Refresh)
        obj.vault, obj.base, obj.release = self.vault, self.base, self.release
        obj.oldunits = [self.unit]
        return obj

    def test_required_stages_without_explicit_vault_fail_before_any_write(self):
        before = self.fingerprints()
        for stage in ['discover', 'build', 'all']:
            with self.subTest(stage=stage):
                result = subprocess.run([sys.executable, str(Path(refresh.__file__)), stage,
                    '--baseline', str(self.base), '--release', str(self.release)],
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('require explicit --vault', result.stderr)
                self.assertEqual(self.fingerprints(), before)

    def test_nonexistent_vault_fails_before_any_write(self):
        before = self.fingerprints()
        with self.assertRaisesRegex(refresh.ComparisonInputError, 'incomplete'):
            refresh.Refresh(self.args(vault=str(self.vault)))
        self.assertEqual(self.fingerprints(), before)

    def test_partial_vault_missing_seed_record_is_rejected(self):
        self.fixture_vault()
        with self.assertRaisesRegex(refresh.ComparisonInputError, 'missing baseline seed record'):
            self.object().require_comparison_vault()

    def test_declared_missing_raw_is_rejected(self):
        self.fixture_vault({'resolved': {'blob_path': 'corpus/blobs/missing.gz'}})
        with self.assertRaisesRegex(refresh.ComparisonInputError, 'missing declared raw capture'):
            self.object().require_comparison_vault()

    def test_missing_comparison_body_cannot_silently_become_a_revision(self):
        self.fixture_vault({'resolved': {}})
        with self.assertRaisesRegex(refresh.ComparisonInputError, 'raw capture and derivative are unavailable'):
            self.object().old_derivative(self.unit)

    def test_existing_native_failed_capture_can_use_its_saved_derivative(self):
        self.fixture_vault({'resolved': {'http_status': 404}})
        (self.vault / 'texts').mkdir()
        (self.vault / 'texts/old.md').write_text('Retained baseline body')
        obj = self.object()
        obj.require_comparison_vault()
        self.assertIsNone(obj.old_derivative(self.unit))
        self.assertEqual(obj.old_text_path(self.unit).read_text(), 'Retained baseline body')

    def test_collect_and_review_do_not_require_historical_vault(self):
        for stage in ['collect', 'review']:
            with self.subTest(stage=stage), patch.object(refresh.Refresh, 'preserve'):
                obj = refresh.Refresh(self.args(stage=stage))
                self.assertIsNone(obj.vault)

    def test_missing_config_reuses_saved_entrypoint_snapshot_without_mutation(self):
        entries = [{'id': 'saved-source', 'url': 'https://example.org/feed', 'method': 'feed',
                    'publisher': 'Saved native snapshot', 'lane': 'main'}]
        (self.release / 'audits').mkdir()
        snapshot = self.release / 'audits/configured-sources.json'
        snapshot.write_text(json.dumps(entries))
        before = self.fingerprints()
        with patch.object(refresh, 'ROOT', self.root):
            self.assertEqual(self.object().configured(), entries)
        self.assertEqual(self.fingerprints(), before)

    def test_missing_or_empty_discovery_configuration_is_rejected(self):
        obj = self.object()
        with patch.object(refresh, 'ROOT', self.root):
            with self.assertRaisesRegex(refresh.ComparisonInputError, 'configuration is missing'):
                obj.configured()
            (self.root / 'config').mkdir()
            for name, data in [('sources.json', {'sources': []}),
                               ('person-expansion-sources.json', {'people': []}),
                               ('spoken-sources.json', {'official_surfaces': []})]:
                (self.root / 'config' / name).write_text(json.dumps(data))
            with self.assertRaisesRegex(refresh.ComparisonInputError, 'zero eligible entrypoints'):
                obj.configured()


if __name__ == '__main__':
    unittest.main(verbosity=2)
