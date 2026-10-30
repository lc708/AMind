"""Current-answer contracts and append-only October release checks."""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import subprocess
import sqlite3
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/amind/scripts'))
import lifecycle
import query


class PackagePartialDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('amind_package_partial_date',ROOT/'scripts/package_amind_refresh.py')
        package=importlib.util.module_from_spec(spec)
        prior_paths=list(sys.path)
        sys.path.insert(0,str(ROOT/'scripts'))
        try:spec.loader.exec_module(package)
        finally:sys.path[:]=prior_paths
        cls.package=package

    def test_publication_windows_use_explicit_publication_month_not_an_arbitrary_pdf_date(self):
        package=self.package
        base={'analysis_unit_id':'month-unit','canonical':'https://example.org/article','published_at':'',
            'extraction':{'date_evidence':[{'kind':'visible_month_only; exact day unavailable','value':'September 2026'}]}}
        rules=package.publication_windows([base])
        self.assertEqual(len(rules),1)
        self.assertEqual(rules[0]['publication_month'],'2026-09')
        self.assertEqual(rules[0]['valid_from'],'2026-09-01')
        ambiguous=copy.deepcopy(base)
        ambiguous['extraction']['date_evidence'][0]['kind']='PDF cover month-only; exact day unavailable'
        self.assertEqual(package.publication_windows([ambiguous]),[])

    def test_month_windows_do_not_suppress_revision_retirement_or_backdate_later_editions(self):
        for month,observed,before,after in [
                ('August 2026','2026-10-17T18:30:00+00:00','2026-10-17','2026-10-18'),
                ('February 2024','2024-03-04T09:00:00+00:00','2024-03-03','2024-03-04')]:
            with self.subTest(month=month):
                old={'analysis_unit_id':'old-month','canonical':'https://example.org/edition','published_at':'',
                    'extraction':{'date_evidence':[{'kind':'visible_month_only; exact day unavailable','value':month}]}}
                # A revision can retain the work's original publication month.
                new={**old,'analysis_unit_id':'new-edition'}
                version={'prior_analysis_unit_id':'old-month','new_analysis_unit_id':'new-edition',
                    'observed_at':observed}
                original=copy.deepcopy([old,new])
                publication=self.package.publication_windows([old,new])
                rules=publication+self.package.revision_windows([old,new],[version],publication)
                lifecycle.validate_records(rules)
                retired=next(r for r in rules if r['kind']=='superseded')
                self.assertEqual(retired['valid_until'],after)
                self.assertEqual(len([r for r in rules if r['kind']=='publication_window']),2)
                old_row={'claim_id':'old','analysis_unit_id':'old-month','source_published_at':'','later_observed_revision':True}
                new_row={'claim_id':'new','analysis_unit_id':'new-edition','source_published_at':''}
                self.assertTrue(lifecycle.assess(old_row,rules,before,'2026-10-18')['eligible'])
                self.assertFalse(lifecycle.assess(new_row,rules,before,'2026-10-18')['eligible'])
                self.assertEqual(lifecycle.assess(old_row,rules,after,'2026-10-18')['reasons'],['superseded'])
                self.assertTrue(lifecycle.assess(new_row,rules,after,'2026-10-18')['eligible'])
                self.assertEqual([old,new],original)

    def test_only_an_existing_retirement_date_can_override_revision_retirement(self):
        units=[{'analysis_unit_id':'old','canonical':'https://example.org/policy'},
            {'analysis_unit_id':'new','canonical':'https://example.org/policy'}]
        version={'prior_analysis_unit_id':'old','new_analysis_unit_id':'new','observed_at':'2026-10-18T04:00:00+00:00'}
        start={'status_id':'start','target_analysis_unit_ids':['old'],'kind':'effective_window',
            'valid_from':'2026-08-01','source_canonical':'https://example.org/policy','reason':'Old edition start.'}
        derived=self.package.revision_windows(units,[version],[start])
        self.assertTrue(any(r['kind']=='superseded' and r['valid_until']=='2026-10-18' for r in derived))
        retirement={**start,'status_id':'scheduled-replacement','valid_until':'2026-11-12'}
        derived=self.package.revision_windows(units,[version],[retirement])
        self.assertFalse(any(r['kind']=='superseded' for r in derived))
        self.assertEqual(retirement['valid_until'],'2026-11-12')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old = {'claim_id':'old', 'analysis_unit_id':'old-unit', 'source_published_at':'2026-07-30'}
        self.rule = {'status_id':'incident-correction', 'target_claim_ids':['old'], 'kind':'corrected',
            'valid_until':'2026-09-09', 'source_canonical':'https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents',
            'reason':'The later assessment explicitly corrects the preliminary explanation.', 'replacement_claim_ids':['new']}

    def test_explicit_correction_changes_eligibility_without_rewriting_history(self):
        original = copy.deepcopy(self.old)
        lifecycle.validate_records([self.rule])
        before = lifecycle.assess(self.old, [self.rule], '2026-09-08', '2026-10-18')
        after = lifecycle.assess(self.old, [self.rule], '2026-09-09', '2026-10-18')
        self.assertTrue(before['eligible'])
        self.assertFalse(after['eligible'])
        self.assertEqual(after['reasons'], ['corrected'])
        self.assertEqual(self.old, original)

    def test_future_policy_and_preceding_policy_have_exclusive_boundary(self):
        old = {**self.rule, 'status_id':'old-policy', 'kind':'effective_window', 'valid_until':'2026-11-12'}
        new = {**self.rule, 'status_id':'new-policy', 'target_claim_ids':['new'], 'kind':'effective_window',
               'valid_from':'2026-11-12', 'valid_until':''}
        row = {'claim_id':'new','source_published_at':'2026-10-08'}
        lifecycle.validate_records([old,new])
        for when, expected in [('2026-10-18',(True,False)), ('2026-11-12',(False,True))]:
            self.assertEqual(tuple(lifecycle.assess(r,[old,new],when,'2026-10-18')['eligible'] for r in [self.old,row]),expected)

    def test_publication_observation_and_effective_dates_remain_distinct(self):
        row={'claim_id':'x','source_published_at':'2026-10-15','source_observed_at':'2026-10-18'}
        self.assertFalse(lifecycle.assess(row,[],'2026-10-14','2026-10-18')['eligible'])
        self.assertTrue(lifecycle.assess(row,[],'2026-10-15','2026-10-18')['eligible'])
        month=lifecycle.assess({'source_published_at':'September 2026'},[],'2026-09-01','2026-10-18')
        self.assertFalse(month['eligible'])
        self.assertEqual(month['publication_availability'],'uncertain')
        self.assertFalse(month['publication_day_known'])

    def test_month_only_publication_has_bounds_and_uncertainty_not_a_fabricated_day(self):
        # Independent date variants exercise a leap year and a different month.
        row={'claim_id':'monthly','source_published_at':'February 2024'}
        before=lifecycle.assess(row,[],'2024-01-31','2026-10-18')
        middle=lifecycle.assess(row,[],'2024-02-17','2026-10-18')
        after=lifecycle.assess(row,[],'2024-02-29','2026-10-18')
        self.assertEqual(before['reasons'],['not_yet_published'])
        self.assertEqual(middle['reasons'],['publication_day_unconfirmed'])
        self.assertEqual(middle['publication_availability'],'uncertain')
        self.assertEqual(middle['publication_earliest_possible'],'2024-02-01')
        self.assertEqual(middle['publication_latest_possible'],'2024-02-29')
        self.assertTrue(after['eligible']);self.assertFalse(after['publication_day_known'])

    def test_source_native_month_registry_preserves_an_unknown_exact_day(self):
        rule={'status_id':'month','kind':'publication_window','target_claim_ids':['x'],
            'valid_from':'2026-09-01','publication_month':'2026-09',
            'source_canonical':'https://example.org/source', 'reason':'Visible September 2026; exact day unavailable.'}
        lifecycle.validate_records([rule])
        row={'claim_id':'x','source_published_at':''}
        self.assertEqual(lifecycle.assess(row,[rule],'2026-08-31','2026-10-18')['reasons'],['not_yet_published'])
        self.assertEqual(lifecycle.assess(row,[rule],'2026-09-17','2026-10-18')['publication_availability'],'uncertain')
        self.assertTrue(lifecycle.assess(row,[rule],'2026-10-01','2026-10-18')['eligible'])
        superseded=lifecycle.assess({**row,'later_observed_revision':True},[rule],'2026-10-01','2026-10-18')
        self.assertFalse(superseded['eligible'])
        self.assertIn('later_observed_revision',superseded['reasons'])
        for change in [{'valid_from':'2026-09-02'},{'publication_month':'September 2026junk'},{'valid_until':'2026-10-01'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                lifecycle.validate_records([{**rule,**change}])

    def test_future_as_of_needs_current_verification(self):
        result=lifecycle.assess(self.old,[],'2026-11-12','2026-10-18')
        self.assertTrue(result['verification_required'])
        self.assertIn('not a live',result['scope'])

    def test_decisions_must_have_precise_dates_explicit_targets_and_sources(self):
        for change in [{'valid_until':'September 2026'},{'target_claim_ids':[]},{'kind':'invented'},
                       {'source_canonical':''},{'valid_from':'2026-09-10'},{'target_claim_ids':'old'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                lifecycle.validate_records([{**self.rule,**change}])
        with self.assertRaises(ValueError):lifecycle.validate_records([self.rule,self.rule])

    def test_lifecycle_file_is_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);payload=(json.dumps(self.rule)+'\n').encode();(root/'current-status.jsonl').write_bytes(payload)
            artifact={'path':'current-status.jsonl','rows':1,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
            self.assertEqual(len(lifecycle.load_records(root,{'artifacts':[artifact]})),1)
            (root/'current-status.jsonl').write_bytes(payload+b' ')
            with self.assertRaises(ValueError):lifecycle.load_records(root,{'artifacts':[artifact]})

    def test_invalid_as_of_is_rejected(self):
        for value in ['2026-02-30','2026-1-01','2026-10-18junk','yesterday']:
            with self.subTest(value=value),self.assertRaises(ValueError):lifecycle.as_of_date({},value)


class PackagedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=ROOT/'skills/amind/data'
        cls.manifest=json.loads((cls.data/'manifest.json').read_text())
        if cls.manifest['release_id'] not in {'amind-v1-increment-2026-10-18','amind-v1-increment-2026-10-30'}:
            raise RuntimeError('Package a supported October release before running integration regressions')
        cls.status=lifecycle.load_records(cls.data,cls.manifest)
        cls.db=sqlite3.connect((cls.data/'amind-full-index.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
        cls.db.row_factory=sqlite3.Row

    @classmethod
    def tearDownClass(cls):cls.db.close()

    def row(self,cid):
        row=self.db.execute(query.INDEX_SELECT+' WHERE c.claim_id=?',(cid,)).fetchone()
        self.assertIsNotNone(row)
        return query.enriched_row(row,{})

    def unit_row(self,uid):
        cid=self.db.execute('SELECT c.claim_id FROM claims c JOIN sources s ON c.source_id=s.id WHERE s.analysis_unit_id=? ORDER BY c.claim_id LIMIT 1',(uid,)).fetchone()
        self.assertIsNotNone(cid)
        return self.row(cid[0])

    def eligible(self,row,when):return lifecycle.assess(row,self.status,when,'2026-10-18')['eligible']

    def test_three_retracted_explanations_are_retained_but_not_current(self):
        for cid in ['nuwa1-claim-12f017683b9189dab10ff751','nuwa1-claim-40316aceaf939ff7ba539884','nuwa1-claim-67bbb8e0fa91c37a9a5ea1f8']:
            with self.subTest(cid=cid):
                row=self.row(cid)
                self.assertTrue(self.eligible(row,'2026-09-08'))
                self.assertFalse(self.eligible(row,'2026-09-09'))

    def test_policy_editions_switch_on_effective_date(self):
        rules=[r for r in self.status if r['source_canonical'].endswith(('/legal/aup','/legal/supported-regions')) and r.get('valid_from')=='2026-11-12']
        self.assertGreaterEqual(len(rules),2)
        self.assertEqual({r['source_canonical'].rstrip('/').rsplit('/',1)[-1] for r in rules},{'aup','supported-regions'})
        for rule in rules:
            row=self.unit_row(rule['target_analysis_unit_ids'][0])
            self.assertFalse(self.eligible(row,'2026-10-18'))
            self.assertTrue(self.eligible(row,'2026-11-12'))
        old=next(r for r in self.status if '/legal/archive/' in r['source_canonical'] and r.get('valid_until')=='2026-11-12')
        row=self.unit_row(old['target_analysis_unit_ids'][0])
        self.assertTrue(self.eligible(row,'2026-11-11'));self.assertFalse(self.eligible(row,'2026-11-12'))

    def test_later_paragraph_corrections_do_not_leak_to_original_publication_day(self):
        for canonical,when,before in [('alignment-assessment-cybersecurity-incidents','2026-09-10','2026-09-09'),('an-update-on-independent-evaluators','2026-10-16','2026-10-15')]:
            rule=next(r for r in self.status if r['source_canonical'].endswith(canonical) and r.get('valid_from')==when and r.get('target_claim_ids'))
            self.assertGreaterEqual(len(rule['target_claim_ids']),2)
            for cid in rule['target_claim_ids']:
                self.assertFalse(self.eligible(self.row(cid),before));self.assertTrue(self.eligible(self.row(cid),when))

    def test_revised_edition_cannot_be_read_before_it_was_observed(self):
        rules=[r for r in self.status if r['status_id'].startswith('edition-start-')]
        self.assertGreaterEqual(len(rules),2)
        import datetime
        for rule in rules:
            row=self.unit_row(rule['target_analysis_unit_ids'][0])
            before=(datetime.date.fromisoformat(rule['valid_from'])-datetime.timedelta(days=1)).isoformat()
            self.assertFalse(self.eligible(row,before));self.assertTrue(self.eligible(row,rule['valid_from']))

    def test_archived_goals_are_historical_without_asserting_completion(self):
        # This regression targets the October 18 archive edition. A later
        # captured archive can legitimately supply newly public completion facts.
        archived=list(self.db.execute('SELECT c.claim_id FROM claims c JOIN sources s ON s.id=c.source_id WHERE s.analysis_unit_id=?',('nuwa1804-unit-6f5679660f417993f733',)))
        self.assertGreater(len(archived),10)
        for cid, in archived:self.assertFalse(self.eligible(self.row(cid),'2026-10-18'))

    def test_month_dated_personal_essay_is_not_available_before_its_month(self):
        row=self.row('nuwa1-claim-9033b7a9b509b9ee753871c8')
        before=lifecycle.assess(row,self.status,'2026-08-31','2026-10-18')
        middle=lifecycle.assess(row,self.status,'2026-09-17','2026-10-18')
        after=lifecycle.assess(row,self.status,'2026-10-01','2026-10-18')
        self.assertEqual(before['reasons'],['not_yet_published'])
        self.assertFalse(before['eligible']);self.assertFalse(middle['eligible'])
        self.assertEqual(middle['publication_availability'],'uncertain')
        self.assertTrue(after['eligible']);self.assertFalse(after['publication_day_known'])

    def test_model_reply_and_system_prompt_are_not_belief_claims(self):
        self.assertIsNone(self.db.execute('SELECT claim_id FROM claims WHERE claim_id=?',('nuwa1-claim-ab13f0863ff4b26a60412952',)).fetchone())
        found=self.db.execute('SELECT count(*) FROM claims c JOIN sources s ON s.id=c.source_id WHERE s.canonical LIKE ?',('%/system-prompts/%',)).fetchone()[0]
        self.assertEqual(found,0)

    def test_actual_cli_is_portable_and_current_results_are_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            command=[sys.executable,str(ROOT/'skills/amind/scripts/query.py')]
            result=subprocess.run(command+['search','alignment assessment cybersecurity incidents','--current','--limit','12','--json'],cwd=tmp,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            matches=[json.loads(line) for line in result.stdout.splitlines() if line.strip()];self.assertTrue(matches)
            self.assertTrue(all(r['current_status']['eligible'] for r in matches))
            result=subprocess.run(command+['show','nuwa1-claim-40316aceaf939ff7ba539884','--json'],cwd=tmp,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(json.loads(result.stdout)['current_status']['eligible'])


if __name__=='__main__':unittest.main(verbosity=2)
