import copy
from .projection import project
def replay(capture):
    # Archive is an operations artifact. Only client is returned by our web route.
    client,items=project(capture)
    return {'client':client,'archive':{'events':copy.deepcopy(capture['events']),'output_items':copy.deepcopy(items)}}
