from .render import render
TERMINALS={'response.completed':'completed','response.failed':'failed','response.incomplete':'incomplete','response.cancelled':'cancelled'}
def project(capture):
    events=capture['events'];display=[];terminal=None;status='disconnected'
    for event in events:
        if event.get('type')=='response.output_text.delta':display.append(event.get('delta',''))
        if event.get('type') in TERMINALS:
            terminal=event.get('response') or {};status=TERMINALS[event['type']]
        elif event.get('type')=='error':status='stream_error'
    items=(terminal or {}).get('output',[]);final=[]
    for item in items:
        if item.get('type')!='message':continue
        if item.get('phase') not in (None,'final_answer'):continue
        final.extend(c.get('text','') for c in item.get('content',[]) if c.get('type')=='output_text')
    final_text=''.join(final);display_text=''.join(display)
    return {'status':status,'display_text':display_text,'final_text':final_text,
            'answer_complete':status=='completed' and bool(final_text),
            'html':render(final_text or display_text)},items
