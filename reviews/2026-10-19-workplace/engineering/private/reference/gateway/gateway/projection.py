from .render import render
TERMINALS={'response.completed':'completed','response.failed':'failed','response.incomplete':'incomplete','response.cancelled':'cancelled'}
def owner(value):
    agent=value.get('agent')
    if agent is None:return None
    if not isinstance(agent,dict) or not isinstance(agent.get('agent_name'),str):raise ValueError('invalid attribution')
    return agent['agent_name']
def project(capture):
    mode=capture.get('mode','single');events=capture.get('events')
    if mode not in ('single','multi_agent') or not isinstance(events,list):raise ValueError('invalid capture')
    owners={};deltas=[];terminal=None;failed=None
    for event in events:
        if not isinstance(event,dict):raise ValueError('event object required')
        if terminal is not None or failed is not None:raise ValueError('event after terminal')
        kind=event.get('type');outer=owner(event);inner=owner(event.get('item') or {})
        if outer is not None and inner is not None and outer!=inner:raise ValueError('conflicting event attribution')
        who=outer or inner;index=event.get('output_index')
        if who is not None and index is not None:
            if index in owners and owners[index]!=who:raise ValueError('stream ownership changed')
            owners[index]=who
        if kind=='response.output_text.delta':
            text=event.get('delta','')
            if not isinstance(text,str):raise ValueError('delta string required')
            deltas.append((index,who,text))
        elif kind in TERMINALS:
            terminal=event.get('response')
            if not isinstance(terminal,dict) or terminal.get('status')!=TERMINALS[kind]:raise ValueError('terminal status mismatch')
        elif kind=='error':failed=event
    items=terminal.get('output',[]) if terminal else []
    if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):raise ValueError('output item array required')
    multi=mode=='multi_agent' or bool(owners) or any(owner(i) is not None for i in items)
    for index,item in enumerate(items):
        who=owner(item)
        if who is not None:
            if index in owners and owners[index]!=who:raise ValueError('terminal ownership changed')
            owners[index]=who
    display=''.join(text for index,who,text in deltas if not multi or (who or owners.get(index))=='/root')
    final=[];refusal=False;pending=False
    for item in items:
        if item.get('type')=='function_call':pending=True
        if item.get('type')!='message':continue
        if multi and owner(item)!='/root':continue
        phase=item.get('phase')
        if phase!='final_answer' and not(not multi and phase is None):continue
        for content in item.get('content',[]):
            if content.get('type')=='output_text':final.append(content.get('text',''))
            elif content.get('type')=='refusal':refusal=True
    status=terminal['status'] if terminal else ('stream_error' if failed else 'disconnected')
    if terminal and status=='completed' and (terminal.get('error') is not None or terminal.get('incomplete_details') is not None):raise ValueError('contradictory completed response')
    final_text=''.join(final)
    return {'status':status,'display_text':display,'final_text':final_text,
            'answer_complete':status=='completed' and not pending and bool(final_text or refusal),
            'html':render(final_text or display)},items
