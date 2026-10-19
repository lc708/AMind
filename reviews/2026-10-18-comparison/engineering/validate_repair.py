#!/usr/bin/env python3
"""Post-discovery validation variants. They are not held-out quality evidence."""
import argparse
import importlib.util
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.root.resolve();rows=[]
versions={'frozen-old':root/'.codex-tmp/contrast-2026-10-18/old/skills/amind-engineering','frozen-new':root/'.codex-tmp/contrast-2026-10-18/new/skills/amind-engineering','repaired-new':root/'skills/amind-engineering'}
variants=[('conflict-root-outside','/root','/root/private',True,None),('conflict-root-inside','/root/private','/root',True,None),('consistent-root','/root','/root',False,'validation text'),('consistent-child','/root/private','/root/private',False,'')]
for version,skill in versions.items():
    spec=importlib.util.spec_from_file_location('validation_response',skill/'scripts/response_contract.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for ident,outer,inner,reject,display in variants:
        events=[{'type':'response.output_item.added','output_index':2,'agent':{'agent_name':outer},'item':{'type':'message','agent':{'agent_name':inner}}},{'type':'response.output_text.delta','output_index':2,'delta':'validation text'}]
        row={'version':version,'variant':ident,'evidence_level':'validation after discovery; not held out','input':events}
        try:row['result']=module.terminal_stream(events);row['passed']=not reject and row['result']['display_deltas']==display
        except ValueError as exc:row['error']=str(exc);row['passed']=reject
        rows.append(row)
a.output.write_text(json.dumps({'scope':'Post-discovery validation, two conflicting variants and two no-op consistency variants','results':rows,'summary':{v:{'passed':sum(r['passed'] for r in rows if r['version']==v),'total':sum(r['version']==v for r in rows)} for v in versions}},indent=2)+'\n');print(json.dumps({v:{'passed':sum(r['passed'] for r in rows if r['version']==v),'total':sum(r['version']==v for r in rows)} for v in versions}))
