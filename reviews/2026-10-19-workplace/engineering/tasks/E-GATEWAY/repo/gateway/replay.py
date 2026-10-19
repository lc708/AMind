import copy
from .projection import project
SUPPORTED={'message','reasoning','function_call','web_search_call'}
def replay(capture):
    client,items=project(capture)
    # The archive predates hosted tool items; old readers only accept these types.
    archived=[i for i in items if i.get('type') in SUPPORTED]
    return {'client':client,'archive':{'events':copy.deepcopy(capture['events']),'output_items':archived}}
