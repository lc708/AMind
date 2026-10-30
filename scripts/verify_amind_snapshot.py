#!/usr/bin/env python3
"""Verify portable snapshot raw/source/claim/history bindings and its active skill.

The checks retain the October verifier's full raw capture, derivative, passage,
claim, audit, membership, lifecycle, Gold and SQLite checks. A historic release
can be verified without comparing it to a newer current skill's bytes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib
from package_amind_snapshot import ROOT, DEFAULT_RELEASE, DEFAULT_BASE, paths, historical_versions
from verify_amind_increment import verify_claim
sys.path.insert(0, str(ROOT/'skills/amind/scripts'))
import lifecycle

def require(ok,message):
    if not ok: raise ValueError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def jb(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(path):
    with (gzip.open if path.suffix=='.gz' else open)(path,'rt',encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]

def verify(release=DEFAULT_RELEASE, base=DEFAULT_BASE, *, require_current=True):
    release, base = paths(release, base)
    manifest=json.loads((release/'manifest.json').read_text())
    require(manifest['release_id']==release.name,'release identity mismatch')
    seen=set()
    for artifact in manifest['artifacts']:
        p=(release/artifact['path']).resolve()
        require(p.is_relative_to(release.resolve()) and not (release/artifact['path']).is_symlink(),'artifact path escape')
        require(p.relative_to(release).as_posix()==artifact['path'],'noncanonical artifact path')
        require(artifact['path'] not in seen,'duplicate artifact');seen.add(artifact['path'])
        payload=p.read_bytes()
        require(len(payload)==artifact['bytes'] and sha(payload)==artifact['sha256'],f'artifact fingerprint mismatch: {artifact["path"]}')
    actual={p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file() and p!=release/'manifest.json'}
    require(seen==actual,'release contains unmanifested or missing artifacts')
    for relative,digest in json.loads((release/'audits/frozen-history.json').read_text()).items():
        historical_file=(ROOT/relative).resolve()
        require(historical_file.is_relative_to((ROOT/'release').resolve()) and not historical_file.is_relative_to(release),'invalid historical path')
        require(sha((ROOT/relative).read_bytes())==digest,f'historical artifact modified: {relative}')
    frozen=json.loads((release/'audits/frozen-history.json').read_text())
    base_manifest=json.loads((base/'manifest.json').read_text())
    expected_history={str(p.relative_to(ROOT)) for p in [base/'manifest.json',*(base/a['path'] for a in base_manifest['artifacts'])]}
    require(expected_history<=set(frozen),'baseline historical inventory is incomplete')
    require(manifest['base_release_id']==base.name,'baseline identity mismatch')
    populations={};tables={}
    for name,key in [('analysis-units','analysis_unit_id'),('atomic-claims','claim_id'),('passages','passage_id'),
                     ('claim-attribution-audit','claim_id'),('theme-membership','claim_id')]:
        all_rows=rows(release/'data'/(name+'.jsonl.gz'));mapping={r[key]:r for r in all_rows}
        require(len(mapping)==len(all_rows),f'duplicate {name} IDs')
        old=rows(base/'data'/(name+'.jsonl.gz'));added=rows(release/'delta'/(name+'.jsonl.gz'))
        require(len(all_rows)==len(old)+len(added),f'population mismatch: {name}')
        require(all(mapping.get(r[key])==r for r in old),f'old rows rewritten: {name}')
        require(all(mapping.get(r[key])==r for r in added),f'delta mismatch: {name}')
        tables[name]=mapping;populations[name]=len(all_rows)
    units=tables['analysis-units'];passages=tables['passages'];claims=tables['atomic-claims']
    require(set(claims)==set(tables['claim-attribution-audit'])==set(tables['theme-membership']),'claim crosswalk mismatch')
    for review in rows(release/'delta/context-reviews.jsonl'):
        require(review['claim_id'] in claims,'context review claim missing')
        e=claims[review['claim_id']]['evidence'][0]
        require(review['passage_id']==e['passage_id'] and review['exact_quote_sha256']==e['exact_quote_sha256'],'context review binding drift')
        require(review.get('human_reviewed') is False and review.get('human_gold_promotion') is False,'AI review incorrectly promoted to human Gold')
    added_claims=rows(release/'delta/atomic-claims.jsonl.gz')
    for claim in added_claims:
        verify_claim(claim,units,passages)
        cid=claim['claim_id']
        require(tables['claim-attribution-audit'][cid]['claim_row_sha256']==sha(jb(claim)),f'audit drift: {cid}')
        require(tables['theme-membership'][cid]['claim_row_sha256']==sha(jb(claim)),f'membership drift: {cid}')
        require(claim['provenance'].get('review_state')=='machine_checked','new claim promoted to human gold')
    new_passages=rows(release/'delta/passages.jsonl.gz')
    for p in new_passages:
        require(sha(p['text'].encode())==p['text_sha256'],f'passage fingerprint: {p["passage_id"]}')
        require(p['source_char_end']-p['source_char_start']==len(p['text']),'passage range mismatch')
    claim_counts=Counter(c['evidence'][0]['passage_id'] for c in added_claims)
    processing=rows(release/'delta/passage-processing.jsonl')
    require(len(processing)==len({p['passage_id'] for p in processing}) and {p['passage_id'] for p in new_passages}=={p['passage_id'] for p in processing},'passage processing coverage')
    for p in processing:
        require(p['claims']==claim_counts[p['passage_id']],'passage processing claim count')
        require(p['claims'] or p.get('claimless_reason'),'missing claimless reason')
    raw_digests=set();checked_raw=set();records={}
    for record_path in (release/'sources/records').glob('*.json'):
        record=json.loads(record_path.read_text())
        if not record.get('ok'):continue
        require(record['record_id'] not in records,'duplicate source record ID')
        records[record['record_id']]=record
        raw_path=(release/record['raw_path']).resolve()
        require(raw_path.is_relative_to((release/'sources/raw').resolve()),'raw source path escape')
        raw_digests.add(record['raw_sha256'])
        if raw_path in checked_raw:continue
        digest=hashlib.sha256()
        with gzip.open(raw_path,'rb') as h:
            for chunk in iter(lambda:h.read(1024*1024),b''):digest.update(chunk)
        require(digest.hexdigest()==record['raw_sha256'],f'raw capture hash: {record_path.name}')
        checked_raw.add(raw_path)
    new_units=rows(release/'delta/analysis-units.jsonl.gz')
    for unit in new_units:
        bound=[records[rid] for rid in unit['source_seed_record_ids'] if rid in records]
        require(len(bound)==1,'new unit source-record binding missing/ambiguous')
        record=bound[0];extracted=record['extracted']
        require(sha(jb(record))==unit['source_manifest_row_sha256'],'unit source-record fingerprint mismatch')
        require(unit['raw_sha256']==record['raw_sha256'] and unit['observed_at']==record['completed_at'],'unit raw/observation binding mismatch')
        require(unit['body_sha256']==extracted['body_sha256'] and unit['published_at']==extracted['published_at'],'unit body/publication binding mismatch')
        text_path=(ROOT/unit['text_path']).resolve()
        require(text_path.is_relative_to((release/'sources/texts').resolve()),'source text path escape')
        text=text_path.read_text(encoding='utf-8')
        require(sha(text.encode())==unit['text_file_sha256']==unit['body_sha256'],'source derivative hash mismatch')
        require(unit['raw_sha256'] in raw_digests,'source raw capture missing')
        pp=sorted((p for p in passages.values() if p['analysis_unit_id']==unit['analysis_unit_id']),key=lambda p:p['passage_sequence'])
        for p in pp:
            require(text[p['source_char_start']:p['source_char_end']]==p['text'],'passage derivative slice mismatch')
        require(sum(sum(not c.isspace() for c in p['text']) for p in pp)==sum(not c.isspace() for c in text),'source passage coverage mismatch')
    exclusions=rows(release/'delta/artifact-exclusions.jsonl')
    for claim in added_claims:
        e=claim['evidence'][0]
        require(not any(e['analysis_unit_id']==x['analysis_unit_id'] and e['source_char_start']<x['source_char_end'] and e['source_char_end']>x['source_char_start'] for x in exclusions),'claim overlaps excluded prompt/transcript artifact')
    artifact_units={u['analysis_unit_id'] for u in new_units if u['component_origin']=='source_artifact'}
    require(not artifact_units&{c['evidence'][0]['analysis_unit_id'] for c in added_claims},'system prompt extracted as beliefs')
    memberships=list(tables['theme-membership'].values())
    for theme in rows(release/'data/theme-catalog.jsonl'):
        matched=[m for m in memberships if theme['theme_id'] in m['theme_ids']]
        require(len(matched)==theme['matched_claim_count'],'theme claim coverage count')
        require(len({m['analysis_unit_id'] for m in matched})==theme['matched_analysis_unit_count'],'theme source coverage count')
        require(sum(m['synthesis_disposition']=='eligible_for_source_level_synthesis' for m in matched)==theme['direct_synthesis_claim_count'],'theme direct coverage count')
        require(theme['count_scope']==release.name,'stale theme coverage scope')
        require(set(theme.get('supplement_claim_ids',[]))<=set(claims),'theme supplement foreign key')
    for voice in rows(release/'data/voice-profiles.jsonl'):
        direct=[c for cid,c in claims.items() if c['voice']['name']==voice['name'] and tables['claim-attribution-audit'][cid]['synthesis_disposition']=='eligible_for_source_level_synthesis']
        require(len(direct)==voice['direct_claim_count'] and len({c['evidence'][0]['analysis_unit_id'] for c in direct})==voice['analysis_unit_count'],'voice coverage count')
    components=rows(release/'data/claim-equivalence-components.jsonl');component_members=set()
    for component in components:
        members=set(component['member_claim_ids'])
        require(members<=set(claims) and not members&component_members,'equivalence foreign key/overlap')
        require(component['representative_claim_id'] in members,'equivalence representative missing')
        component_members|=members
    versions=historical_versions(base)+rows(release/'delta/version-relations.jsonl')
    later_by_unit={};prior_by_unit={}
    for version in versions:
        prior=version.get('prior_analysis_unit_id');new=version['new_analysis_unit_id']
        require(new in units and (not prior or prior in units),'version foreign key')
        require(version.get('eligibility_scope','unit') in {'unit','claim'},'unknown version eligibility scope')
        if prior:
            require(units[prior]['work_id']==units[new]['work_id'],'version work binding')
            if version.get('eligibility_scope','unit')=='unit':later_by_unit[prior]=new
        require(new not in prior_by_unit or prior_by_unit[new]==version,'conflicting version relation')
        prior_by_unit[new]=version
    status=rows(release/'data/current-status.jsonl');lifecycle.validate_records(status)
    preserved={r['status_id']:r for r in rows(base/'data/current-status.jsonl')} if (base/'data/current-status.jsonl').exists() else {}
    current={r['status_id']:r for r in status}
    require(all(current.get(key)==value for key,value in preserved.items()),'historical lifecycle decision rewritten')
    require(len(rows(release/'data/synthesis-evidence.jsonl'))==54,'gold evidence population changed')
    require((release/'data/synthesis-evidence.jsonl').read_bytes()==(base/'data/synthesis-evidence.jsonl').read_bytes(),'gold evidence rewritten')

    for r in status:
        require(set(r.get('target_claim_ids',[]))<=set(claims),'status references unknown claim')
        require(set(r.get('target_analysis_unit_ids',[]))<=set(units),'status references unknown source')
        require(set(r.get('replacement_claim_ids',[]))<=set(claims),'status replacement claim missing')
        require(set(r.get('replacement_analysis_unit_ids',[]))<=set(units),'status replacement source missing')
    skill=ROOT/'skills/amind/data';sm=json.loads((skill/'manifest.json').read_text())
    current_skill_checked=sm['release_id']==manifest['release_id']
    require(not require_current or current_skill_checked,'selected release is not the current packaged skill')
    if current_skill_checked:
        require(sha((skill/'manifest.json').read_bytes())==manifest['skill_manifest_sha256'],'skill manifest fingerprint')
        for a in sm['artifacts']:
            require(sha((skill/a['path']).read_bytes())==a['sha256'],f'skill artifact: {a["path"]}')
        require((skill/'current-status.jsonl').read_bytes()==(release/'data/current-status.jsonl').read_bytes(),'lifecycle copy drift')
        gold={r['claim_id']:r for r in rows(base/'data/synthesis-evidence.jsonl')}
        human={r['claim_id']:r for r in rows(base/'data/representative-evidence-review.jsonl')}
        kernel=rows(skill/'evidence-kernel.jsonl')
        require(len(kernel)==54 and {r['claim_id'] for r in kernel}==set(gold),'skill Gold population changed')
        fields=('analysis_unit_id','attribution_class','claim_id','claim_row_sha256','claim_type','edition_id',
                'epistemic_force','exact_quote','exact_quote_sha256','passage_id','proposition','source_canonical',
                'source_published_at','source_record_ids','source_title','theme_id','voice','work_id')
        for row in kernel:
            original=gold[row['claim_id']];review=human[row['claim_id']]
            require(all(row.get(key)==original.get(key) for key in fields),'skill Gold evidence rewritten')
            expected_review={'agenda_is_not_answer':review['agenda_is_not_answer'],'method':review['review_method'],
                'reviewed_at':review['reviewed_at'],'semantic_status':review['semantic_review_status'],'support_mode':review['support_mode']}
            require(row['review']==expected_review,'skill Gold human review rewritten')
        conn=sqlite3.connect((skill/'amind-full-index.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            require(conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
            require({r[0] for r in conn.execute('SELECT claim_id FROM claims')}==set(claims),'index claims mismatch')
            require({r[0] for r in conn.execute('SELECT analysis_unit_id FROM sources')}==set(units),'index sources mismatch')
            require(conn.execute('SELECT count(*) FROM claims_fts').fetchone()[0]==len(claims),'FTS population')
            for uid,payload in conn.execute('SELECT analysis_unit_id,payload_zlib FROM sources'):
                source=json.loads(zlib.decompress(payload))
                require(source.get('later_observed_revision')==later_by_unit.get(uid),'index revision eligibility drift')
                require(source.get('version_relation')==prior_by_unit.get(uid),'index version metadata drift')
            meta={k:json.loads(v) for k,v in conn.execute('SELECT key,value FROM metadata')}
            require(meta['release_id']==manifest['release_id'],'index release identity mismatch')
            expected_inputs={str((release/'data'/name).relative_to(ROOT)) for name in
                ['analysis-units.jsonl.gz','atomic-claims.jsonl.gz','claim-attribution-audit.jsonl.gz',
                 'claim-equivalence-components.jsonl','passages.jsonl.gz','synthesis-evidence.jsonl','theme-membership.jsonl.gz']}
            require(set(meta['source_fingerprints'])==expected_inputs,'index input fingerprint inventory mismatch')
            for relative,digest in meta['source_fingerprints'].items():
                require(sha((ROOT/relative).read_bytes())==digest,f'index source drift: {relative}')
        finally:conn.close()
    require((release/'data/representative-evidence-review.jsonl').read_bytes()==(base/'data/representative-evidence-review.jsonl').read_bytes(),'gold release rewritten')
    c=manifest['counts']
    require(c['analysis_units']==len(units) and c['atomic_claims']==len(claims) and c['passages']==len(passages),'manifest counts mismatch')
    return {'verdict':'PASS','release_id':manifest['release_id'],'counts':c,
            'historical_files_unchanged':len(json.loads((release/'audits/frozen-history.json').read_text())),
            'new_claims_quote_verified':len(added_claims),'lifecycle_decisions':len(status),'new_human_gold_rows':0,
            'current_skill_checked':current_skill_checked}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',help='explicit release; a noncurrent one is verified as frozen history')
    parser.add_argument('--base',help='baseline, inferred from an explicitly selected release when omitted')
    args=parser.parse_args()
    try:
        selected=(ROOT/(args.release or DEFAULT_RELEASE)).resolve()
        baseline=args.base or (json.loads((selected/'manifest.json').read_text())['base_release_id'] if args.release else DEFAULT_BASE)
        if not str(baseline).startswith('release/') and not Path(baseline).is_absolute():baseline='release/'+baseline
        current=json.loads((ROOT/'skills/amind/data/manifest.json').read_text())['release_id']
        result=verify(selected,baseline,require_current=not (args.release and current!=selected.name))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error) as error:
        print('AMind snapshot verification FAILED: '+str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
