import hashlib,json,sqlite3
def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def operation_key(tenant,job,stage,item):return hashlib.sha256(packed([job,stage,item]).encode()).hexdigest()
class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(str(path),isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs(tenant TEXT,job TEXT,spec TEXT,cancelled INTEGER,attempts INTEGER,PRIMARY KEY(tenant,job))')
        self.db.execute('CREATE TABLE IF NOT EXISTS work(tenant TEXT,job TEXT,stage TEXT,item TEXT,state TEXT,result TEXT,operation_key TEXT,PRIMARY KEY(tenant,job,stage,item))')
    def close(self):self.db.close()
    def job(self,tenant,job):
        row=self.db.execute('SELECT spec,cancelled,attempts FROM jobs WHERE job=?',(job,)).fetchone()
        if row is None:raise ValueError('job not found for tenant')
        return {'spec':json.loads(row[0]),'cancelled':bool(row[1]),'attempts':row[2]}
    def rows(self,tenant,job):
        return [dict(zip(('stage','item','state','result','operation_key'),r)) for r in self.db.execute('SELECT stage,item,state,result,operation_key FROM work WHERE tenant=? AND job=? ORDER BY rowid',(tenant,job))]
    def update(self,tenant,job,stage,item,state,result=None):
        self.db.execute('UPDATE work SET state=?,result=? WHERE tenant=? AND job=? AND stage=? AND item=?',(state,packed(result),tenant,job,stage,item))
