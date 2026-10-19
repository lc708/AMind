from .validation import validate_capture
from .replay import replay
from .metrics import archive_summary
class Gateway:
    def __init__(self):self.accepted=0
    def ingest(self,capture):
        validate_capture(capture)
        bundle=replay(capture)
        bundle['archive']['summary']=archive_summary(capture,bundle['archive']['output_items'])
        self.accepted+=1
        return bundle
def replay_capture(capture):
    # HTTP integration uses bundle['client']; the full bundle stays in ops storage.
    return Gateway().ingest(capture)
