#!/usr/bin/env python3
"""Verify the self-contained one-off AMind release, using the standard library."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RELEASE_ID='amind-v1-increment-2026-09-08'
RELEASE=ROOT/'release'/RELEASE_ID


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def jb(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def rows(path):
    with (gzip.open if path.suffix=='.gz' else open)(path,'rt',encoding='utf-8') as h:
        return [json.loads(line) for line in h if line.strip()]


def verify_claim(claim, units, passages):
    cid=claim['claim_id'];require(len(claim['evidence'])==1,f'evidence cardinality: {cid}')
    e=claim['evidence'][0];u=units[e['analysis_unit_id']];p=passages[e['passage_id']]
    q=e['exact_quote'];start=e['source_char_start']-p['source_char_start']
    require(0<len(q)<=320,f'quote length: {cid}')
    require(start>=0 and p['text'][start:start+len(q)]==q,f'quote offset/text mismatch: {cid}')
    require(e['source_char_end']==e['source_char_start']+len(q),f'quote end mismatch: {cid}')
    require(e['source_line_start']==p['source_line_start']+p['text'].count('\n',0,start),f'quote line mismatch: {cid}')
    require(e['exact_quote_sha256']==sha(q.encode()),f'quote hash: {cid}')
    require(e['work_id']==u['work_id']==p['work_id'] and e['edition_id']==u['edition_id']==p['edition_id'],f'version binding: {cid}')
    require(p['analysis_unit_id']==u['analysis_unit_id'],f'unit binding: {cid}')
    require(e['body_sha256']==u['body_sha256']==p['source_body_sha256'],f'body binding: {cid}')
    require(e['text_file_sha256']==u['text_file_sha256']==p['source_text_file_sha256'],f'text-file binding: {cid}')
    material=u['analysis_unit_id']+'\0'+claim['proposition']+'\0'+e['exact_quote_sha256']
    require(cid=='nuwa1-claim-'+sha(material.encode())[:24],f'stable claim identity: {cid}')
    require(claim['provenance']['review_state']=='machine_checked',f'increment cannot promote human review: {cid}')


def verify(release=RELEASE, *, local_vault=False):
    manifest=json.loads((release/'manifest.json').read_text())
    require(manifest['release_id']==RELEASE_ID,'invalid release identity')
    for a in manifest['artifacts']:
        p=(release/a['path']).resolve()
        require(p.is_relative_to(release.resolve()),'artifact path escape')
        payload=p.read_bytes()
        require(len(payload)==a['bytes'] and sha(payload)==a['sha256'],f'artifact fingerprint: {a["path"]}')
    baseline=json.loads((release/'audits/baseline.json').read_text())
    checked=0
    for relative,fp in baseline['fingerprints'].items():
        if relative.startswith('release/amind-v1/') or local_vault:
            require(sha((ROOT/relative).read_bytes())==fp['sha256'],f'frozen baseline changed: {relative}')
            checked+=1
    data=release/'data';delta=release/'delta';counts=manifest['counts']
    populations={};all_rows={}
    for name,key in [('analysis-units','analysis_unit_id'),('atomic-claims','claim_id'),('passages','passage_id'),
                     ('claim-attribution-audit','claim_id'),('theme-membership','claim_id')]:
        rr=rows(data/(name+'.jsonl.gz'));mapping={r[key]:r for r in rr}
        require(len(mapping)==len(rr),f'duplicate IDs: {name}')
        all_rows[name]=mapping;populations[name]=len(rr)
        original=rows(ROOT/'release/amind-v1/data'/(name+'.jsonl.gz'))
        require(all(mapping.get(r[key])==r for r in original),f'baseline row changed: {name}')
        added=rows(delta/(name+'.jsonl.gz'))
        require(len(rr)==len(original)+len(added),f'delta population: {name}')
        require(all(mapping.get(r[key])==r for r in added),f'delta content: {name}')
    require(populations['analysis-units']==counts['analysis_units'],'unit count')
    require(populations['atomic-claims']==counts['atomic_claims'],'claim count')
    require(populations['passages']==counts['passages'],'passage count')
    all_claim_ids=set(all_rows['atomic-claims'])
    require(set(all_rows['claim-attribution-audit'])==all_claim_ids==set(all_rows['theme-membership']),'claim/audit/theme crosswalk')
    units=all_rows['analysis-units'];passages=all_rows['passages']
    exclusions=rows(delta/'artifact-exclusions.jsonl');by_unit={}
    for e in exclusions: by_unit.setdefault(e['analysis_unit_id'],[]).append(e)
    new_claims=rows(delta/'atomic-claims.jsonl.gz')
    claim_counts={}
    for c in new_claims:
        verify_claim(c,units,passages)
        e=c['evidence'][0];a=all_rows['claim-attribution-audit'][c['claim_id']]
        require(a['claim_row_sha256']==sha(jb(c)),f'audit fingerprint: {c["claim_id"]}')
        require(all_rows['theme-membership'][c['claim_id']]['claim_row_sha256']==sha(jb(c)),f'theme fingerprint: {c["claim_id"]}')
        require(not any(e['source_char_start']<x['source_char_end'] and e['source_char_end']>x['source_char_start']
                       for x in by_unit.get(e['analysis_unit_id'],[])),f'claim inside excluded artifact: {c["claim_id"]}')
        claim_counts[e['passage_id']]=claim_counts.get(e['passage_id'],0)+1
    new_passages=rows(delta/'passages.jsonl.gz')
    for p in new_passages:
        require(sha(p['text'].encode())==p['text_sha256'],f'passage fingerprint: {p["passage_id"]}')
        require(p['source_char_end']-p['source_char_start']==len(p['text']),f'passage range: {p["passage_id"]}')
    processing=rows(delta/'passage-processing.jsonl')
    require({p['passage_id'] for p in new_passages}=={r['passage_id'] for r in processing},'missing passage processing decision')
    for p in processing:
        require(p['claims']==claim_counts.get(p['passage_id'],0),'passage claim count')
        require(p['claims'] or p['claimless_reason'],'missing claimless reason')
    components=rows(data/'claim-equivalence-components.jsonl');seen=set()
    for c in components:
        members=set(c['member_claim_ids'])
        require(members<=all_claim_ids and not members&seen,'equivalence foreign key or overlap')
        require(c['representative_claim_id'] in members and len(members)==c['member_count'],'equivalence representative/count')
        seen.update(members)
    memberships=list(all_rows['theme-membership'].values())
    for theme in rows(data/'theme-catalog.jsonl'):
        matched=[m for m in memberships if theme['theme_id'] in m['theme_ids']]
        require(len(matched)==theme['matched_claim_count'],'theme claim coverage count')
        require(len({m['analysis_unit_id'] for m in matched})==theme['matched_analysis_unit_count'],'theme source coverage count')
        require(sum(m['synthesis_disposition']=='eligible_for_source_level_synthesis' for m in matched)==theme['direct_synthesis_claim_count'],'theme direct coverage count')
    for v in rows(delta/'version-relations.jsonl'):
        require(v['new_analysis_unit_id'] in units,'new version foreign key')
        if v.get('prior_analysis_unit_id'):
            require(units[v['prior_analysis_unit_id']]['work_id']==units[v['new_analysis_unit_id']]['work_id'],'version work mismatch')
    for c in rows(delta/'contradiction-candidates.jsonl'):
        require(set(c['claim_ids'])<=all_claim_ids,'opposition foreign key')
    current_manifest=json.loads((ROOT/'skills/amind/data/manifest.json').read_text())
    current_skill_checked=current_manifest.get('release_id')==RELEASE_ID
    if current_skill_checked:
        skill=ROOT/'skills/amind/data';sm=json.loads((skill/'manifest.json').read_text())
        require(sha((skill/'manifest.json').read_bytes())==manifest['skill_manifest_sha256'],'skill manifest drift')
        require(sm['release_id']==manifest['release_id'],'skill release mismatch')
        for a in sm['artifacts']:
            require(sha((skill/a['path']).read_bytes())==a['sha256'],f'skill artifact drift: {a["path"]}')
        conn=sqlite3.connect((skill/'amind-full-index.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            meta={k:json.loads(v) for k,v in conn.execute('SELECT key,value FROM metadata')}
            require(conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
            require(meta['release_id']==RELEASE_ID,'index release')
            require({r[0] for r in conn.execute('SELECT claim_id FROM claims')}==all_claim_ids,'index claim set')
            require({r[0] for r in conn.execute('SELECT analysis_unit_id FROM sources')}==set(units),'index unit set')
            require(conn.execute('SELECT count(*) FROM claims_fts').fetchone()[0]==len(all_claim_ids),'FTS population')
            for relative,expected in meta['source_fingerprints'].items():
                require(sha((ROOT/relative).read_bytes())==expected,'index source fingerprint')
        finally:conn.close()
    if local_vault:
        for u in rows(delta/'analysis-units.jsonl.gz'):
            text=(ROOT/u['text_path']).read_text()
            require(sha(text.encode())==u['text_file_sha256'],'local derivative hash')
            pp=sorted((p for p in new_passages if p['analysis_unit_id']==u['analysis_unit_id']),key=lambda p:p['passage_sequence'])
            require(sum(sum(not ch.isspace() for ch in p['text']) for p in pp)==sum(not ch.isspace() for ch in text),'nonspace passage coverage')
    return {'verdict':'PASS','baseline_files_unchanged':checked,'new_claims_quote_verified':len(new_claims),
            'new_passages_processed':len(new_passages),'counts':counts,'new_human_gold_rows':0,
            'current_skill_checked':current_skill_checked}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--local-vault',action='store_true')
    p.add_argument('--historical',action='store_true',help='verify the frozen September increment independently of the current skill')
    args=p.parse_args()
    manifest=json.loads((ROOT/'skills/amind/data/manifest.json').read_text())
    if not args.historical and manifest.get('release_id') not in {'amind-v1', RELEASE_ID}:
        if manifest['release_id']=='amind-v1-increment-2026-10-18':
            from verify_amind_refresh import verify as verify_current
            result=verify_current()
        else:
            from verify_amind_snapshot import verify as verify_current
            current=ROOT/'release'/manifest['release_id']
            release_manifest=json.loads((current/'manifest.json').read_text())
            result=verify_current(current,ROOT/'release'/release_manifest['base_release_id'])
    else:
        result=verify(local_vault=args.local_vault)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,sqlite3.Error) as e:
        print(f'AMind increment verification FAILED: {e}',file=sys.stderr);raise SystemExit(2)
