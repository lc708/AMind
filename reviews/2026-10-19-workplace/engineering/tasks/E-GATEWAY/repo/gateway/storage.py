import json,os,tempfile
from pathlib import Path
MAX_CAPTURE_BYTES=8*1024*1024
def load_capture(path):
    raw=path.read_bytes()
    if len(raw)>MAX_CAPTURE_BYTES:raise ValueError('capture exceeds desk replay limit')
    capture=json.loads(raw)
    if not isinstance(capture,dict):raise ValueError('capture object required')
    return capture
def write_result(path,result):
    # A browser poll must see the previous artifact or a complete new artifact.
    content=json.dumps(result,ensure_ascii=False,allow_nan=False)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.gateway-',delete=False) as output:
            temporary=Path(output.name);output.write(content);output.flush();os.fsync(output.fileno())
        os.replace(temporary,path);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
