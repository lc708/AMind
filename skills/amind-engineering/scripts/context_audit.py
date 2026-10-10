#!/usr/bin/env python3
"""Diagnose normalized Responses-style request/response traces without network calls."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def differences(expected,actual,path=''):
    """Return paths and hashes, not private prompt/reasoning contents."""
    if type(expected) is not type(actual): return [{'path':path or '/', 'change':'type', 'expected_hash':digest(expected),'actual_hash':digest(actual)}]
    if isinstance(expected,dict):
        found=[]
        for key in sorted(set(expected)|set(actual)):
            pointer=path+'/'+key.replace('~','~0').replace('/','~1')
            if key not in actual: found.append({'path':pointer,'change':'removed','expected_hash':digest(expected[key])})
            elif key not in expected: found.append({'path':pointer,'change':'added','actual_hash':digest(actual[key])})
            else: found.extend(differences(expected[key],actual[key],pointer))
        return found
    if isinstance(expected,list):
        found=[]
        for i in range(max(len(expected),len(actual))):
            pointer=path+'/'+str(i)
            if i>=len(actual): found.append({'path':pointer,'change':'removed','expected_hash':digest(expected[i])})
            elif i>=len(expected): found.append({'path':pointer,'change':'added','actual_hash':digest(actual[i])})
            else: found.extend(differences(expected[i],actual[i],pointer))
        return found
    return [] if expected==actual else [{'path':path or '/','change':'changed','expected_hash':digest(expected),'actual_hash':digest(actual)}]


def audit(turns):
    findings=[]; responses={}; calls={}; resolved=set(); prior=None
    def add(turn,code,detail,severity='error'): findings.append({'turn':turn,'code':code,'detail':detail,'severity':severity})
    for n,turn in enumerate(turns):
        if not isinstance(turn,dict): raise ValueError('each trace line is a normalized turn object')
        request=turn.get('request',{}); response=turn.get('response',{}); mode=turn.get('state_owner')
        if mode not in ('client','response_chain','conversation'): raise ValueError('state_owner must be client/response_chain/conversation')
        incoming=request.get('input',[])
        if not isinstance(incoming,list): raise ValueError('normalize input to an item array before diagnosis')
        output=response.get('output',[])
        if not isinstance(output,list): raise ValueError('normalize output to an item array')
        pointer=request.get('previous_response_id'); conversation=request.get('conversation')
        if pointer and conversation: add(n,'mixed_state_owners','previous_response_id and conversation are both set')
        if mode=='client' and (pointer or conversation): add(n,'mixed_state_owners','client replay also supplies server-owned state')
        if mode=='response_chain' and pointer and pointer not in responses and pointer not in turn.get('external_response_ids',[]):
            add(n,'unknown_previous_response','chain points outside observed/declared history','warning')
        if mode=='conversation' and not conversation: add(n,'missing_conversation','conversation owner lacks conversation reference')
        if mode=='response_chain' and prior and not pointer: add(n,'lost_chain','continuation lost previous_response_id')
        if prior and mode=='client':
            old_items=prior['request'].get('input',[])+prior['response'].get('output',[])
            if turn.get('compaction_boundary'):
                opaque=[x for x in incoming if x.get('type')=='compaction']
                if not opaque: add(n,'missing_compaction','declared boundary has no compaction item')
                expected=turn.get('expected_compaction_hash')
                if expected and not any(digest(x)==expected for x in opaque): add(n,'changed_compaction','opaque compaction bytes differ from the recorded response')
            else:
                changes=differences(old_items,incoming[:len(old_items)])
                allowed=turn.get('intentional_changes',{})
                for change in changes:
                    reason=allowed.get(change['path'])
                    code='intentional_history_change' if isinstance(reason,str) and reason.strip() else 'history_drift'
                    add(n,code,change,'info' if code.startswith('intentional') else 'error')
        if pointer in responses:
            old_output=responses[pointer].get('output',[])
            old_hashes={digest(x) for x in old_output}
            if any(digest(x) in old_hashes for x in incoming): add(n,'duplicated_server_history','new input repeats the previous response output','warning')
            # A phase-lost projection evades exact hashes. Equal assistant content
            # is only a diagnostic candidate, never authority to delete input.
            for i,item in enumerate(incoming):
                if not isinstance(item,dict) or item.get('role')!='assistant': continue
                projected=digest({k:v for k,v in item.items() if k!='phase'})
                for j,old in enumerate(old_output):
                    if not isinstance(old,dict) or old.get('role')!='assistant': continue
                    if digest(item)==digest(old): continue
                    if projected==digest({k:v for k,v in old.items() if k!='phase'}):
                        add(n,'possible_phase_drift_replay',{
                            'input_index':i,'previous_output_index':j,
                            'differences':differences(old,item),
                            'interpretation':'Possible replay with changed phase; verify trusted event provenance before changing input'},'warning')
                        break
        for item in incoming+output:
            if not isinstance(item,dict): raise ValueError('each normalized item must be an object')
            kind=item.get('type')
            if kind=='function_call':
                key=item.get('call_id')
                if not isinstance(key,str) or not key: add(n,'missing_call_id','function call has no call_id'); continue
                fingerprint=digest(item)
                if key in calls and calls[key]!=fingerprint: add(n,'reused_call_id','same call_id identifies different calls')
                calls[key]=fingerprint
                args=item.get('arguments')
                try:
                    if isinstance(args,str): args=json.loads(args)
                    if not isinstance(args,dict): raise ValueError()
                except ValueError: add(n,'malformed_arguments','function arguments are not a JSON object')
            elif kind=='function_call_output':
                key=item.get('call_id')
                if key not in calls:
                    # Server-managed histories may begin before this trace window.
                    add(n,'orphan_tool_result','no observed call matches call_id','warning' if mode!='client' else 'error')
                resolved.add(key)
            elif kind=='compaction' and not item.get('encrypted_content'):
                add(n,'incomplete_compaction','compaction item has no opaque encrypted_content')
        if response.get('status') in ('failed','incomplete','cancelled'):
            add(n,'nonterminal_success',{'status':response['status']},'warning')
        if turn.get('terminal') and set(calls)-resolved:
            add(n,'unresolved_tool_calls',{'count':len(set(calls)-resolved)})
        rid=response.get('id')
        if rid:
            if rid in responses: add(n,'duplicate_response_id','response ID appears twice')
            responses[rid]=response
        prior=turn
    return {'turns':len(turns),'findings':findings,'errors':sum(x['severity']=='error' for x in findings),
            'limits':'Normalized structural diagnosis only. Verify provider-specific state/compaction rules. Hash-only output avoids prompt contents; hashes are still identifiers. No live ablation or opaque-content decoding.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--expected',type=Path,help='Optional expected normalized request JSON; compare to actual JSON in --trace')
    a=p.parse_args()
    try:
        if a.expected:
            result={'differences':differences(json.loads(a.expected.read_text()),json.loads(a.trace.read_text()))}
        else: result=audit([json.loads(s) for s in a.trace.read_text().splitlines() if s.strip()])
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 2 if result.get('errors') else 0
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
