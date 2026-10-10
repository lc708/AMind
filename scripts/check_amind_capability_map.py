#!/usr/bin/env python3
"""Validate source coverage metadata and local resource links; not semantic parity."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def check(upstream=None):
    base=ROOT/'skills/amind-engineering/references'
    data=json.loads((base/'upstream-capabilities.json').read_text())
    entries=data['entries']; paths=[e['path'] for e in entries]
    if len(paths)!=len(set(paths)) or len(paths)!=data['source_file_count']: raise ValueError('source inventory mismatch')
    for entry in entries:
        if not entry['capability'] or not entry['evidence_level']: raise ValueError('missing capability/evidence classification')
        for ref in entry['resources']:
            if not (base/ref).is_file(): raise ValueError('missing resource: '+ref)
        if upstream:
            content=(upstream/entry['path']).read_bytes()
            if hashlib.sha256(content).hexdigest()!=entry['sha256']: raise ValueError('source hash mismatch: '+entry['path'])
    if upstream:
        actual={p.relative_to(upstream).as_posix() for p in upstream.rglob('*') if p.is_file()}
        if actual!=set(paths): raise ValueError('upstream has unindexed or missing files')
    return {'source_files':len(entries),'section_locators':sum(len(e['sections']) for e in entries),
            'source_hashes_verified':bool(upstream),'meaning':'inventory and resource checks only; semantic/behavioral evidence is separate'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--upstream',type=Path);a=p.parse_args()
    print(json.dumps(check(a.upstream),indent=2))
