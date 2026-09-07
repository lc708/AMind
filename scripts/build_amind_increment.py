#!/usr/bin/env python3
"""Offline construction of the one-off 2026-09-08 AMind increment.

Requires the local source-building workspace. The resulting release and skill
are self-contained; the frozen amind-v1 release is never rewritten.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / '.codex-tmp/amind-increment-deps'))
import run_amind_increment as run
import build_nuwa_v1_analysis_input as segmenter
import build_nuwa_v1_remaining_routine_specs as routine
import build_nuwa_v1_pilot_claims as binder
import build_nuwa_v1_claim_audit as auditor
import build_amind_skill_index as indexer

BATCH = run.BATCH
BASE = ROOT / 'release/amind-v1'
RELEASE_ID = 'amind-v1-increment-2026-09-08'
RELEASE = ROOT / 'release' / RELEASE_ID
DATA = RELEASE / 'data'
SKILL = ROOT / 'skills/amind'
DATE = run.BATCH_ID

# Reviewed native-Markdown diffs: these change assertions or an explicit name.
REVISIONS = {
    'am-1f8a05290f02': '2026-08-19 changelog: prompt-injection bug bounty and corrected Cowork comparisons',
    'am-04444957f494': 'Model Report date and Opus 5 capability/safeguard entries updated',
    'am-38625a1674b2': 'Same Transparency Hub model-report update via the root carrier',
    'am-1efab94d119f': '2026-08-26 Compliance API availability and surface coverage update',
    'am-7c06bf54140f': '2026-09-01 watermark detection API private-preview availability',
    'am-c36ea9655937': 'Student-data de-identification and privacy wording changed',
    'am-75e705627fc7': '2026-08-24 explicit Clio rename to Anthropic Insights',
    'am-ebf049d78b4b': 'Same explicit Clio rename via another carrier',
    'am-bd313e7fdc9f': 'Added the factual statement that Claude Tag is the CI/CD first responder',
}
EDITORIAL = {
    'am-529fc74cf913': 'Business/data terminology, heading clarifications, byline and cross-reference; core analytics assertions unchanged',
    'am-da1eeb928338': 'Byline and related-guide cross-reference only',
    'am-98513b0db9bd': 'Added report link and citation metadata; article assertions unchanged',
    'am-7352b7884b13': 'Advertisement marker only in the 2024 TIME interview',
    'am-951275a590bf': 'Question-heading Markdown formatting only',
    'am-fa695d5fd972': 'Title capitalization and related-content chrome only',
}
# Explicit same-work evidence, rather than title similarity or a global hash merge.
ALIASES = {
    'am-38625a1674b2': 'am-04444957f494',
    'am-ebf049d78b4b': 'am-75e705627fc7',
    'am-inc-c1d28f87c219': 'am-6995ebbe4cb8',
    'am-81485ad71116': 'am-1f8a05290f02',  # bytes equal the BASE edition, not its revision
}
TITLE_FIXES = {
    'am-7940727f2287': 'TASTE: Can AI Models Judge AI Safety Research Proposals?',
    'am-inc-b121cb5ff5d2': 'TASTE: Can AI Models Judge AI Safety Research Proposals? (paper)',
    'am-3e30bfe41fa1': 'Improving our alignment and security efforts',
}
AUTHOR_FIXES = {
    'am-7940727f2287': ['Hasan Baig', 'Hailey Joren', 'Joe Benton'],
    'am-inc-b121cb5ff5d2': ['Hasan Baig', 'Hailey Joren', 'Joe Benton'],
    'am-7ad561be51ff': ['Nicholas L. Turner', 'Jeffrey Wu', 'Joshua Batson'],
    'am-9b8561d9322b': ['Richard Qi', 'Benjamin Wright', 'Monte MacDiarmid', 'Evan Hubinger'],
    'am-d3b10c04e073': ['Jack Hopkins', 'Dipika Khullar', 'Rowan Wang', 'Fabien Roger'],
    'am-d95223dea117': ['Adam Karvonen', 'Euan Ong', 'Subhash Kantamneni', 'Samuel Marks'],
    'am-9f49e2c2ea79': ['Chen Yueh-Han', 'Jiaxin Wen', 'Jan Hendrik Kirchner'],
    'am-40944f4dff24': ['Ali Shazal', 'Matthew Koen'],
}
DATE_FIXES = {'am-7940727f2287': '2026-08-28', 'am-a65f210da18b': '2026-09-01',
              'am-d3b10c04e073': '2026-08-21', 'am-d95223dea117': '2026-08-21',
              'am-7ad561be51ff': '2026-08-21'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jb(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as h:
        return [json.loads(line) for line in h if line.strip()]


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value if isinstance(value, bytes) else jb(value)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(payload)
    temp.replace(path)


def put_rows(path, value):
    payload = b''.join(jb(row) for row in value)
    put(path, gzip.compress(payload, mtime=0) if str(path).endswith('.gz') else payload)


def sid(prefix, material, length=24):
    return prefix + sha(material.encode())[:length]


def canonical(record):
    return run.normalize(record.get('source', {}).get('url') or record['resolved']['requested_url'])


def trim_chrome(text):
    text = re.split(r'(?im)^#{1,3} Related (?:posts|content)\s*$', text)[0]
    return '\n'.join(line for line in text.splitlines() if not re.match(
        r'^(?:- (?:Author\(s\)|Reading time|Share Copy link)|Advertisement\s*$)', line)).strip()


def body_equal(left, right):
    return re.sub(r'\s+', ' ', trim_chrome(left)).strip() == re.sub(r'\s+', ' ', trim_chrome(right)).strip()


def raw_bytes(record):
    return gzip.decompress((ROOT / record['resolved']['blob_path']).read_bytes())


def derivative(record):
    """Preserve capture separately; fix PDF layout and mark transcript DOM blocks."""
    e = record['extracted']
    details = {'native_extractor': e['extractor'], 'native_body_sha256': e['body_sha256']}
    if record['resolved'].get('content_kind') == 'pdf':
        import pymupdf as fitz
        doc = fitz.open(stream=raw_bytes(record), filetype='pdf')
        pieces = []
        for i, page in enumerate(doc):
            blocks = []
            for block in page.get_text('blocks', sort=True):
                if block[6] == 0:
                    blocks.append(re.sub(r'\s+', ' ', block[4]).strip())
            pieces.append(f'## Page {i+1}\n\n' + '\n\n'.join(blocks))
        details.update({'derivative_extractor': 'pymupdf-blocks-1.28.2', 'pages': len(doc),
                        'normalization': 'join wrapped whitespace inside each PDF text block; retain page boundaries and every text block'})
        return '\n\n'.join(pieces), details
    text = trim_chrome(e['markdown'])
    if record['record_id'] == 'am-9b8561d9322b':
        from lxml import html
        import collect_pages
        doc = html.fromstring(raw_bytes(record))
        artifacts = doc.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " rs-xcode ")]')
        replaced = 0
        for node in artifacts:
            fragment = collect_pages.markdown_from_element(node)
            if fragment and fragment in text and not fragment.startswith('```'):
                text = text.replace(fragment, '```source-artifact\n' + fragment + '\n```')
                replaced += 1
        details['transcript_dom_blocks_marked'] = replaced
        details['transcript_dom_blocks_seen'] = len(artifacts)
    details['derivative_extractor'] = 'native-markdown-with-related-content-trim-v1'
    return text, details


def metadata(record):
    e = record['extracted']; rid = record['record_id']
    title = TITLE_FIXES.get(rid, e.get('title') or unquote(Path(urlsplit(canonical(record)).path).name))
    authors = AUTHOR_FIXES.get(rid, e.get('authors') or [])
    published = DATE_FIXES.get(rid, e.get('published_at') or '')
    date_basis = 'native source metadata' if e.get('published_at') else 'not stated'
    if rid in DATE_FIXES:
        date_basis = 'visible article byline or PDF cover, reviewed in this batch'
    if not published:
        match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d\d\b', e.get('markdown', '')[:2500])
        if match:
            from dateutil.parser import parse
            published = parse(match.group()).date().isoformat()
            date_basis = 'date printed at document beginning; not a sitemap modification time'
    return title, authors, published, date_basis


def prepare():
    run.preserve_baseline()
    base_units = rows(BASE / 'data/analysis-units.jsonl.gz')
    by_seed = {}
    by_url = {}
    for u in base_units:
        by_url[run.normalize(u['canonical'])] = u
        for rid in u['source_seed_record_ids']:
            by_seed[rid] = u
    records = {p.stem: read(p) for p in sorted((BATCH/'records').glob('*.json'))}
    decisions = []
    units = []; passages = []; versions = []
    for rid, r in records.items():
        old_path = ROOT / 'corpus/records' / (rid + '.json')
        old = read(old_path) if old_path.exists() else None
        e = r.get('extracted', {}); old_e = (old or {}).get('extracted', {})
        prior = by_seed.get(rid) or by_url.get(canonical(r))
        d = {'record_id': rid, 'url': canonical(r), 'title': e.get('title') or '',
             'capture_state': r.get('state'), 'observed_at': r.get('updated_at'),
             'raw_sha256': r.get('resolved', {}).get('raw_sha256'),
             'native_body_sha256': e.get('body_sha256'), 'prior_analysis_unit_id': (prior or {}).get('analysis_unit_id')}
        if not e.get('markdown'):
            d.update(disposition='unavailable', reason=r.get('resolved', {}).get('error') or 'metadata only; no source body')
        elif rid == 'am-7a0982543260':
            d.update(disposition='excluded_homonym', reason='CO2 transport/energy paper: Tom Brown is a different author, not the Anthropic core person')
        elif rid in ALIASES:
            target = ALIASES[rid]
            target_record = read(ROOT/'corpus/records'/(target+'.json')) if rid == 'am-81485ad71116' else records[target]
            assert e['body_sha256'] == target_record['extracted']['body_sha256'], f'alias content differs: {rid}'
            d.update(disposition='duplicate_carrier', equivalent_record_id=target,
                     equivalent_edition='baseline' if rid == 'am-81485ad71116' else 'observed',
                     reason='Explicit same work/carrier mapping confirmed with exact extracted body hash')
        elif rid == 'am-5f984c008f41' or canonical(r).endswith('/system-prompts/overview'):
            d.update(disposition='metadata_only', reason='Leadership attribution or system-prompt navigation index; retained as captured metadata')
        elif old and e.get('body_sha256') == old_e.get('body_sha256'):
            d.update(disposition='unchanged_body', reason='Re-fetched body hash identical to baseline')
        elif old and rid not in REVISIONS:
            diff = '\n'.join(difflib.unified_diff(old_e.get('markdown','').splitlines(), e['markdown'].splitlines(), n=2))
            put(BATCH/'diffs'/(rid+'.diff'), diff.encode())
            d.update(disposition='editorial_or_template_change', reason=EDITORIAL.get(rid,
                'Reviewed diff changes only related-content, byline or formatting; no new substantive source assertion'))
        else:
            kind = 'revised_work' if prior or rid in REVISIONS else 'new_work'
            if '/system-prompts/' in canonical(r):
                kind = 'source_artifact'  # all versions retained, no inferred publication after cutoff
            d.update(disposition=kind, reason=REVISIONS.get(rid, 'Newly captured qualifying written source; discovery date is not publication date'))
            text, extraction = derivative(r)
            title, authors, published, date_basis = metadata(r)
            work_id = prior['work_id'] if prior else sid('wrk-', canonical(r), 32)
            text_sha = sha(text.encode())
            edition_id = sid('edn-', work_id+'\0'+r['resolved']['raw_sha256'], 32)
            unit_id = sid('nuwa1804-unit-', work_id+'\0'+edition_id+'\0'+text_sha, 20)
            text_path = BATCH / 'analysis-texts' / (unit_id+'.md')
            put(text_path, text.encode())
            u = {'schema_name':'nuwa-v1-analysis-unit','schema_version':1,'analysis_unit_id':unit_id,
                 'work_id':work_id,'edition_id':edition_id,'title':title,'authors':authors,
                 'canonical':canonical(r),'published_at':published,'publication_date_basis':date_basis,
                 'observed_at':r['updated_at'],'modified_at':e.get('modified_at') or '',
                 'language':'en','unit_status':'body_primary','component_origin':kind,
                 'historical_role': {'status':'source_attribution_only; no inferred person role'},
                 'source_seed_record_ids':[rid]+[a for a,t in ALIASES.items() if t==rid and a!='am-81485ad71116'],
                 'source_manifest_row_sha256':sha(jb(r['source'])),
                 'body_sha256':text_sha,'text_file_sha256':text_sha,'text_path':str(text_path.relative_to(ROOT)),
                 'selection_reason':d['reason'],'raw_sha256':r['resolved']['raw_sha256'],
                 'extraction':extraction,'batch_id':DATE}
            # Publication and revision observation are deliberately separate.
            if prior or (old and rid in REVISIONS):
                versions.append({'work_id':work_id,'prior_analysis_unit_id':(prior or {}).get('analysis_unit_id'),
                                 'new_analysis_unit_id':unit_id,'prior_edition_id':prior['edition_id'] if prior else sid('edn-',work_id+'\0'+old['resolved']['raw_sha256'],32),
                                 'new_edition_id':edition_id,'observed_at':r['updated_at'],
                                 'prior_raw_sha256':old['resolved']['raw_sha256'] if old else None,
                                 'prior_body_analyzed_in_v1':prior is not None,
                                 'explicit_modified_at':'2026-08-19' if rid=='am-1f8a05290f02' else '',
                                 'relation':'later_observed_revision','basis':d['reason'],
                                 'historical_claims_retained':True})
            _, pp = segmenter.segment_text(text, unit_id, text_sha, 6000)
            for i, p in enumerate(pp):
                p.update({'schema_name':'nuwa-v1-passage','schema_version':1,'analysis_unit_id':unit_id,
                          'work_id':work_id,'edition_id':edition_id,'source_seed_record_ids':u['source_seed_record_ids'],
                          'source_text_path':u['text_path'],'source_text_file_sha256':text_sha,
                          'source_body_sha256':text_sha,'previous_passage_id':pp[i-1]['passage_id'] if i else '',
                          'next_passage_id':pp[i+1]['passage_id'] if i+1<len(pp) else ''})
            units.append(u); passages.extend(pp)
            d.update(title=title, analysis_unit_id=unit_id, work_id=work_id, edition_id=edition_id,
                     published_at=published, publication_date_basis=date_basis)
        decisions.append(d)
    for name, values in [('source-decisions',decisions),('analysis-units',units),('passages',passages),('version-relations',versions)]:
        put_rows(BATCH/(name+'.jsonl'), values)
    stats = {'source_dispositions':dict(collections.Counter(d['disposition'] for d in decisions)),
             'analysis_units':len(units),'passages':len(passages),'version_relations':len(versions)}
    put(BATCH/'preparation-audit.json', stats)
    print(json.dumps(stats, indent=2))


def excluded_ranges(text, unit):
    """Offsets in the complete derivative; exclusions remain available as context."""
    ranges = []
    opened = None
    for match in re.finditer(r'(?m)^\s*(?:```|~~~).*$', text):
        if opened is None:
            opened = match.start()
        else:
            ranges.append((opened,match.end(),'fenced code, prompt or transcript')); opened=None
    if opened is not None:
        ranges.append((opened,len(text),'continued fenced artifact'))
    rid=unit['source_seed_record_ids'][0]
    if unit['component_origin']=='source_artifact':
        ranges.append((0,len(text),'versioned system-prompt artifact, not author beliefs'))
    # Source section labels bound prompts/examples even where native HTML lacks fences.
    patterns = [r'(?im)^#{1,6}\s+.*(?:references|acknowledgements?|bibliography)\s*$']
    if rid=='am-9f49e2c2ea79':
        patterns += [r'(?im)^#{1,6}\s+.*(?:researcher briefing|monitor judge prompt|judge prompt|full prompts).*$']
    for pattern in patterns:
        for m in re.finditer(pattern,text):
            level=len(m.group().split()[0]); following=re.search(r'(?m)^#{1,'+str(level)+r'}\s+',text[m.end():])
            end=m.end()+following.start() if following else len(text)
            ranges.append((m.start(),end,'reference or explicitly labelled source-external section'))
    if 'jack-clark.net' in unit['canonical']:
        m=re.search(r'(?im)^(?:#{1,6}\s*)?(?:Tech Tales|Tech tales)',text)
        if m: ranges.append((m.start(),len(text),'Import AI fiction/Tech Tales tail'))
    if rid=='am-inc-b121cb5ff5d2':
        m=re.search(r'(?m)^## Page 51$',text)
        if m: ranges.append((m.start(),len(text),'TASTE Appendix G: source-native scaffold prompts'))
    return sorted(ranges)


def extract():
    run.preserve_baseline()
    units=rows(BATCH/'analysis-units.jsonl'); passages=rows(BATCH/'passages.jsonl')
    by_unit={u['analysis_unit_id']:u for u in units}; by_text=collections.defaultdict(list)
    for p in passages: by_text[p['analysis_unit_id']].append(p['text'])
    policy=read(ROOT/'config/nuwa-v1-remaining-routine-atomization-policy.json')
    policy['source_external_passage_sequence_ranges']=[]
    policy['source_external_section_terms'] += ['researcher briefing','monitor judge prompt','judge prompt']
    exclusions={u['analysis_unit_id']:excluded_ranges((ROOT/u['text_path']).read_text(),u) for u in units}
    seeds=[]; coverage=[]; used=collections.defaultdict(set); propositions=set()
    seed_by_id={}
    for p in passages:
        u=by_unit[p['analysis_unit_id']]; text=p['text']; count=0
        defaults=routine.voice_defaults(u)
        if urlsplit(u['canonical']).hostname in {'claude.com','platform.claude.com'}:
            defaults['organization']='Anthropic'
        # Case studies quote customers; a mechanical pass cannot assign each sentence reliably.
        reported = u['extraction'].get('pages') is not None or 'jack-clark.net' in u['canonical'] or ('claude.com/blog/' in u['canonical'] and any(
            marker in u['canonical'] for marker in ['how-abc-','how-monday-','how-warp-','how-slack-','bain-company-']))
        if reported:
            defaults['attribution_basis'] += ' This document includes evaluation artifacts, third-party work or customer testimony; the routine pass conservatively keeps its statements in reported scope pending individual passage-context review.'
        skip=routine.passage_skip_reason(p,policy)
        for a,b,reason in exclusions[u['analysis_unit_id']]:
            if a<=p['source_char_start'] and b>=p['source_char_end']: skip=reason
        if skip is None:
            for ss,se in routine.eligible_spans(text,policy):
                for start,end in routine.sentence_spans(text,ss,se):
                    for a,b in routine.split_long_span(text,start,end,320,280):
                        if any(p['source_char_start']+a<y and p['source_char_start']+b>x for x,y,_ in exclusions[u['analysis_unit_id']]): continue
                        quote=text[a:b]
                        if not routine.candidate_is_substantive(quote,policy): continue
                        quote=routine.unique_quote(by_text[u['analysis_unit_id']],text,a,b,320)
                        if not quote or len(quote)>320 or quote in used[u['analysis_unit_id']] or not routine.candidate_is_substantive(quote,policy): continue
                        actual=text.find(quote)
                        if any(p['source_char_start']+actual<y and p['source_char_start']+actual+len(quote)>x for x,y,_ in exclusions[u['analysis_unit_id']]): continue
                        used[u['analysis_unit_id']].add(quote)
                        fragment=a>start or b<end
                        prop=routine.normalize_proposition(text[a:b],defaults['voice_name'],defaults['voice_type'],clause_fragment=fragment)
                        if prop in propositions: prop=prop.rstrip('.')+f" (source unit {u['analysis_unit_id'][-6:]}, passage {p['passage_sequence']}, occurrence {count+1})."
                        assert prop not in propositions
                        propositions.add(prop)
                        kind,force=routine.classify(text[a:b]); conditions=[]
                        if fragment: conditions.append('One clause of a longer source sentence; inspect adjacent passage context.')
                        condition=routine.simulation_condition(text)
                        if condition: conditions.append(condition)
                        if u['source_seed_record_ids'][0]=='am-9b8561d9322b':
                            conditions.append('Controlled simulation and reward-hacking training experiment with an intentionally modified model; not evidence that deployed Claude has these objectives.')
                        if u['source_seed_record_ids'][0]=='am-9f49e2c2ea79':
                            conditions.append('Well-characterized alignment failures in bounded research environments; production-model generalization is not established by this result.')
                        if u['extraction'].get('pages'):
                            conditions.append('A reported statement or artifact in this PDF; do not attribute quoted model outputs or experimental prompts to the authors. Read the complete bound page context.')
                        seed={'seed_id':sid('inc-seed-',p['passage_id']+quote),'unit_id':u['analysis_unit_id'],
                              'proposition':prop,'quote':quote,'claim_type':kind,'epistemic_force':'quoted_position' if reported else force,
                              'domains':routine.domains_for(text[a:b],u['title']),'conditions':conditions,
                              'invalidation_conditions':[],**defaults}
                        seeds.append(seed); seed_by_id[seed['seed_id']]=seed; count+=1
        coverage.append({'passage_id':p['passage_id'],'analysis_unit_id':u['analysis_unit_id'],'claims':count,
                         'processing':'deterministic routine extraction; not human semantic review',
                         'claimless_reason':None if count else skip or 'No unique qualifying author-prose span after code, tables, quotation, reference and repeated-text filters'})
    claims,bindings=binder.extract_claim_records(seeds,units,passages,read(ROOT/'config/amind-v1-atomic-claim.schema.json'),DATE,
                     'incremental source-exact deterministic routine extraction with source-artifact exclusions','amind-increment-2026-09-08-1')
    audit_policy=read(ROOT/'config/nuwa-v1-claim-audit-policy.json')
    attribution=[auditor.claim_attribution(c,audit_policy) for c in claims]
    themes=read(ROOT/'config/nuwa-v1-synthesis-policy.json')['themes']
    memberships=[]
    for c,audit in zip(claims,attribution):
        ev=c['evidence'][0];u=by_unit[ev['analysis_unit_id']]
        searchable=' '.join([c['proposition'],' '.join(c['domains']),u['title']]).lower()
        hits={t['theme_id']:sorted({k for k in t['keywords'] if k.lower() in searchable}) for t in themes}
        hits={k:v for k,v in hits.items() if v}
        memberships.append({'schema_name':'nuwa-v1-theme-membership','schema_version':1,'claim_id':c['claim_id'],
            'claim_row_sha256':sha(jb(c)),'analysis_unit_id':u['analysis_unit_id'],'work_id':u['work_id'],
            'edition_id':u['edition_id'],'attribution_class':audit['attribution_class'],
            'synthesis_disposition':audit['synthesis_disposition'],'theme_ids':list(hits),'match_terms_by_theme':hits})
    for name,values in [('atomic-claims',claims),('claim-attribution-audit',attribution),('theme-membership',memberships),
                        ('passage-processing',coverage),('claim-bindings',bindings),('claim-seeds',seeds)]:
        put_rows(BATCH/(name+'.jsonl'),values)
    put_rows(BATCH/'artifact-exclusions.jsonl',[{'analysis_unit_id':uid,'source_char_start':a,'source_char_end':b,'reason':r}
                                              for uid,ranges in exclusions.items() for a,b,r in ranges])
    stats={'claims':len(claims),'passages':len(passages),'passages_with_claims':sum(bool(x['claims']) for x in coverage),
           'attribution':dict(collections.Counter(x['attribution_class'] for x in attribution)),
           'review_state':'machine_checked; no new human-reviewed gold evidence'}
    put(BATCH/'extraction-audit.json',stats); print(json.dumps(stats,indent=2))


# Individually read source passages / PDF pages. This is an AI context review,
# never a human-gold promotion. IDs bind immutable propositions and quotations.
CONTEXT_REVIEWS = {
    'nuwa1-claim-11b5c248c375720ccbd7e01f': ('asserted', 'Opus 5 system-card changelog, page 2, dated August 19, 2026; prompt-injection bounty results added.'),
    'nuwa1-claim-97e9e462ffe3dcdab315a7bd': ('asserted', 'Opus 5 changelog page 2: comparison harness mismatch; other models were rerun on the Opus 5 harness.'),
    'nuwa1-claim-5b350695da0f57d449a175ee': ('asserted', 'Opus 5 changelog page 2: only the Cowork evaluation drops thinking-disabled results; do not apply this to all evaluations.'),
    'nuwa1-claim-c07946b5b8c10fa0c037c2be': ('observed_result', 'System-card automated behavioral audit only; mixed metrics are not an overall judgment that capability implies better alignment.'),
    'nuwa1-claim-7d4e7ce4f1af1d8393daaec1': ('observed_result', 'Fable/Mythos 5.1 system card page 91; same bounded automated behavioral audit, not a general safety ranking.'),
    'nuwa1-claim-3104b0095bcf79c2b04a9eba': ('observed_result', 'System-prompt pressure to make known-false low-harm assertions; not a statement about all user interactions.'),
    'nuwa1-claim-26142aa4470bceda2a45b746': ('observed_result', 'Ten well-characterized alignment failures; held-out tests and larger target models, not demonstrated automation of all alignment research.'),
    'nuwa1-claim-0055c290658a8deaa21be3e0': ('observed_result', '28 researchers, at most eight hours, same benchmark task; not an unrestricted comparison with all human safety research.'),
    'nuwa1-claim-be8d186c11974572af9dade7': ('observed_result', 'TASTE standard setup and 92 proposal pairs; 77% is estimated human agreement with labels, not objective correctness. PDF figure 1 also visually checked.'),
    'nuwa1-claim-06f1995e29319dcf771700ae': ('observed_result', 'Out-of-distribution on-policy lie-detection cases; source reports a failure of generalization, not impossibility of lie detection.'),
    'nuwa1-claim-4e01ad5e2cc88d03e00d6e62': ('observed_result', 'CHIVE counterfactual prediction benchmark and three specified activation-reading tools; no universal claim that interpretability is useless.'),
    'nuwa1-claim-d1c20353d5f6055c05f58c6d': ('observed_result', 'Controlled simulation and deliberately reward-hacking-trained model. Absence of observed self-preservation or beyond-episode behavior is bounded to these evaluations.'),
}


def context_review():
    claims=rows(BATCH/'atomic-claims.jsonl'); by_id={c['claim_id']:c for c in claims}
    assert set(CONTEXT_REVIEWS)<=set(by_id), 'context review claim ID drift'
    reviews=[]
    for cid,(force,scope) in CONTEXT_REVIEWS.items():
        c=by_id[cid]
        c['epistemic_force']=force
        c['conditions']=[x for x in c['conditions'] if not x.startswith('A reported statement or artifact')]
        if scope not in c['conditions']: c['conditions'].append(scope)
        c['provenance']['extraction_method']='source-exact routine extraction followed by individual AI passage-context review'
        ev=c['evidence'][0]
        reviews.append({'claim_id':cid,'passage_id':ev['passage_id'],'exact_quote_sha256':ev['exact_quote_sha256'],
                        'reviewer_type':'AI assistant','human_reviewed':False,'review_state':'machine_checked',
                        'scope_note':scope,'human_gold_promotion':False})
    policy=read(ROOT/'config/nuwa-v1-claim-audit-policy.json')
    audits=[auditor.claim_attribution(c,policy) for c in claims]
    ab={a['claim_id']:a for a in audits}
    memberships=rows(BATCH/'theme-membership.jsonl')
    for m in memberships:
        c=by_id[m['claim_id']];a=ab[m['claim_id']]
        m.update(claim_row_sha256=sha(jb(c)),attribution_class=a['attribution_class'],synthesis_disposition=a['synthesis_disposition'])
    for name,data in [('atomic-claims',claims),('claim-attribution-audit',audits),('theme-membership',memberships),('context-reviews',reviews)]:
        put_rows(BATCH/(name+'.jsonl'),data)
    audit=read(BATCH/'extraction-audit.json')
    audit['individually_AI_context_reviewed_claims']=len(reviews)
    audit['attribution']=dict(collections.Counter(a['attribution_class'] for a in audits))
    put(BATCH/'extraction-audit.json',audit)


def equivalence_increment(base_claims, delta_claims):
    """Extend only same-work, same-voice, source-exact matches; retain v1 groups."""
    components=rows(BASE/'data/claim-equivalence-components.jsonl')
    parent={}; bases={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x: parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    for comp in components:
        for cid in comp['member_claim_ids']: union(comp['member_claim_ids'][0],cid)
    groups=collections.defaultdict(list)
    new_ids={c['claim_id'] for c in delta_claims}
    for c in base_claims+delta_claims:
        e=c['evidence'][0];v=c['voice']
        key=(e['work_id'],v['voice_type'],v['name'],v['organization'],e['exact_quote_sha256'])
        groups[key].append(c['claim_id'])
    for values in groups.values():
        if len(values)>1 and any(x in new_ids for x in values):
            for cid in values: union(values[0],cid)
    merged=collections.defaultdict(list)
    for cid in sorted(parent): merged[find(cid)].append(cid)
    old_by_members={tuple(c['member_claim_ids']):c for c in components}
    result=[]
    for members in merged.values():
        if len(members)<2: continue
        if tuple(members) in old_by_members: result.append(old_by_members[tuple(members)])
        else:
            result.append({'schema_name':'nuwa-v1-claim-equivalence-component','schema_version':1,
                'component_id':sid('inc-equivalence-', '\0'.join(members)),
                'representative_claim_id':members[0],'member_claim_ids':members,'member_count':len(members),
                'matching_bases':['frozen_v1_components_preserved','same_work_voice_and_exact_quote_for_incremental_edges'],
                'synthesis_rule':'retain_all_provenance_count_component_once_for_frequency'})
    return sorted(result,key=lambda c:c['component_id'])


def opposition_screen(base_claims, delta_claims):
    all_claims=base_claims+delta_claims
    tokens=[auditor.content_tokens(c['proposition']) for c in all_claims]
    frequencies=collections.Counter(t for ts in tokens for t in ts)
    inverted=collections.defaultdict(list)
    for i,ts in enumerate(tokens):
        for t in ts:
            if 2<=frequencies[t]<=250: inverted[t].append(i)
    polarity=[auditor.polarity(c['proposition']) for c in all_claims]
    result=[]
    for i in range(len(base_claims),len(all_claims)):
        counts=collections.Counter(j for t in tokens[i] if t in inverted for j in inverted[t] if j<i)
        for j,shared in counts.items():
            if shared<2: continue
            opposite=[d for d in polarity[i].keys() & polarity[j].keys() if polarity[i][d]!=polarity[j][d]]
            if not opposite: continue
            intersection=len(tokens[i]&tokens[j]);union=len(tokens[i]|tokens[j]);short=min(len(tokens[i]),len(tokens[j]))
            jac=intersection/union if union else 0; overlap=intersection/short if short else 0
            domains=set(all_claims[i]['domains'])&set(all_claims[j]['domains'])
            if (jac<.3 and overlap<.6) or (not domains and jac<.45):continue
            a,b=all_claims[j],all_claims[i]
            result.append({'claim_ids':[a['claim_id'],b['claim_id']],
                'analysis_unit_ids':[a['evidence'][0]['analysis_unit_id'],b['evidence'][0]['analysis_unit_id']],
                'screen':'lexical opposition; not a semantic contradiction finding',
                'shared_rare_tokens':shared,'jaccard':round(jac,6),'shorter_overlap':round(overlap,6),
                'opposed_dimensions':sorted(opposite),'disposition':'preserve_distinct_scopes_pending_individual_semantic_review'})
    return sorted(result,key=lambda r:r['claim_ids'])


def set_index_inputs():
    for name,filename in [('ANALYSIS_UNITS','analysis-units.jsonl.gz'),('ATOMIC_CLAIMS','atomic-claims.jsonl.gz'),
       ('ATTRIBUTION_AUDIT','claim-attribution-audit.jsonl.gz'),('EQUIVALENCE_COMPONENTS','claim-equivalence-components.jsonl'),
       ('PASSAGES','passages.jsonl.gz'),('SYNTHESIS_EVIDENCE','synthesis-evidence.jsonl'),('THEME_MEMBERSHIP','theme-membership.jsonl.gz')]:
        setattr(indexer,name,DATA/filename)
    indexer.INPUTS=(indexer.ANALYSIS_UNITS,indexer.ATOMIC_CLAIMS,indexer.ATTRIBUTION_AUDIT,indexer.EQUIVALENCE_COMPONENTS,
                    indexer.PASSAGES,indexer.SYNTHESIS_EVIDENCE,indexer.THEME_MEMBERSHIP)


def update_theme_counts():
    themes=rows(BASE/'data/theme-catalog.jsonl')
    claims={c['claim_id']:c for c in rows(BATCH/'atomic-claims.jsonl')}
    units={u['analysis_unit_id']:u for u in rows(BATCH/'analysis-units.jsonl')}
    memberships=rows(BATCH/'theme-membership.jsonl')
    for t in themes:
        mm=[m for m in memberships if t['theme_id'] in m['theme_ids']]
        direct=[m for m in mm if m['synthesis_disposition']=='eligible_for_source_level_synthesis']
        uids={m['analysis_unit_id'] for m in mm}
        t['matched_claim_count']+=len(mm);t['matched_analysis_unit_count']+=len(uids)
        t['direct_synthesis_claim_count']+=len(direct)
        for m in direct:
            voice=claims[m['claim_id']]['voice']['voice_type']
            t['direct_claims_by_voice_type'][voice]=t['direct_claims_by_voice_type'].get(voice,0)+1
        for uid in uids:
            match=re.search(r'\b(?:19|20)\d{2}\b',units[uid]['published_at'])
            year=int(match.group()) if match else None
            band='undated' if year is None else 'through_2018' if year<=2018 else '2019_2022' if year<=2022 else '2023_2024' if year<=2024 else '2025_2026'
            t['analysis_units_by_time_band'][band]=t['analysis_units_by_time_band'].get(band,0)+1
        t['count_scope']=RELEASE_ID
        t['thesis_and_representatives_scope']='frozen amind-v1; see incremental synthesis report for new qualified findings'
    put_rows(DATA/'theme-catalog.jsonl',themes)
    put_rows(SKILL/'data/theme-catalog.jsonl',themes)


def package():
    run.preserve_baseline(); context_review()
    populations={}
    base_claims=rows(BASE/'data/atomic-claims.jsonl.gz');new_claims=rows(BATCH/'atomic-claims.jsonl')
    for name,key in [('analysis-units','analysis_unit_id'),('atomic-claims','claim_id'),('passages','passage_id'),
                     ('claim-attribution-audit','claim_id'),('theme-membership','claim_id')]:
        baseline=rows(BASE/'data'/(name+'.jsonl.gz'));delta=rows(BATCH/(name+'.jsonl'))
        assert not ({r[key] for r in baseline}&{r[key] for r in delta}),f'ID collision: {name}'
        combined=sorted(baseline+delta,key=lambda r:r[key]); populations[name]=len(combined)
        put_rows(DATA/(name+'.jsonl.gz'),combined)
        put_rows(RELEASE/'delta'/(name+'.jsonl.gz'),delta)
    components=equivalence_increment(base_claims,new_claims)
    put_rows(DATA/'claim-equivalence-components.jsonl',components)
    opposition=opposition_screen(base_claims,new_claims)
    put_rows(RELEASE/'delta/contradiction-candidates.jsonl',opposition)
    for name in ['synthesis-evidence','representative-evidence-review','theme-catalog','voice-profiles','synthesis-tensions','version-audit']:
        put(DATA/(name+'.jsonl'),(BASE/'data'/(name+'.jsonl')).read_bytes())
    update_theme_counts()
    for name in ['source-decisions','version-relations','context-reviews','artifact-exclusions','passage-processing']:
        put(RELEASE/'delta'/(name+'.jsonl'),(BATCH/(name+'.jsonl')).read_bytes())
    for name in ['baseline.json','discovery-summary.json','preparation-audit.json','extraction-audit.json']:
        put(RELEASE/'audits'/name,(BATCH/name).read_bytes())
    counts={'analysis_units':populations['analysis-units'],'atomic_claims':populations['atomic-claims'],
            'passages':populations['passages'],'reviewed_kernel_claims':54,
            'equivalence_components':len(components),'new_claims':len(new_claims),
            'new_units':len(rows(BATCH/'analysis-units.jsonl')),'new_passages':len(rows(BATCH/'passages.jsonl')),
            'lexical_opposition_candidates':len(opposition)}
    set_index_inputs()
    temporary=SKILL/'data/amind-increment-building.sqlite3'
    if temporary.exists(): temporary.unlink()
    indexer.build_index_file(temporary,release_id=RELEASE_ID,expected=counts,version_relations=rows(BATCH/'version-relations.jsonl'))
    temporary.replace(SKILL/'data/amind-full-index.sqlite3')
    put(SKILL/'data/passages.jsonl.gz',(DATA/'passages.jsonl.gz').read_bytes())
    # Preserve the exact existing reviewed kernel and its adjustment provenance.
    manifest=read(SKILL/'data/manifest.json')
    manifest.update(release_id=RELEASE_ID,skill_version='1.2.1',base_release_id='amind-v1',
                    source_observation_cutoff=DATE,incremental_batch_id=DATE)
    for field,value in [('full_index_analysis_units',counts['analysis_units']),('full_index_atomic_claims',counts['atomic_claims']),
       ('full_index_passages',counts['passages']),('full_release_analysis_units',counts['analysis_units']),
       ('full_release_atomic_claims',counts['atomic_claims']),('full_index_equivalence_components',len(components))]:
        manifest['counts'][field]=value
    manifest['counts']['full_index_direct_claims']=sum(a['synthesis_disposition']=='eligible_for_source_level_synthesis'
                                                    for a in rows(DATA/'claim-attribution-audit.jsonl.gz'))
    for artifact in manifest['artifacts']:
        payload=(SKILL/'data'/artifact['path']).read_bytes()
        artifact.update(bytes=len(payload),sha256=sha(payload))
        if artifact['path']=='amind-full-index.sqlite3': artifact['rows']=counts['atomic_claims']
        if artifact['path']=='passages.jsonl.gz': artifact['rows']=counts['passages']
    manifest['sources']=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in sorted(DATA.iterdir()) if p.is_file()]
    manifest['incremental_boundary']={'raw_baseline_unchanged':True,'new_human_reviewed_gold_rows':0,
        'new_claims_review':'machine checked; selected passages additionally reviewed by AI',
        'complete_web_coverage_claimed':False,'recurring_update_configured':False,
        'report':str((RELEASE/'reports/update.zh-CN.md').relative_to(ROOT))}
    put(SKILL/'data/manifest.json',manifest)
    observations=[read(p) for p in (BATCH/'requests').glob('*.json')]
    release_manifest={'schema_name':'amind-increment-release','schema_version':1,'release_id':RELEASE_ID,
        'base_release_id':'amind-v1','source_observation_cutoff':DATE,'timezone':'Asia/Singapore',
        'observation_started_at':min(o['started_at'] for o in observations),
        'observation_finished_at':max(o['completed_at'] for o in observations),
        'counts':counts,'source_coverage':read(BATCH/'discovery-summary.json'),
        'review_boundary':manifest['incremental_boundary'],
        'skill_manifest_sha256':sha((SKILL/'data/manifest.json').read_bytes()),
        'artifacts':[{'path':str(p.relative_to(RELEASE)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
                     for folder in ['data','delta','audits','reports'] for p in sorted((RELEASE/folder).rglob('*')) if p.is_file()]}
    if (RELEASE/'README.md').is_file():
        payload=(RELEASE/'README.md').read_bytes()
        release_manifest['artifacts'].append({'path':'README.md','bytes':len(payload),'sha256':sha(payload)})
    put(RELEASE/'manifest.json',release_manifest)
    run.preserve_baseline()
    print(json.dumps(counts,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare','extract','package'])
    args=parser.parse_args()
    {'prepare':prepare,'extract':extract,'package':package}[args.stage]()


if __name__=='__main__':
    main()
