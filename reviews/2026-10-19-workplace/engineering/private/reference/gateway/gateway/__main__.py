import argparse,json,sys
from pathlib import Path
from .service import replay_capture
from .storage import load_capture,write_result
def main():
    p=argparse.ArgumentParser(description='Offline support-desk capture replay')
    p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        result=replay_capture(load_capture(a.capture));write_result(a.out,result)
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print(json.dumps({'error':str(exc)}));return 2
    print(json.dumps({'written':str(a.out),'status':result['client']['status']}));return 0
if __name__=='__main__':sys.exit(main())
