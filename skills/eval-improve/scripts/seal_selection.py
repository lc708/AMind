#!/usr/bin/env python3
"""Freeze one validation-selected treatment before running the final test split."""
import argparse
import json
import sys
from pathlib import Path
from kernel_common import compatible, sha, write_json, read_json


def portable_identity(identity):
    return {k:v for k,v in identity.items() if k not in ('split','reps','case_groups')}


def seal(flow,candidate,output,rationale):
    flow = Path(flow).resolve()
    output = Path(output).parent.resolve() / Path(output).name
    if not rationale.strip(): raise ValueError('selection rationale required')
    baseline,current=compatible(flow,candidate)
    if current['split']!='val': raise ValueError('select using validation, not the final test')
    if output.exists(): raise ValueError('selection certificate already exists; preserve it')
    certificate={'schema_version':2,'candidate':candidate,'validation_comparison_hash':current['comparison_hash'],
                 'contract_fingerprint':sha(portable_identity(current['comparison_identity'])),
                 'treatments':{'baseline':baseline['treatment_hash'],candidate:current['treatment_hash']},
                 'validation_results':{'baseline':baseline['results_sha256'],candidate:current['results_sha256']},
                 'rationale':rationale,'meaning':'Selection frozen; this is not evidence that the selected candidate improved'}
    certificate['certificate_hash']=sha(certificate)
    write_json(output.parent,output.name,certificate); return certificate


def verify(path,manifest):
    cert=read_json(path); body={k:v for k,v in cert.items() if k!='certificate_hash'}
    if cert.get('certificate_hash')!=sha(body): raise ValueError('selection certificate hash mismatch')
    if cert.get('contract_fingerprint')!=sha(portable_identity(manifest['comparison_identity'])):
        raise ValueError('final test contract changed after selection')
    if cert.get('treatments',{}).get(manifest['variant'])!=manifest['treatment_hash']:
        raise ValueError('final test target was not frozen in this selection')
    return cert['certificate_hash']


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--flow',required=True,type=Path); p.add_argument('--candidate',required=True)
    p.add_argument('--output',required=True,type=Path); p.add_argument('--rationale',required=True); a=p.parse_args()
    try: print(json.dumps(seal(a.flow,a.candidate,a.output,a.rationale),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
