#!/usr/bin/env python3
"""Verify the portable October evidence release, historical retention and lifecycle."""
from __future__ import annotations
import gzip
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/amind/scripts'))
import lifecycle
from verify_amind_increment import verify_claim

RELEASE=ROOT/'release/amind-v1-increment-2026-10-18'
BASE=ROOT/'release/amind-v1-increment-2026-09-08'


def require(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def jb(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(path):
    with (gzip.open if path.suffix=='.gz' else open)(path,'rt',encoding='utf-8') as h:
        return [json.loads(l) for l in h if l.strip()]


def verify():
    manifest=json.loads((RELEASE/'manifest.json').read_text())
    require(manifest['release_id']==RELEASE.name,'release identity mismatch')
    seen=set()
    for artifact in manifest['artifacts']:
        p=(RELEASE/artifact['path']).resolve()
        require(p.is_relative_to(RELEASE.resolve()) and not (RELEASE/artifact['path']).is_symlink(),'artifact path escape')
        require(artifact['path'] not in seen,'duplicate artifact');seen.add(artifact['path'])
        payload=p.read_bytes()
        require(len(payload)==artifact['bytes'] and sha(payload)==artifact['sha256'],f'artifact fingerprint mismatch: {artifact["path"]}')
    actual={p.relative_to(RELEASE).as_posix() for p in RELEASE.rglob('*') if p.is_file() and p!=RELEASE/'manifest.json'}
    require(seen==actual,'release contains unmanifested or missing artifacts')
    for relative,digest in json.loads((RELEASE/'audits/frozen-history.json').read_text()).items():
        require(relative.startswith(('release/amind-v1/','release/amind-v1-increment-2026-09-08/')),'invalid historical path')
        require(sha((ROOT/relative).read_bytes())==digest,f'historical artifact modified: {relative}')
    populations={};tables={}
    for name,key in [('analysis-units','analysis_unit_id'),('atomic-claims','claim_id'),('passages','passage_id'),
                     ('claim-attribution-audit','claim_id'),('theme-membership','claim_id')]:
        all_rows=rows(RELEASE/'data'/(name+'.jsonl.gz'));mapping={r[key]:r for r in all_rows}
        require(len(mapping)==len(all_rows),f'duplicate {name} IDs')
        old=rows(BASE/'data'/(name+'.jsonl.gz'));added=rows(RELEASE/'delta'/(name+'.jsonl.gz'))
        require(len(all_rows)==len(old)+len(added),f'population mismatch: {name}')
        require(all(mapping.get(r[key])==r for r in old),f'old rows rewritten: {name}')
        require(all(mapping.get(r[key])==r for r in added),f'delta mismatch: {name}')
        tables[name]=mapping;populations[name]=len(all_rows)
    units=tables['analysis-units'];passages=tables['passages'];claims=tables['atomic-claims']
    require(set(claims)==set(tables['claim-attribution-audit'])==set(tables['theme-membership']),'claim crosswalk mismatch')
    for review in rows(RELEASE/'delta/context-reviews.jsonl'):
        require(review['claim_id'] in claims,'context review claim missing')
        e=claims[review['claim_id']]['evidence'][0]
        require(review['passage_id']==e['passage_id'] and review['exact_quote_sha256']==e['exact_quote_sha256'],'context review binding drift')
        require(review.get('human_reviewed') is False and review.get('human_gold_promotion') is False,'AI review incorrectly promoted to human Gold')
    added_claims=rows(RELEASE/'delta/atomic-claims.jsonl.gz')
    for claim in added_claims:
        verify_claim(claim,units,passages)
        cid=claim['claim_id']
        require(tables['claim-attribution-audit'][cid]['claim_row_sha256']==sha(jb(claim)),f'audit drift: {cid}')
        require(tables['theme-membership'][cid]['claim_row_sha256']==sha(jb(claim)),f'membership drift: {cid}')
        require(claim['provenance'].get('review_state')=='machine_checked','new claim promoted to human gold')
    new_passages=rows(RELEASE/'delta/passages.jsonl.gz')
    for p in new_passages:
        require(sha(p['text'].encode())==p['text_sha256'],f'passage fingerprint: {p["passage_id"]}')
        require(p['source_char_end']-p['source_char_start']==len(p['text']),'passage range mismatch')
    claim_counts=Counter(c['evidence'][0]['passage_id'] for c in added_claims)
    processing=rows(RELEASE/'delta/passage-processing.jsonl')
    require(len(processing)==len({p['passage_id'] for p in processing}) and {p['passage_id'] for p in new_passages}=={p['passage_id'] for p in processing},'passage processing coverage')
    for p in processing:
        require(p['claims']==claim_counts[p['passage_id']],'passage processing claim count')
        require(p['claims'] or p.get('claimless_reason'),'missing claimless reason')
    raw_digests=set();checked_raw=set();records={}
    for record_path in (RELEASE/'sources/records').glob('*.json'):
        record=json.loads(record_path.read_text())
        if not record.get('ok'):continue
        require(record['record_id'] not in records,'duplicate source record ID')
        records[record['record_id']]=record
        raw_path=(RELEASE/record['raw_path']).resolve()
        require(raw_path.is_relative_to((RELEASE/'sources/raw').resolve()),'raw source path escape')
        raw_digests.add(record['raw_sha256'])
        if raw_path in checked_raw:continue
        digest=hashlib.sha256()
        with gzip.open(raw_path,'rb') as h:
            for chunk in iter(lambda:h.read(1024*1024),b''):digest.update(chunk)
        require(digest.hexdigest()==record['raw_sha256'],f'raw capture hash: {record_path.name}')
        checked_raw.add(raw_path)
    new_units=rows(RELEASE/'delta/analysis-units.jsonl.gz')
    for unit in new_units:
        bound=[records[rid] for rid in unit['source_seed_record_ids'] if rid in records]
        require(len(bound)==1,'new unit source-record binding missing/ambiguous')
        record=bound[0];extracted=record['extracted']
        require(sha(jb(record))==unit['source_manifest_row_sha256'],'unit source-record fingerprint mismatch')
        require(unit['raw_sha256']==record['raw_sha256'] and unit['observed_at']==record['completed_at'],'unit raw/observation binding mismatch')
        require(unit['body_sha256']==extracted['body_sha256'] and unit['published_at']==extracted['published_at'],'unit body/publication binding mismatch')
        text_path=(ROOT/unit['text_path']).resolve()
        require(text_path.is_relative_to((RELEASE/'sources/texts').resolve()),'source text path escape')
        text=text_path.read_text(encoding='utf-8')
        require(sha(text.encode())==unit['text_file_sha256']==unit['body_sha256'],'source derivative hash mismatch')
        require(unit['raw_sha256'] in raw_digests,'source raw capture missing')
        pp=sorted((p for p in passages.values() if p['analysis_unit_id']==unit['analysis_unit_id']),key=lambda p:p['passage_sequence'])
        for p in pp:
            require(text[p['source_char_start']:p['source_char_end']]==p['text'],'passage derivative slice mismatch')
        require(sum(sum(not c.isspace() for c in p['text']) for p in pp)==sum(not c.isspace() for c in text),'source passage coverage mismatch')
    exclusions=rows(RELEASE/'delta/artifact-exclusions.jsonl')
    for claim in added_claims:
        e=claim['evidence'][0]
        require(not any(e['analysis_unit_id']==x['analysis_unit_id'] and e['source_char_start']<x['source_char_end'] and e['source_char_end']>x['source_char_start'] for x in exclusions),'claim overlaps excluded prompt/transcript artifact')
    artifact_units={u['analysis_unit_id'] for u in new_units if u['component_origin']=='source_artifact'}
    require(not artifact_units&{c['evidence'][0]['analysis_unit_id'] for c in added_claims},'system prompt extracted as beliefs')
    memberships=list(tables['theme-membership'].values())
    for theme in rows(RELEASE/'data/theme-catalog.jsonl'):
        matched=[m for m in memberships if theme['theme_id'] in m['theme_ids']]
        require(len(matched)==theme['matched_claim_count'],'theme claim coverage count')
        require(len({m['analysis_unit_id'] for m in matched})==theme['matched_analysis_unit_count'],'theme source coverage count')
        require(sum(m['synthesis_disposition']=='eligible_for_source_level_synthesis' for m in matched)==theme['direct_synthesis_claim_count'],'theme direct coverage count')
        require(theme['count_scope']==RELEASE.name,'stale theme coverage scope')
        require(set(theme.get('supplement_claim_ids',[]))<=set(claims),'theme supplement foreign key')
    for voice in rows(RELEASE/'data/voice-profiles.jsonl'):
        direct=[c for cid,c in claims.items() if c['voice']['name']==voice['name'] and tables['claim-attribution-audit'][cid]['synthesis_disposition']=='eligible_for_source_level_synthesis']
        require(len(direct)==voice['direct_claim_count'] and len({c['evidence'][0]['analysis_unit_id'] for c in direct})==voice['analysis_unit_count'],'voice coverage count')
    components=rows(RELEASE/'data/claim-equivalence-components.jsonl');component_members=set()
    for component in components:
        members=set(component['member_claim_ids'])
        require(members<=set(claims) and not members&component_members,'equivalence foreign key/overlap')
        require(component['representative_claim_id'] in members,'equivalence representative missing')
        component_members|=members
    status=rows(RELEASE/'data/current-status.jsonl');lifecycle.validate_records(status)
    for r in status:
        require(set(r.get('target_claim_ids',[]))<=set(claims),'status references unknown claim')
        require(set(r.get('target_analysis_unit_ids',[]))<=set(units),'status references unknown source')
        require(set(r.get('replacement_claim_ids',[]))<=set(claims),'status replacement claim missing')
        require(set(r.get('replacement_analysis_unit_ids',[]))<=set(units),'status replacement source missing')
    skill=ROOT/'skills/amind/data';sm=json.loads((skill/'manifest.json').read_text())
    require(sm['release_id']==manifest['release_id'],'skill release mismatch')
    require(sha((skill/'manifest.json').read_bytes())==manifest['skill_manifest_sha256'],'skill manifest fingerprint')
    for a in sm['artifacts']:
        require(sha((skill/a['path']).read_bytes())==a['sha256'],f'skill artifact: {a["path"]}')
    require((skill/'current-status.jsonl').read_bytes()==(RELEASE/'data/current-status.jsonl').read_bytes(),'lifecycle copy drift')
    require((RELEASE/'data/representative-evidence-review.jsonl').read_bytes()==(BASE/'data/representative-evidence-review.jsonl').read_bytes(),'gold release rewritten')
    conn=sqlite3.connect((skill/'amind-full-index.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        require(conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
        require({r[0] for r in conn.execute('SELECT claim_id FROM claims')}==set(claims),'index claims mismatch')
        require({r[0] for r in conn.execute('SELECT analysis_unit_id FROM sources')}==set(units),'index sources mismatch')
        require(conn.execute('SELECT count(*) FROM claims_fts').fetchone()[0]==len(claims),'FTS population')
        meta={k:json.loads(v) for k,v in conn.execute('SELECT key,value FROM metadata')}
        for relative,digest in meta['source_fingerprints'].items():
            require(sha((ROOT/relative).read_bytes())==digest,f'index source drift: {relative}')
    finally:conn.close()
    c=manifest['counts']
    require(c['analysis_units']==len(units) and c['atomic_claims']==len(claims) and c['passages']==len(passages),'manifest counts mismatch')
    return {'verdict':'PASS','release_id':manifest['release_id'],'counts':c,
            'historical_files_unchanged':len(json.loads((RELEASE/'audits/frozen-history.json').read_text())),
            'new_claims_quote_verified':len(added_claims),'lifecycle_decisions':len(status),'new_human_gold_rows':0}


if __name__=='__main__':
    try:
        import argparse
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--release',help='explicit dated release, including a frozen historical release')
        parser.add_argument('--base',help='explicit baseline; defaults to the selected release manifest')
        args=parser.parse_args()
        current=json.loads((ROOT/'skills/amind/data/manifest.json').read_text())
        if args.release or current['release_id']!=RELEASE.name:
            from verify_amind_snapshot import verify as verify_snapshot
            selected=(ROOT/args.release).resolve() if args.release else ROOT/'release'/current['release_id']
            selected_manifest=json.loads((selected/'manifest.json').read_text())
            baseline=(ROOT/args.base).resolve() if args.base else ROOT/'release'/selected_manifest['base_release_id']
            result=verify_snapshot(selected,baseline,require_current=not (args.release and current['release_id']!=selected.name))
        else:result=verify()
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,sqlite3.Error) as error:
        print(f'AMind refresh verification FAILED: {error}',file=sys.stderr);raise SystemExit(2)
