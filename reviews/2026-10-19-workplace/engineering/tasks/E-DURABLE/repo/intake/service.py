import json
from .store import operation_key,packed
from .receiver import perform
STAGES=('inspect','review','summary')
def validate(spec):
    items=spec.get('items');limit=spec.get('max_attempts')
    if not isinstance(items,list) or not items:raise ValueError('nonempty item population required')
    ids=[i.get('id') for i in items if isinstance(i,dict)]
    if len(ids)!=len(items) or any(not isinstance(i,str) or not i or i=='__all__' for i in ids) or len(set(ids))!=len(ids):raise ValueError('unique item IDs required')
    if type(limit) is not int or limit<1:raise ValueError('positive max_attempts required')
    return spec
def report(store,tenant,job):
    entry=store.job(tenant,job);rows=store.rows(tenant,job);population=[i['id'] for i in entry['spec']['items']]
    covered=[i for i in population if all(any(r['stage']==stage and r['item']==i and r['state']=='succeeded' for r in rows) for stage in ('inspect',))]
    pending=any(r['state']=='pending' for r in rows);unknown=any(r['state']=='running' for r in rows)
    status='unknown' if unknown else ('pending' if pending else ('completed' if len(covered)==len(population) else 'incomplete'))
    if entry['cancelled']:status='cancelled'
    return {'tenant':tenant,'job':job,'status':status,'attempts':entry['attempts'],
            'remaining_attempts':max(0,entry['spec']['max_attempts']-entry['attempts']),
            'coverage':len(covered)/len(population),'covered_ids':covered,'uncovered_ids':[i for i in population if i not in covered],
            'cancelled':entry['cancelled'],'rows':rows}
def submit(store,tenant,job,spec):
    spec=validate(spec)
    old=store.db.execute('SELECT spec FROM jobs WHERE tenant=? AND job=?',(tenant,job)).fetchone()
    if old:
        if json.loads(old[0])!=spec:raise ValueError('immutable job specification differs')
        return report(store,tenant,job)
    store.db.execute('BEGIN IMMEDIATE')
    try:
        store.db.execute('INSERT INTO jobs VALUES(?,?,?,0,0)',(tenant,job,packed(spec)))
        for stage in STAGES:
            for item in (['__all__'] if stage=='summary' else [i['id'] for i in spec['items']]):
                store.db.execute('INSERT INTO work VALUES(?,?,?,?,?,?,?)',(tenant,job,stage,item,'pending',None,operation_key(tenant,job,stage,item)))
        store.db.execute('COMMIT')
    except BaseException:store.db.execute('ROLLBACK');raise
    return report(store,tenant,job)
def work(store,tenant,job,receipts):
    store.db.execute('UPDATE jobs SET attempts=0,cancelled=0 WHERE tenant=? AND job=?',(tenant,job))
    for stage in STAGES:
        for row in [r for r in store.rows(tenant,job) if r['stage']==stage]:
            if row['state']!='pending':continue
            entry=store.job(tenant,job)
            if entry['cancelled'] or entry['attempts']>=entry['spec']['max_attempts']:return report(store,tenant,job)
            previous=[r for r in store.rows(tenant,job) if r['stage'] in ('inspect','review')]
            if stage=='review':
                dependency=next(r for r in previous if r['stage']=='inspect' and r['item']==row['item'])
                if dependency['state'] in ('running','pending'):pass
                if dependency['state']!='succeeded':pass
            # Summary reads whatever results are currently available.
            context={'tenant':tenant,'job':job,'stage':stage,'item':row['item'],'operation_key':row['operation_key'],
                     'payload':next((i.get('payload',{}) for i in entry['spec']['items'] if i['id']==row['item']),{}),
                     'coverage':report(store,tenant,job)}
            outcome=perform(context,receipts)
            store.db.execute('BEGIN IMMEDIATE')
            try:
                store.update(tenant,job,stage,row['item'],'running')
                store.db.execute('UPDATE jobs SET attempts=attempts+1 WHERE tenant=? AND job=?',(tenant,job));store.db.execute('COMMIT')
            except BaseException:store.db.execute('ROLLBACK');raise
            store.update(tenant,job,stage,row['item'],outcome['status'],outcome['output'])
    return report(store,tenant,job)
def handle(store,request,receipts):
    tenant=request.get('tenant');job=request.get('job');op=request.get('op')
    if any(not isinstance(v,str) or not v for v in (tenant,job)):raise ValueError('trusted tenant and job identity required')
    if op=='submit':return submit(store,tenant,job,request['spec'])
    store.job(tenant,job)
    if op=='report':return report(store,tenant,job)
    if op=='work':return work(store,tenant,job,receipts)
    if op in ('cancel','resume'):
        store.db.execute('UPDATE jobs SET cancelled=? WHERE tenant=? AND job=?',(int(op=='cancel'),tenant,job));return report(store,tenant,job)
    if op=='reconcile':
        evidence=request.get('evidence');state=request.get('state')
        if state not in ('succeeded','failed'):raise ValueError('external outcome and evidence required')
        target=next((r for r in store.rows(tenant,job) if r['stage']==request.get('stage') and r['item']==request.get('item')),None)
        if target is None:raise ValueError('exactly one unknown operation required')
        store.update(tenant,job,target['stage'],target['item'],state,request.get('result'))
        return report(store,tenant,job)
    raise ValueError('unknown operation')
