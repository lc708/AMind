"""Injectable Responses-style tool loop and durable effect ledger; no provider client.

The application supplies model_call(request), tool validators, authorization and handlers.
This is a synchronous reference kernel, not a hosted agent platform or an isolation layer.
"""
import hashlib
import importlib.util
import json
import sqlite3
import time
from pathlib import Path


# Keep standalone imports and importlib-loaded skill modules on the same public
# response contract, without relying on the host's sys.path or SDK installation.
_response_spec=importlib.util.spec_from_file_location('amind_loop_response_contract',Path(__file__).with_name('response_contract.py'))
_response_contract=importlib.util.module_from_spec(_response_spec)
_response_spec.loader.exec_module(_response_contract)


class ReconciliationRequired(RuntimeError): pass


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def operation_key(tenant, task_id, call_id):
    """Remote deduplication scope must include tenant, not just the local DB key.

    Retain persisted remote keys for in-flight operations when upgrading an existing
    integration; changing an unresolved operation's key can duplicate the effect.
    """
    if any(not isinstance(x,str) or not x for x in (tenant,task_id,call_id)):
        raise ValueError('nonempty trusted tenant, task and call identity required')
    return hashlib.sha256(canonical(['amind-effect-v2',tenant,task_id,call_id]).encode()).hexdigest()


class EffectLedger:
    """SQLite dispatch records. Remote effects still need their own idempotency/reconciliation."""
    def __init__(self, path):
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS effects (tenant TEXT, key TEXT, request_hash TEXT, state TEXT, result TEXT, PRIMARY KEY(tenant,key))')
    def close(self): self.db.close()
    def perform(self, tenant, key, request, handler):
        fingerprint=hashlib.sha256(canonical(request).encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT request_hash,state,result FROM effects WHERE tenant=? AND key=?',(tenant,key)).fetchone()
            if old:
                if old[0]!=fingerprint: raise ValueError('idempotency key reused with different request')
                if old[1]!='complete': raise ReconciliationRequired('effect outcome unknown; query remote state before retry')
                self.db.execute('COMMIT'); return json.loads(old[2])
            self.db.execute('INSERT INTO effects VALUES (?,?,?, ?,NULL)',(tenant,key,fingerprint,'pending'))
            self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction: self.db.execute('ROLLBACK')
            raise
        # Crash/timeout before the following commit leaves pending and intentionally cannot auto-retry.
        result=handler(key)
        encoded=canonical(result)
        changed=self.db.execute("UPDATE effects SET state='complete',result=? WHERE tenant=? AND key=? AND request_hash=? AND state='pending'",
                                (encoded,tenant,key,fingerprint)).rowcount
        if changed!=1:
            old=self.db.execute('SELECT request_hash,state,result FROM effects WHERE tenant=? AND key=?',(tenant,key)).fetchone()
            if old and old[0]==fingerprint and old[1]=='complete':
                if old[2]==encoded: return json.loads(old[2])
                raise ReconciliationRequired('late handler conflicts with an externally settled effect; confirmed result retained; inspect the receipt before continuing')
            raise ReconciliationRequired('effect record changed during dispatch; reconcile before continuing')
        return result
    def reconcile(self, tenant, key, result, evidence):
        if not isinstance(evidence,str) or not evidence.strip(): raise ValueError('external reconciliation evidence required')
        encoded=canonical({'result':result,'evidence':evidence})
        self.db.execute('CREATE TABLE IF NOT EXISTS reconciliations (tenant TEXT,key TEXT,evidence TEXT)')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            changed=self.db.execute("UPDATE effects SET state='complete',result=? WHERE tenant=? AND key=? AND state='pending'",(canonical(result),tenant,key)).rowcount
            if changed!=1: raise ValueError('exactly one pending effect required')
            self.db.execute('INSERT INTO reconciliations VALUES (?,?,?)',(tenant,key,encoded)); self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise


def run_loop(model_call, input_items, tools, tenant, task_id, ledger, authorize,
             max_rounds=8, max_tool_calls=24, timeout_s=120, cancelled=lambda:False,
             operation_key_for=operation_key):
    """Each tool has schema, validate(args), handler(args, key), side_effect boolean.

    model_call receives {input, tools}; it must set the user's chosen model/settings,
    enforce a transport deadline, and return the full provider output-item dictionaries.
    validate and authorize raise on failure. No dispatch occurs before both succeed.
    operation_key_for may resolve an already-persisted remote key during migration.
    """
    if not tenant or not task_id or max_rounds<1 or max_tool_calls<0 or timeout_s<=0: raise ValueError('invalid loop contract')
    history=list(input_items); dispatches=0; seen={}; started=time.monotonic()
    def checkpoint():
        if cancelled(): raise RuntimeError('cancelled')
        if time.monotonic()-started>=timeout_s: raise TimeoutError('task deadline exceeded')
    for _ in range(max_rounds):
        checkpoint()
        response=model_call({'input':history,'tools':[t['schema'] for t in tools.values()],
                             'remaining_seconds':max(0,timeout_s-(time.monotonic()-started))})
        checkpoint()
        _response_contract.validate_terminal(response)  # Dispatch safety shares terminal validation, not display parsing.
        if response.get('status')!='completed': return {'status':response.get('status','unknown'),'history':history,'response':response}
        output=response.get('output')
        if not isinstance(output,list) or any(not isinstance(i,dict) for i in output): raise ValueError('full output items required')
        calls=[i for i in output if i.get('type')=='function_call']
        if dispatches+len(calls)>max_tool_calls: raise RuntimeError('tool-call budget exceeded before dispatch')
        history.extend(output)  # Preserve phase, reasoning and opaque items exactly.
        if not calls: return {'status':'completed','history':history,'response':response,'tool_calls':dispatches}
        for call in calls:
            checkpoint(); name=call.get('name'); call_id=call.get('call_id')
            if name not in tools or not isinstance(call_id,str) or not call_id: raise ValueError('unknown tool or missing call_id')
            tool=tools[name]; args=json.loads(call['arguments']) if isinstance(call.get('arguments'),str) else call.get('arguments')
            if not isinstance(args,dict): raise ValueError('tool arguments must be an object')
            tool['validate'](args); authorize(tenant,name,args)
            checkpoint()  # Validation/authorization may block or observe cancellation.
            fingerprint=canonical({'name':name,'args':args})
            if call_id in seen and seen[call_id][0]!=fingerprint: raise ValueError('call_id changed payload')
            # Stable scope is supplied by the caller; do not use untrusted args as tenant/task identity.
            key=operation_key_for(tenant,task_id,call_id)
            if not isinstance(key,str) or not key: raise ValueError('invalid durable operation key')
            def dispatch(k):
                checkpoint()  # A ledger lock wait must not bypass cancellation/deadline.
                return tool['handler'](args,k)
            if call_id in seen: result=seen[call_id][1]
            elif tool.get('side_effect'):
                result=ledger.perform(tenant,key,{'task':task_id,'name':name,'args':args},dispatch)
            else: result=dispatch(key)
            dispatches+=1; seen[call_id]=(fingerprint,result)
            checkpoint()
            history.append({'type':'function_call_output','call_id':call_id,'output':canonical(result)})
    return {'status':'round_limit','history':history,'tool_calls':dispatches}
