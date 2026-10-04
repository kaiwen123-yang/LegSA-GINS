"""Read/verify the lossless original-V3 task, metric and action ledgers. No science calls."""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,sys
p=argparse.ArgumentParser(__doc__)
p.add_argument('table',choices=('tasks','metrics','actions'))
p.add_argument('--verify',action='store_true',help='Verify complete compressed and decompressed hashes/size/data-row count')
p.add_argument('--fields',help='Comma separated exact CSV field names; omitted means all fields')
p.add_argument('--limit',type=int,default=20,help='Displayed rows; zero means all rows')
a=p.parse_args();assert a.limit>=0
root=Path(__file__).resolve().parent
receipt=json.loads((root/'LOSSLESS_LEDGER_PACKING_RECEIPT.json').read_text())
name={'tasks':'TASK_LEDGER.csv','metrics':'METRIC_LEDGER.csv','actions':'NATIVE_ACTION_LEDGER.csv'}[a.table]
item=next(x for x in receipt['archives'] if x['csv_name']==name)
archive=root/item['gzip_name']
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4194304),b''):h.update(block)
    return h.hexdigest()
assert sha(archive)==item['compressed_sha256'],'compressed identity mismatch'
if a.verify:
    h=hashlib.sha256();size=0
    with gzip.open(archive,'rb') as f:
        for block in iter(lambda:f.read(4194304),b''):h.update(block);size+=len(block)
    assert h.hexdigest()==item['uncompressed_sha256'] and size==item['uncompressed_bytes']
    with gzip.open(archive,'rt',encoding='utf-8',newline='') as f:
        r=csv.DictReader(f);count=sum(1 for _ in r)
    assert count==item['decompressed_data_rows']
    print(json.dumps({'all_checks_passed':True,'table':a.table,'data_rows':count,'uncompressed_bytes':size,'sha256':h.hexdigest()},indent=2));sys.exit(0)
with gzip.open(archive,'rt',encoding='utf-8',newline='') as f:
    r=csv.DictReader(f);fields=a.fields.split(',') if a.fields else r.fieldnames
    assert set(fields)<=set(r.fieldnames),'unknown field requested'
    w=csv.DictWriter(sys.stdout,fieldnames=fields);w.writeheader()
    for index,row in enumerate(r):
        if a.limit and index>=a.limit:break
        w.writerow({k:row[k] for k in fields})
