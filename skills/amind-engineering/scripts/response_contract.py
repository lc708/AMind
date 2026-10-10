"""Offline reference normalizers for Responses payloads, terminal streams and batch joins.
No SDK, credentials or network calls. Preserve raw provider fields before simplifying.
"""
import copy


def normalize(response):
    if not isinstance(response,dict): raise ValueError('response must be a dictionary')
    output=response.get('output',[])
    if not isinstance(output,list): raise ValueError('output must be an item array')
    text=[]; final_text=[]; commentary_text=[]; refusals=[]; final_refusals=[]; calls=[]
    for item in output:
        if not isinstance(item,dict): raise ValueError('output item must be an object')
        if item.get('type')=='function_call': calls.append(copy.deepcopy(item))
        if item.get('type')!='message': continue
        contents=item.get('content',[])
        if not isinstance(contents,list): raise ValueError('message content must be an item array')
        for content in contents:
            if not isinstance(content,dict): raise ValueError('content item must be an object')
            if content.get('type')=='output_text':
                value=content.get('text',''); text.append(value)
                if item.get('phase')=='commentary': commentary_text.append(value)
                elif item.get('phase') in (None,'final_answer'): final_text.append(value)
            elif content.get('type')=='refusal':
                value=content.get('refusal',''); refusals.append(value)
                if item.get('phase') in (None,'final_answer'): final_refusals.append(value)
    status=response.get('status','unknown')
    if status=='completed' and (response.get('error') is not None or response.get('incomplete_details') is not None):
        raise ValueError('completed response contains an error or incomplete details')
    return {'status':status,'scorable_transport':status=='completed','text':''.join(text),
            'final_text':''.join(final_text),'commentary_text':''.join(commentary_text),
            'answer_complete':status=='completed' and not calls and bool(final_text or final_refusals),
            'refusals':refusals,'function_calls':calls,'output_items':copy.deepcopy(output),
            'model':response.get('model'),'usage':copy.deepcopy(response.get('usage')),
            'response_id':response.get('id'),'incomplete_details':copy.deepcopy(response.get('incomplete_details')),
            'error':copy.deepcopy(response.get('error')),'raw_response':copy.deepcopy(response)}


def terminal_stream(events):
    """Partial text and an open/idle stream never substitute for a terminal response."""
    terminal=None; failure=None; text_deltas=[]; raw_events=[]
    for event in events:
        kind=event.get('type')
        if terminal is not None or failure is not None: raise ValueError('event after terminal outcome')
        raw_events.append(copy.deepcopy(event))
        if kind=='response.output_text.delta': text_deltas.append(event.get('delta',''))
        elif kind in ('response.completed','response.failed','response.incomplete'):
            terminal=event.get('response')
            expected=kind.split('.')[-1]
            if not isinstance(terminal,dict) or terminal.get('status')!=expected: raise ValueError('terminal event/status mismatch')
        elif kind=='error': failure=copy.deepcopy(event)
    if terminal is not None: return {**normalize(terminal),'display_deltas':''.join(text_deltas),'raw_events':raw_events}
    return {'status':'stream_error' if failure else 'disconnected','scorable_transport':False,
            'display_deltas':''.join(text_deltas),'error':failure,'usage':None,'raw_events':raw_events}


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
