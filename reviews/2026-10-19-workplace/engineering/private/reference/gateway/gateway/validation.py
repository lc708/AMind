ALLOWED_MODES=frozenset(('single','multi_agent'))
def validate_capture(capture):
    if capture.get('mode','single') not in ALLOWED_MODES:raise ValueError('unsupported replay mode')
    events=capture.get('events')
    if not isinstance(events,list):raise ValueError('ordered event array required')
    if len(events)>50000:raise ValueError('event count exceeds desk replay limit')
    for position,event in enumerate(events):
        if not isinstance(event,dict):raise ValueError('event object required at '+str(position))
        if not isinstance(event.get('type'),str):raise ValueError('event type required at '+str(position))
    # This is envelope validation. The projector owns protocol/terminal semantics.
    return capture
