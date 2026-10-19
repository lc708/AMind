import argparse,json,sys
from pathlib import Path
from .store import Store
from .service import handle
def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--receipts',type=Path,required=True);a=p.parse_args()
    store=None
    try:
        request=json.loads(a.request.read_text());store=Store(a.db);answer=handle(store,request,a.receipts)
        print(json.dumps(answer));return 0
    except (ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2
    finally:
        if store:store.close()
if __name__=='__main__':sys.exit(main())
