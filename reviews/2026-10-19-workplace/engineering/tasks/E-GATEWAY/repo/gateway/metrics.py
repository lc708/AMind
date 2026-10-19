from collections import Counter
def archive_summary(capture,items):
    kinds=Counter(event['type'] for event in capture['events'])
    item_types=Counter(str(item.get('type','unknown')) for item in items)
    first=capture['events'][0] if capture['events'] else {}
    last=capture['events'][-1] if capture['events'] else {}
    start=first.get('received_at_ms');stop=last.get('received_at_ms')
    elapsed=None
    if type(start) in (int,float) and type(stop) in (int,float) and stop>=start:elapsed=stop-start
    return {'format_version':1,'capture_id':capture.get('capture_id'),
            'event_count':len(capture['events']),'event_types':dict(kinds),
            'item_count':len(items),'item_types':dict(item_types),'capture_elapsed_ms':elapsed}
