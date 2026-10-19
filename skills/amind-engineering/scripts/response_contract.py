"""Offline reference normalizers for Responses payloads, terminal streams and batch joins.
No SDK, credentials or network calls. Preserve raw provider fields before simplifying.
"""
import copy


HOSTED_ITEMS = frozenset(('multi_agent_call', 'multi_agent_call_output', 'agent_message'))
KNOWN_ITEMS = HOSTED_ITEMS | frozenset(('message', 'reasoning', 'compaction', 'function_call',
    'web_search_call', 'file_search_call', 'computer_call', 'code_interpreter_call',
    'image_generation_call', 'mcp_call', 'mcp_list_tools', 'mcp_approval_request', 'custom_tool_call'))


def agent_name(value):
    agent = value.get('agent') or {}
    if not isinstance(agent, dict): raise ValueError('agent attribution must be an object')
    name = agent.get('agent_name')
    if name is not None and (not isinstance(name, str) or not name): raise ValueError('invalid agent name')
    return name


def validate_mode(request, transport='http', compact_endpoint=False):
    """Validate documented mode incompatibilities, not all API fields or access.

    Hosted Multi-agent actions are not developer functions. App-side dispatch
    budgets remain necessary: the provider max_tool_calls field is unsupported.
    """
    if transport not in ('http', 'sse', 'websocket'): raise ValueError('unknown transport')
    multi = request.get('multi_agent') or {}
    if not isinstance(multi, dict): raise ValueError('multi_agent must be an object')
    enabled = multi.get('enabled', False)
    if type(enabled) is not bool: raise ValueError('multi_agent.enabled must be boolean')
    if enabled:
        if compact_endpoint: raise ValueError('Multi-agent does not support standalone compact')
        if 'max_tool_calls' in request: raise ValueError('Multi-agent does not support max_tool_calls; bound application dispatch')
        if (request.get('reasoning') or {}).get('summary') is not None:
            raise ValueError('Multi-agent does not support reasoning.summary')
        limit = multi.get('max_concurrent_subagents', 3)
        if type(limit) is not int or limit < 1: raise ValueError('positive subagent concurrency required')
    return {'mode': 'multi_agent' if enabled else 'single', 'transport': transport,
            'automatic_compaction': enabled, 'application_tool_budget_required': enabled}


def validate_terminal(response):
    """Validate terminal facts without interpreting opaque/message content."""
    if not isinstance(response,dict): raise ValueError('response must be a dictionary')
    status=response.get('status','unknown')
    if status=='completed' and (response.get('error') is not None or response.get('incomplete_details') is not None):
        raise ValueError('completed response contains an error or incomplete details')
    return status


def normalize(response, mode='auto'):
    status=validate_terminal(response)
    output=response.get('output',[])
    if not isinstance(output,list): raise ValueError('output must be an item array')
    if mode not in ('auto', 'single', 'multi_agent'): raise ValueError('unknown response mode')
    attributed = any(isinstance(i, dict) and (i.get('agent') is not None or i.get('type') in HOSTED_ITEMS) for i in output)
    if mode == 'single' and attributed: raise ValueError('attributed output requires multi_agent mode')
    effective_mode = 'multi_agent' if mode == 'multi_agent' or attributed else 'single'
    text=[]; final_text=[]; commentary_text=[]; refusals=[]; final_refusals=[]; calls=[]; per_agent={}
    for item in output:
        if not isinstance(item,dict): raise ValueError('output item must be an object')
        if item.get('type')=='function_call': calls.append(copy.deepcopy(item))
        if item.get('type')!='message': continue
        owner = agent_name(item)
        user_visible = effective_mode == 'single' or owner == '/root'
        final_phase = item.get('phase') == 'final_answer' or (effective_mode == 'single' and item.get('phase') is None)
        contents=item.get('content',[])
        if not isinstance(contents,list): raise ValueError('message content must be an item array')
        for content in contents:
            if not isinstance(content,dict): raise ValueError('content item must be an object')
            if content.get('type')=='output_text':
                value=content.get('text','')
                if not isinstance(value, str): raise ValueError('output text must be a string')
                per_agent.setdefault(owner or 'unattributed', []).append(value)
                if not user_visible: continue
                text.append(value)
                if item.get('phase')=='commentary': commentary_text.append(value)
                elif final_phase: final_text.append(value)
            elif content.get('type')=='refusal':
                if not user_visible: continue
                value=content.get('refusal',''); refusals.append(value)
                if final_phase: final_refusals.append(value)
    unknown_items=[copy.deepcopy(i) for i in output if i.get('type') not in KNOWN_ITEMS]
    return {'status':status,'scorable_transport':status=='completed','text':''.join(text),
            'final_text':''.join(final_text),'commentary_text':''.join(commentary_text),
            'answer_complete':status=='completed' and not calls and not unknown_items and bool(final_text or final_refusals),
            'refusals':refusals,'function_calls':calls,'output_items':copy.deepcopy(output),
            'model':response.get('model'),'usage':copy.deepcopy(response.get('usage')),
            'response_id':response.get('id'),'incomplete_details':copy.deepcopy(response.get('incomplete_details')),
            'error':copy.deepcopy(response.get('error')),'raw_response':copy.deepcopy(response),
            'mode':effective_mode, 'agent_text':{k:''.join(v) for k,v in per_agent.items()},
            'hosted_items':[copy.deepcopy(i) for i in output if i.get('type') in HOSTED_ITEMS],
            'unknown_items':unknown_items}


def terminal_stream(events, mode='auto'):
    """Partial text and an open/idle stream never substitute for a terminal response."""
    terminal=None; failure=None; text_deltas=[]; raw_events=[]; owners={}; attributed=False
    for event in events:
        kind=event.get('type')
        if terminal is not None or failure is not None: raise ValueError('event after terminal outcome')
        raw_events.append(copy.deepcopy(event))
        event_owner = agent_name(event)
        item_owner = agent_name(event.get('item') or {})
        if event_owner is not None and item_owner is not None and event_owner != item_owner:
            raise ValueError('event and item changed agent attribution')
        owner = event_owner or item_owner
        attributed = attributed or owner is not None
        index = event.get('output_index')
        if owner and index is not None:
            if index in owners and owners[index] != owner: raise ValueError('output index changed agent attribution')
            owners[index] = owner
        if kind=='response.output_text.delta': text_deltas.append((index,owner,event.get('delta','')))
        elif kind in ('response.completed','response.failed','response.incomplete'):
            terminal=event.get('response')
            expected=kind.split('.')[-1]
            if not isinstance(terminal,dict) or terminal.get('status')!=expected: raise ValueError('terminal event/status mismatch')
        elif kind=='error': failure=copy.deepcopy(event)
    result = normalize(terminal, mode='multi_agent' if attributed and mode=='auto' else mode) if terminal is not None else None
    if terminal is not None:
        for index,item in enumerate(terminal.get('output',[])):
            owner=agent_name(item)
            if owner is not None:
                if index in owners and owners[index]!=owner: raise ValueError('terminal output changed stream agent attribution')
                owners[index]=owner
    multi = mode == 'multi_agent' or attributed or (result and result['mode'] == 'multi_agent')
    if mode == 'single' and multi: raise ValueError('attributed stream requires multi_agent mode')
    display=''.join(delta for index,owner,delta in text_deltas if not multi or (owner or owners.get(index)) == '/root')
    by_agent={}
    for index,owner,delta in text_deltas: by_agent.setdefault(owner or owners.get(index) or 'unattributed', []).append(delta)
    projections={'display_deltas':display,'agent_deltas':{k:''.join(v) for k,v in by_agent.items()},'raw_events':raw_events}
    if terminal is not None: return {**result,**projections}
    return {'status':'stream_error' if failure else 'disconnected','scorable_transport':False,
            **projections,'error':failure,'usage':None}


class InjectionTracker:
    """Offline WebSocket acknowledgement state; never executes tools or sends data.

    Persist snapshot() with the application's effect ledger. An unacknowledged
    injection after reconnect is unknown, not permission to execute its tool again.
    """
    def __init__(self, response_id, max_tool_outputs, snapshot=None):
        if not isinstance(response_id,str) or not response_id or type(max_tool_outputs) is not int or max_tool_outputs < 0:
            raise ValueError('response identity and application tool budget required')
        self.response_id=response_id; self.limit=max_tool_outputs
        self.calls={}; self.completed=False; self.cancelled=False
        if snapshot is not None:
            if snapshot.get('response_id')!=response_id or snapshot.get('limit')!=max_tool_outputs:
                raise ValueError('injection contract changed')
            self.calls=copy.deepcopy(snapshot['calls']); self.completed=snapshot['completed']; self.cancelled=snapshot['cancelled']
    def prepare(self, call, output):
        if self.cancelled: raise RuntimeError('cancelled: no new injection')
        if call.get('type')!='function_call': raise ValueError('only developer function outputs can be injected')
        key=call.get('call_id')
        if not isinstance(key,str) or not key: raise ValueError('missing call identity')
        if key in self.calls: raise ValueError('injection already recorded; reconcile acknowledgement instead of repeating execution')
        if any(v['state']=='pending' for v in self.calls.values()):
            raise RuntimeError('acknowledge the single outstanding injection before sending another')
        if len(self.calls)>=self.limit: raise RuntimeError('application tool-output budget exceeded')
        item={'type':'function_call_output','call_id':key,'output':copy.deepcopy(output)}
        self.calls[key]={'item':item,'state':'continuation' if self.completed else 'pending'}
        if self.completed: return None
        return {'type':'response.inject','response_id':self.response_id,'input':[item]}
    def acknowledge(self, call_ids, event):
        # The transport associates the acknowledgement with its submitted input.
        # Ambiguous ack correlation is deliberately rejected rather than guessed.
        if event.get('response_id')!=self.response_id: raise ValueError('wrong response acknowledgement')
        if not call_ids or len(call_ids)!=len(set(call_ids)): raise ValueError('unique acknowledged call IDs required')
        if set(call_ids)!={k for k,v in self.calls.items() if v['state']=='pending'}:
            raise ValueError('acknowledgement must match the unique outstanding injection')
        kind=event.get('type'); code=(event.get('error') or {}).get('code')
        if kind=='response.inject.created': state='accepted'
        elif kind=='response.inject.failed' and code=='response_already_completed': state='continuation'
        elif kind=='response.inject.failed': state='failed'
        else: raise ValueError('not an injection acknowledgement')
        for key in call_ids:
            if key not in self.calls or self.calls[key]['state']!='pending': raise ValueError('unknown or duplicate acknowledgement')
        if state=='continuation' and event.get('input') != [self.calls[key]['item'] for key in call_ids]:
            raise ValueError('failed injection returned different continuation items')
        for key in call_ids:
            self.calls[key]['state']=state
            self.calls[key]['acknowledgement']=copy.deepcopy(event)
    def finish_response(self): self.completed=True
    def cancel(self): self.cancelled=True
    def snapshot(self):
        return copy.deepcopy({'response_id':self.response_id,'limit':self.limit,'calls':self.calls,
                              'completed':self.completed,'cancelled':self.cancelled})
    def outcome(self):
        states=[v['state'] for v in self.calls.values()]
        return {'done':self.completed and 'pending' not in states and 'failed' not in states,
                'unknown_call_ids':[k for k,v in self.calls.items() if v['state']=='pending'],
                'failed_call_ids':[k for k,v in self.calls.items() if v['state']=='failed'],
                'continuation_input':[copy.deepcopy(v['item']) for v in self.calls.values() if v['state']=='continuation'],
                'cancelled':self.cancelled}


def match_batch(request_ids, results):
    if len(request_ids)!=len(set(request_ids)): raise ValueError('duplicate request custom_id')
    expected=set(request_ids); indexed={}
    for row in results:
        key=row.get('custom_id')
        if key not in expected: raise ValueError('unknown batch custom_id')
        if key in indexed: raise ValueError('duplicate batch custom_id')
        indexed[key]=row
    errors=[]; incomplete=[]; unknown=[]
    for key,row in indexed.items():
        result=row.get('response') or {}; code=result.get('status_code')
        body=result.get('body') or {}; status=body.get('status') if isinstance(body,dict) else None
        if (row.get('error') is not None or not isinstance(code,int) or isinstance(code,bool)
                or not 200<=code<300 or (isinstance(body,dict) and (body.get('error') is not None
                or (status=='completed' and body.get('incomplete_details') is not None)))):
            errors.append(key)
        elif status in ('failed','incomplete','cancelled'):
            errors.append(key)
            if status=='incomplete': incomplete.append(key)
        elif status!='completed': unknown.append(key)
    return {'ordered':[copy.deepcopy(indexed.get(key)) for key in request_ids],
            'missing':[key for key in request_ids if key not in indexed],
            'errors':errors,'incomplete':incomplete,'unknown_status':unknown}
