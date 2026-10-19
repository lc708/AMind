#!/usr/bin/env python3
"""Interpret captured cache diagnostics; no requests and no billing estimates."""
import argparse
import copy
import json
from pathlib import Path


def analyze(response, expected_comparison_id=None):
    if not isinstance(response,dict): raise ValueError('response object required')
    diagnostics=response.get('prompt_cache_diagnostics')
    cached=(response.get('usage') or {}).get('input_tokens_details',{}).get('cached_tokens')
    if cached is not None and (type(cached) is not int or cached<0): raise ValueError('invalid reported cached token count')
    options=response.get('request_prompt_cache_options') or {}
    # Request options are trusted capture metadata, not a response API field.
    comparison=options.get('comparison_response_id')
    requested=expected_comparison_id or comparison
    if expected_comparison_id and comparison!=expected_comparison_id:
        status='inconclusive'; reason='comparison request not captured or identity mismatch'
    elif not isinstance(diagnostics,dict): status='not_measured'; reason='diagnostics absent'
    elif diagnostics.get('type') in ('cache_hit','cache_miss'):
        status='observed'; reason=diagnostics.get('reason') if diagnostics['type']=='cache_miss' else None
    else: status='inconclusive'; reason=(diagnostics or {}).get('type','unknown diagnostic type')
    return {'status':status,'comparison_response_id':requested,'diagnostic':copy.deepcopy(diagnostics),
        'reason':reason,'reported_cached_tokens':cached,'billing_cost_usd':None,
        'scope':'diagnostic comparison does not load history or guarantee actual cache reuse; usage owns reuse, invoice owns cost'}


def probe_coverage(observations,required_ids):
    """A 200/zero defects cannot pass when the intended object was not tested.

    Adapter-normalized facts are deliberately provider-neutral. Populate
    target_present/check_applied/same_scope from actual provider evidence.
    """
    if len(required_ids)!=len(set(required_ids)) or not required_ids: raise ValueError('unique required probe population needed')
    indexed={}
    for row in observations:
        key=row.get('id')
        if key not in required_ids or key in indexed: raise ValueError('unknown or duplicate observation')
        measured=all(row.get(k) is True for k in ('target_present','check_applied','same_scope'))
        if measured and type(row.get('violations')) is not int: raise ValueError('measured probe needs a violation count')
        if measured and row['violations']<0: raise ValueError('negative violation count')
        indexed[key]={'id':key,'status':('failed' if row['violations'] else 'passed') if measured else 'not_measured',
                      'evidence':row.get('evidence')}
    rows=[indexed.get(key,{'id':key,'status':'not_measured','evidence':None}) for key in required_ids]
    measured=sum(row['status']!='not_measured' for row in rows)
    return {'status':'failed' if any(row['status']=='failed' for row in rows) else ('passed' if measured==len(rows) else 'inconclusive'),
            'measured':measured,'required':len(rows),'coverage':measured/len(rows),'observations':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('capture',type=Path); p.add_argument('--comparison-id')
    a=p.parse_args(); print(json.dumps(analyze(json.loads(a.capture.read_text()),a.comparison_id),indent=2))
