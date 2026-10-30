"""Snapshot packaging preserves old eligibility contracts and claim-level scope."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'skills/amind/scripts'))
import lifecycle
import package_amind_snapshot as package


class IndexRevisionScopeTests(unittest.TestCase):
    def build(self, root, scope):
        spec=importlib.util.spec_from_file_location('snapshot_fixture_indexer',ROOT/'scripts/build_amind_skill_index.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder);builder.ROOT=root
        units=[{'analysis_unit_id':name,'work_id':'work','edition_id':name,'title':'Fixture','canonical':'https://example.test/work','published_at':'2026-10-01'} for name in ('old','new')]
        claims=[{'claim_id':'c'+str(i),'proposition':'Fixture proposition '+str(i),'voice':{'name':'Fixture'},
                 'evidence':[{'analysis_unit_id':'new' if i==53 else 'old','passage_id':'p-new' if i==53 else 'p-old'}]} for i in range(54)]
        values={'ANALYSIS_UNITS':units,'ATOMIC_CLAIMS':claims,
                'ATTRIBUTION_AUDIT':[{'claim_id':c['claim_id'],'attribution_class':'direct_source_position','synthesis_disposition':'eligible_for_source_level_synthesis'} for c in claims],
                'EQUIVALENCE_COMPONENTS':[], 'PASSAGES':[{'passage_id':'p-old'},{'passage_id':'p-new'}],
                'SYNTHESIS_EVIDENCE':[{'claim_id':c['claim_id']} for c in claims],
                'THEME_MEMBERSHIP':[{'claim_id':c['claim_id'],'theme_ids':[]} for c in claims]}
        for attr,rows in values.items():
            file=root/(attr+'.jsonl');file.write_text(''.join(json.dumps(r)+'\n' for r in rows));setattr(builder,attr,file)
        builder.INPUTS=tuple(getattr(builder,a) for a in values)
        relation={'prior_analysis_unit_id':'old','new_analysis_unit_id':'new','observed_at':'2026-10-30'}
        if scope is not None:relation['eligibility_scope']=scope
        path=root/'index.sqlite3'
        builder.build_index_file(path,release_id='fixture-increment',expected={'analysis_units':2,'atomic_claims':54,'passages':2,'reviewed_kernel_claims':54},version_relations=[relation])
        conn=sqlite3.connect(path)
        try:return {uid:json.loads(zlib.decompress(payload)) for uid,payload in conn.execute('SELECT analysis_unit_id,payload_zlib FROM sources')}
        finally:conn.close()
    def test_default_and_explicit_unit_revision_keep_historical_behavior(self):
        for scope in (None,'unit'):
            with self.subTest(scope=scope),tempfile.TemporaryDirectory() as temp:
                sources=self.build(Path(temp),scope)
                self.assertEqual(sources['old']['later_observed_revision'],'new')
                self.assertFalse(lifecycle.assess({'analysis_unit_id':'old','later_observed_revision':'new'},[],'2026-10-30','2026-10-30')['eligible'])
    def test_claim_revision_keeps_unaffected_old_claims_eligible(self):
        with tempfile.TemporaryDirectory() as temp:
            sources=self.build(Path(temp),'claim')
            self.assertIsNone(sources['old']['later_observed_revision'])
            self.assertEqual(sources['new']['version_relation']['prior_analysis_unit_id'],'old')
            self.assertEqual(sources['new']['version_relation']['eligibility_scope'],'claim')
            rule={'status_id':'changed','kind':'superseded','target_claim_ids':['changed'],'valid_until':'2026-10-19',
                  'source_canonical':'https://example.test/work','reason':'Only the changed proposition is obsolete.'}
            changed={'claim_id':'changed','analysis_unit_id':'old','later_observed_revision':sources['old']['later_observed_revision']}
            stable={**changed,'claim_id':'unchanged'}
            self.assertFalse(lifecycle.assess(changed,[rule],'2026-10-30','2026-10-30')['eligible'])
            self.assertTrue(lifecycle.assess(stable,[rule],'2026-10-30','2026-10-30')['eligible'])
            self.assertTrue(lifecycle.assess(changed,[rule],'2026-10-18','2026-10-30')['eligible'])
    def test_unknown_revision_scope_fails_instead_of_changing_retrieval(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(RuntimeError,'scope'):
            self.build(Path(temp),'guessed')


class StatusPreservationTests(unittest.TestCase):
    def old(self):return {'status_id':'old','kind':'historical_only','target_claim_ids':['c'],
            'valid_until':'2026-10-18','source_canonical':'https://example.test/work','reason':'Frozen decision.'}
    def test_identical_baseline_status_is_deduplicated_and_new_status_added(self):
        old=self.old();new={**old,'status_id':'new','target_claim_ids':['d']}
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'data').mkdir();(base/'data/current-status.jsonl').write_text(json.dumps(old)+'\n')
            original=copy.deepcopy([old,new]);result=package.preserved_statuses(base,[old,new])
            self.assertEqual(result,[old,new]);self.assertEqual([old,new],original)
    def test_baseline_status_cannot_be_silently_replaced(self):
        old=self.old()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'data').mkdir();(base/'data/current-status.jsonl').write_text(json.dumps(old)+'\n')
            with self.assertRaisesRegex(ValueError,'rewritten'):package.preserved_statuses(base,[{**old,'valid_until':'2026-10-30'}])


class ReleaseWriterOwnershipTests(unittest.TestCase):
    def fixture(self, root):
        root = root.resolve()
        release = root / 'release/amind-v1-increment-2026-10-30'
        base = root / 'release/amind-v1-increment-2026-10-18'
        release.mkdir(parents=True); base.mkdir()
        marker = release / 'audits/refresh-run.json'; marker.parent.mkdir()
        expected = {'schema_name': 'amind-refresh-run', 'release_id': release.name,
                    'date': '2026-10-30', 'base_release_id': base.name}
        marker.write_text(json.dumps(expected))
        return release, base, marker, expected

    def test_only_matching_direct_dated_owned_release_is_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); release, base, marker, expected = self.fixture(root)
            before = marker.read_bytes()
            with patch.object(package, 'ROOT', root):
                package.require_owned_release(release, base, '2026-10-30')
                for date in ('2026-10-18', '2026-10-31'):
                    with self.subTest(date=date), self.assertRaises(ValueError):
                        package.require_owned_release(release, base, date)
                with self.assertRaises(ValueError): package.require_owned_release(release, root / 'release/different-base', '2026-10-30')
            self.assertEqual(marker.read_bytes(), before)

    def test_existing_historical_manifest_is_never_written_by_package_or_seal_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); release, base, marker, expected = self.fixture(root)
            historical = base / 'manifest.json'; historical.write_text('{"frozen":"exact bytes"}\n')
            original = historical.read_bytes()
            for seal_only in (False, True):
                with self.subTest(seal_only=seal_only), patch.object(package, 'ROOT', root), self.assertRaises(ValueError):
                    package.package(str(base), str(release), date='2026-10-18', seal_only=seal_only)
                self.assertEqual(historical.read_bytes(), original)

    def test_forged_nested_target_and_different_run_marker_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); release, base, marker, expected = self.fixture(root)
            nested = base / release.name; (nested / 'audits').mkdir(parents=True)
            (nested / 'audits/refresh-run.json').write_text(json.dumps(expected))
            with patch.object(package, 'ROOT', root):
                with self.assertRaises(ValueError): package.require_owned_release(nested, base, '2026-10-30')
                marker.write_text(json.dumps({**expected, 'date': '2026-10-29'}))
                with self.assertRaises(ValueError): package.require_owned_release(release, base, '2026-10-30')

    def test_symlinked_marker_or_marker_parent_cannot_authorize_writes(self):
        for link_parent in (False, True):
            with self.subTest(link_parent=link_parent), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); release, base, marker, expected = self.fixture(root)
                external = root / 'unrelated'; external.mkdir()
                stored = external / 'refresh-run.json'; stored.write_text(json.dumps(expected))
                marker.unlink()
                if link_parent:
                    marker.parent.rmdir(); marker.parent.symlink_to(external, target_is_directory=True)
                else: marker.symlink_to(stored)
                before = stored.read_bytes()
                with patch.object(package, 'ROOT', root), self.assertRaises(ValueError):
                    package.require_owned_release(release, base, '2026-10-30')
                self.assertEqual(stored.read_bytes(), before)

    def test_owned_release_rejects_a_symlinked_output_before_it_can_rewrite_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); release, base, marker, expected = self.fixture(root)
            original = base / 'theme-catalog.jsonl'; original.write_text('{"scope":"frozen"}\n')
            (release / 'data').mkdir()
            (release / 'data/theme-catalog.jsonl').symlink_to(original)
            before = original.read_bytes()
            with patch.object(package, 'ROOT', root), self.assertRaises(ValueError):
                package.require_owned_release(release, base, '2026-10-30')
            self.assertEqual(original.read_bytes(), before)


if __name__=='__main__':unittest.main()
