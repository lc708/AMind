#!/usr/bin/env python3
"""Regression coverage for source bindings, version retrieval and frozen v1."""
import copy
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sqlite3
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'release/amind-v1-increment-2026-09-08'
QUERY=ROOT/'skills/amind/scripts/query.py'


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def read_rows(path):
    with (gzip.open if path.suffix=='.gz' else open)(path,'rt') as h:return [json.loads(l) for l in h if l.strip()]


class IncrementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier=module('verify_amind_increment')
        cls.units={r['analysis_unit_id']:r for r in read_rows(RELEASE/'delta/analysis-units.jsonl.gz')}
        cls.passages={r['passage_id']:r for r in read_rows(RELEASE/'delta/passages.jsonl.gz')}
        cls.claims=read_rows(RELEASE/'delta/atomic-claims.jsonl.gz')

    def query(self,*args):
        r=subprocess.run([sys.executable,str(QUERY),*args,'--json'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]

    def test_original_v1_index_retains_frozen_population_and_provenance(self):
        builder=module('build_amind_skill_index')
        payload,counts=builder.build_index_bytes()
        self.assertEqual(counts['atomic_claims'],52225)
        # SQLite file layout differs across runtime versions. Compare the frozen
        # input fingerprints and every claim ID, rather than cross-version bytes.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'v1.sqlite3';p.write_bytes(payload)
            conn=sqlite3.connect(p)
            meta={k:json.loads(v) for k,v in conn.execute('SELECT key,value FROM metadata')}
            expected={r['claim_id'] for r in read_rows(ROOT/'release/amind-v1/data/atomic-claims.jsonl.gz')}
            self.assertEqual({r[0] for r in conn.execute('SELECT claim_id FROM claims')},expected)
            self.assertEqual(meta['release_id'],'amind-v1')
            for relative,digest in meta['source_fingerprints'].items():
                self.assertEqual(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest(),digest)
            conn.close()

    def test_tampered_quote_and_offsets_are_rejected(self):
        original=self.claims[0]
        self.verifier.verify_claim(original,self.units,self.passages)
        for field,value in [('exact_quote','fabricated source quote'),('source_char_start',-1),('work_id','wrong-work')]:
            c=copy.deepcopy(original);c['evidence'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.verifier.verify_claim(c,self.units,self.passages)

    def test_increment_index_rebuild_is_identical_in_same_runtime(self):
        builder=module('build_amind_skill_index')
        for attr,name in [('ANALYSIS_UNITS','analysis-units.jsonl.gz'),('ATOMIC_CLAIMS','atomic-claims.jsonl.gz'),
          ('ATTRIBUTION_AUDIT','claim-attribution-audit.jsonl.gz'),('EQUIVALENCE_COMPONENTS','claim-equivalence-components.jsonl'),
          ('PASSAGES','passages.jsonl.gz'),('SYNTHESIS_EVIDENCE','synthesis-evidence.jsonl'),('THEME_MEMBERSHIP','theme-membership.jsonl.gz')]:
            setattr(builder,attr,RELEASE/'data'/name)
        builder.INPUTS=(builder.ANALYSIS_UNITS,builder.ATOMIC_CLAIMS,builder.ATTRIBUTION_AUDIT,builder.EQUIVALENCE_COMPONENTS,
                        builder.PASSAGES,builder.SYNTHESIS_EVIDENCE,builder.THEME_MEMBERSHIP)
        manifest=json.loads((RELEASE/'manifest.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp)/'first.sqlite3';second=Path(tmp)/'second.sqlite3'
            for p in (first,second):
                builder.build_index_file(p,release_id=manifest['release_id'],expected=manifest['counts'],
                                         version_relations=read_rows(RELEASE/'delta/version-relations.jsonl'))
            self.assertEqual(first.read_bytes(),second.read_bytes())
            # The checked-in binary may use a different SQLite/zlib version.
            # Compare all logical records, including decompressed evidence, too.
            fingerprints=[]
            for p in (first, (ROOT/'skills/amind/data/amind-full-index.sqlite3') if json.loads((ROOT/'skills/amind/data/manifest.json').read_text())['release_id']==manifest['release_id'] else second):
                conn=sqlite3.connect(p.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
                digest=hashlib.sha256()
                try:
                    for table,key in [('metadata','key'),('sources','id'),('voices','id'),('claims','id')]:
                        digest.update(table.encode())
                        for row in conn.execute(f'SELECT * FROM {table} ORDER BY {key}'):
                            logical=[json.loads(zlib.decompress(v)) if isinstance(v,bytes) else v for v in row]
                            digest.update((json.dumps(logical,sort_keys=True,separators=(',',':'))+'\n').encode())
                finally:conn.close()
                fingerprints.append(digest.hexdigest())
            self.assertEqual(*fingerprints)

    def test_system_prompt_artifacts_have_context_but_no_belief_claims(self):
        artifact_ids={u['analysis_unit_id'] for u in self.units.values() if u['component_origin']=='source_artifact'}
        self.assertEqual(len(artifact_ids),18)
        self.assertTrue(artifact_ids<={p['analysis_unit_id'] for p in self.passages.values()})
        self.assertFalse(artifact_ids & {c['evidence'][0]['analysis_unit_id'] for c in self.claims})

    def test_new_system_card_is_retrievable_with_bound_context(self):
        results=self.query('search','mythos 5.1 regression','--current','--limit','3')
        self.assertEqual(results[0]['claim_id'],'nuwa1-claim-c07946b5b8c10fa0c037c2be')
        self.assertEqual(results[0]['source_published_at'],'2026-09-01')
        self.assertFalse(results[0]['review']['human_reviewed'])
        shown=self.query('show',results[0]['claim_id'],'--passage')[0]
        self.assertIn(shown['exact_quote'],shown['passage']['text'])

    def test_current_retrieval_excludes_prior_edition_but_show_preserves_it(self):
        versions=read_rows(RELEASE/'delta/version-relations.jsonl')
        v=next(v for v in versions if v['prior_analysis_unit_id']=='nuwa1804-unit-2bb40970ae15ff116b1b')
        results=self.query('search','watermark','--current','--limit','50','--no-diversify')
        self.assertNotIn(v['prior_analysis_unit_id'],{r['analysis_unit_id'] for r in results})
        self.assertIn(v['new_analysis_unit_id'],{r['analysis_unit_id'] for r in results})
        old=self.query('show','nuwa1-claim-d162b0f6f39ecfe20178397f','--passage')[0]
        self.assertEqual(old['later_observed_revision'],v['new_analysis_unit_id'])
        self.assertIn(old['exact_quote'],old['passage']['text'])

    def test_simulation_is_explicitly_retrievable_without_losing_scope(self):
        results=self.query('search','reward seeker','--include-simulated','--limit','50','--no-diversify')
        simulated=[r for r in results if r['attribution_class']=='bounded_simulation_evidence']
        self.assertTrue(simulated)
        self.assertTrue(all(r['conditions'] for r in simulated))
        self.assertTrue(all(r['synthesis_disposition']=='preserve_with_simulation_scope' for r in simulated))

    def test_old_pdf_carrier_is_not_misclassified_as_new_revision(self):
        decisions={r['record_id']:r for r in read_rows(RELEASE/'delta/source-decisions.jsonl')}
        self.assertEqual(decisions['am-81485ad71116']['equivalent_edition'],'baseline')
        self.assertEqual(decisions['am-inc-c1d28f87c219']['disposition'],'duplicate_carrier')
        self.assertEqual(decisions['am-7a0982543260']['disposition'],'excluded_homonym')


if __name__=='__main__':unittest.main(verbosity=2)
