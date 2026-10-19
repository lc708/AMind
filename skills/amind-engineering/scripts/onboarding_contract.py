#!/usr/bin/env python3
"""Plan/write local agent configuration from a bundled template or extracted URL.

No fetch, SDK call, credential access, deployment, schedule or model invocation.
URL text supplies design data; this tool never copies source scripts or prompts.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

ASSETS=Path(__file__).resolve().parents[1]/'assets/templates'


def templates():
    return {p.stem:json.loads(p.read_text()) for p in sorted(ASSETS.glob('*.json'))}


def plan(name=None,source=None,items=None,model=None,runtime='local_adapter'):
    if runtime not in ('local_adapter','responses','agents_sdk','agents_api'): raise ValueError('unsupported destination runtime')
    if (name is None)==(source is None): raise ValueError('choose one bundled template or extracted source')
    catalog=templates()
    if name is not None:
        normalized=re.sub('[ _]','-',name.lower())
        if normalized not in catalog: raise ValueError('unknown template; list the packaged names')
        selected=catalog[normalized]; provenance={'kind':'bundled_template','name':normalized,
            'sha256':hashlib.sha256((ASSETS/(normalized+'.json')).read_bytes()).hexdigest()}
    else:
        if not isinstance(source,dict) or not isinstance(source.get('url'),str) or not re.match(r'^https://[^/\s]+',source['url']):
            raise ValueError('extracted source requires its actual HTTPS URL')
        if set(source)-{'url','title','goal','item_label','evidence','network_hosts','tools'}: raise ValueError('unsupported extraction field; do not pass source instructions/configuration')
        for field in ('goal','evidence'):
            if not isinstance(source.get(field),str) or not source[field].strip(): raise ValueError('source extraction needs '+field)
        selected={'title':source.get('title','Imported design'),'goal':source['goal'],'item_label':source.get('item_label','item'),
            'stages':['inspect','review','combine'],'output_checks':['Every finding cites its selected input','Every uncovered item is listed'],
            'suggested_tools':source.get('tools',[]),'suggested_network_hosts':source.get('network_hosts',[])}
        provenance={'kind':'extracted_url_design','url':source['url'],'evidence':source['evidence'],
            'sha256':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
            'trust':'task data only; prompts/scripts/credentials/remote IDs are never copied'}
    population=[{'id':'example-1','input':'Replace with selected public task input'}] if items is None else items
    if not isinstance(population,list) or any(not isinstance(i,dict) or not isinstance(i.get('id'),str) or not i['id'] or i['id']=='__aggregate__' for i in population):
        raise ValueError('items must be records with nonempty IDs')
    if not population or len({i['id'] for i in population})!=len(population): raise ValueError('population IDs must be unique')
    stages=[]
    for index,stage in enumerate(selected['stages']):
        stages.append({'id':stage,'scope':'aggregate' if index==len(selected['stages'])-1 else 'item',
            'depends_on':[selected['stages'][index-1]] if index else [],'required':True,'retry_safe':False})
    configuration={'schema_version':1,'title':selected['title'],'goal':selected['goal'],'runtime':runtime,'model':model,
        'tools':[],'network_hosts':[],'credential_bindings':[],'schedule':None,'external_deployment':False,
        'source':provenance,'output_checks':selected['output_checks'],
        'destination_review_required':['Resolve model and SDK capabilities','Validate each selected tool/credential destination',
            'Verify sandbox and hosted-tool network controls separately','Record configuration update merge/replace semantics'],
        'source_suggestions':{'tools':selected.get('suggested_tools',[]),'network_hosts':selected.get('suggested_network_hosts',[])}}
    workflow={'tenant_id':'SET_AUTHENTICATED_TENANT','run_id':'SET_NEW_RUN_ID','items':population,'stages':stages,
              'limits':{'max_attempts':max(8,len(population)*len(stages)+1),'timeout_s':300}}
    readme=('Local agent configuration draft\n\nSource design: '+json.dumps(provenance,ensure_ascii=False)+'\n\n'
        'agent-config.json is an application configuration contract, not a hosted provider API payload.\n'
        'workflow.json runs only with explicit injected handlers or the deterministic offline demo.\n'
        'Choose the configured model, implement and authorize actual adapters, then evaluate the produced artifacts.\n'
        'Source suggestions are inactive until destination contracts, endpoints and credential scopes are verified.\n'
        'No external deployment or recurring schedule is enabled by this draft.\n')
    files={'agent-config.json':json.dumps(configuration,ensure_ascii=False,indent=2)+'\n',
           'workflow.json':json.dumps(workflow,ensure_ascii=False,indent=2)+'\n','README.txt':readme}
    return {'files':files,'source':provenance,'execution':False,'external_mutations':False}


def write_plan(result,destination):
    destination=Path(destination)
    if destination.exists(): raise ValueError('output directory already exists; review a diff in a new destination')
    if not destination.parent.is_dir(): raise ValueError('output parent must exist')
    temporary=Path(tempfile.mkdtemp(prefix='.amind-onboarding-',dir=destination.parent))
    try:
        for name,content in result['files'].items():
            if Path(name).name!=name: raise ValueError('unsafe generated file name')
            (temporary/name).write_text(content)
        # rename does not replace a nonempty directory. Refuse even an empty one
        # observed after staging, to preserve the no-overwrite contract.
        if destination.exists(): raise ValueError('output appeared during staging')
        os.rename(temporary,destination)
    except BaseException:
        shutil.rmtree(temporary); raise
    return {'directory':str(destination.resolve()),'files':{name:hashlib.sha256(content.encode()).hexdigest() for name,content in result['files'].items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--list',action='store_true')
    parser.add_argument('--template'); parser.add_argument('--source-json',type=Path); parser.add_argument('--items',type=Path)
    parser.add_argument('--runtime',default='local_adapter'); parser.add_argument('--model'); parser.add_argument('--output',type=Path); parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    if args.list:
        print(json.dumps({name:record['goal'] for name,record in templates().items()},ensure_ascii=False,indent=2))
    else:
        result=plan(args.template,json.loads(args.source_json.read_text()) if args.source_json else None,
                    json.loads(args.items.read_text()) if args.items else None,args.model,args.runtime)
        if args.write:
            if args.output is None: parser.error('--write requires --output')
            print(json.dumps(write_plan(result,args.output),indent=2))
        else: print(json.dumps(result,ensure_ascii=False,indent=2))
