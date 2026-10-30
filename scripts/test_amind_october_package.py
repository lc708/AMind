"""End-to-end contracts for the packaged October 30 evidence population."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/amind/scripts'))
import query
import lifecycle


class OctoberPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=ROOT/'skills/amind/data';cls.manifest=json.loads((cls.data/'manifest.json').read_text())
        if cls.manifest['release_id']!='amind-v1-increment-2026-10-30':raise RuntimeError('package October 30 before integration checks')
        cls.rules=lifecycle.load_records(cls.data,cls.manifest)
        cls.db=sqlite3.connect((cls.data/'amind-full-index.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        cls.db.row_factory=sqlite3.Row

    @classmethod
    def tearDownClass(cls):cls.db.close()

    def row(self,cid):
        native=self.db.execute(query.INDEX_SELECT+' WHERE c.claim_id=?',(cid,)).fetchone()
        self.assertIsNotNone(native);return query.enriched_row(native,{})

    def status(self,row,when='2026-10-30'):
        return lifecycle.assess(row,self.rules,when,self.manifest['source_observation_cutoff'])

    def test_all_baseline_claim_ids_survive_the_new_index(self):
        with gzip.open(ROOT/'release/amind-v1-increment-2026-10-18/data/atomic-claims.jsonl.gz','rt') as f:
            old={json.loads(line)['claim_id'] for line in f}
        now={r[0] for r in self.db.execute('SELECT claim_id FROM claims')}
        self.assertTrue(old<now);self.assertEqual(len(old),129132)

    def test_old_goals_switch_on_public_change_date_and_history_survives(self):
        for cid in ['nuwa1-claim-f1e6ef8a32dd331bf0cf9626','nuwa1-claim-d37254c0a75ef11ff7d4637d','nuwa1-claim-6264a7b897849b6ed7d2e299']:
            row=self.row(cid)
            self.assertTrue(self.status(row,'2026-10-18')['eligible'])
            self.assertFalse(self.status(row,'2026-10-19')['eligible'])
            self.assertFalse(self.status(row)['eligible'])

    def test_every_captured_future_policy_edition_stays_inactive_until_november(self):
        sources=self.db.execute("SELECT id,canonical FROM sources WHERE canonical LIKE '%/legal/aup' OR canonical LIKE '%/legal/supported-regions'").fetchall()
        self.assertGreaterEqual(len(sources),2)
        for source in sources:
            cid=self.db.execute('SELECT claim_id FROM claims WHERE source_id=? LIMIT 1',(source['id'],)).fetchone()[0]
            row=self.row(cid)
            with self.subTest(canonical=source['canonical'],source=source['id']):
                self.assertFalse(self.status(row)['eligible'])
                self.assertTrue(self.status(row,'2026-11-12')['eligible'])

    def test_jpp_observation_confirms_availability_without_a_publication_day(self):
        source=self.db.execute("SELECT id,published_at FROM sources WHERE canonical LIKE '%/2026/october-update/index.html'").fetchone()
        self.assertIsNotNone(source);self.assertEqual(source['published_at'],'')
        cid=self.db.execute('SELECT claim_id FROM claims WHERE source_id=? LIMIT 1',(source['id'],)).fetchone()[0]
        row=self.row(cid)
        self.assertFalse(self.status(row,'2026-10-29')['eligible'])
        current=self.status(row);self.assertTrue(current['eligible']);self.assertFalse(current['publication_day_known'])

    def test_runtime_manual_switches_on_observation_without_inventing_publication(self):
        for uid,old in [('nuwa1804-unit-dc96c908ea8562a576a9',True),('nuwa1804-unit-ef36093b5aee9b2a5518',False)]:
            source=self.db.execute('SELECT id,published_at FROM sources WHERE analysis_unit_id=?',(uid,)).fetchone()
            self.assertIsNotNone(source)
            cid=self.db.execute('SELECT claim_id FROM claims WHERE source_id=? LIMIT 1',(source['id'],)).fetchone()[0]
            row=self.row(cid)
            self.assertEqual(self.status(row,'2026-10-29')['eligible'],old)
            self.assertEqual(self.status(row)['eligible'],not old)
            if not old:self.assertEqual(source['published_at'],'')

    def test_every_reviewed_new_blog_and_research_source_is_indexed(self):
        needles=['/2026/graft','/2026/red-teaming-auto-mode','agents-judgment-calls','alignment-assessment-ukaisi',
            'attack-surface-reduction','formal-verification','discovering-vulnerabilities-with-claude',
            'claude-scorpion-toxin-binder-design','early-progress-drug-development','fold-subagents',
            'claude.dev/blog/building-effective-agent-automations','claude.dev/blog/solving-code-review-at-anthropic',
            'claude.dev/blog/claude-code-in-the-cloud','claude.dev/blog/getting-started-with-claude-code-mods',
            'claude.dev/blog/automating-eval-design-and-hillclimbing','import-ai-477','import-ai-478','public-benefit-report']
        for needle in needles:
            with self.subTest(source=needle):self.assertGreater(self.db.execute('SELECT count(*) FROM sources WHERE canonical LIKE ?',('%'+needle+'%',)).fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM sources WHERE canonical LIKE '%claude.dev/blog/%'").fetchone()[0],10)

    def test_reviewed_gold_bytes_remain_identical(self):
        self.assertEqual(hashlib.sha256((self.data/'evidence-kernel.jsonl').read_bytes()).hexdigest(),
            'a80170900edaa7a41c8583090ad87a14ee06cc95140b725ea6b47a5b32a40a3a')

    def test_newly_backfilled_fulfilled_report_plan_is_historical(self):
        audit=json.loads((ROOT/'release/amind-v1-increment-2026-10-30/curation/curation-audit.json').read_text())
        self.assertTrue(audit['fulfilled_new_source_plans_retired'])
        for cid in audit['fulfilled_new_source_plans_retired']:
            row=self.row(cid);self.assertTrue(self.status(row,'2026-10-18')['eligible'])
            self.assertFalse(self.status(row,'2026-10-21')['eligible'])


if __name__=='__main__':unittest.main()
