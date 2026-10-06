#!/usr/bin/env python3
"""Date grouping only. No new stream parsing or claims of independent routes."""
from pathlib import Path
import argparse,csv,datetime,json,hashlib
p=argparse.ArgumentParser()
for k in ['main-scope','body-summary','out']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();rows=[]
for v in json.loads(a.main_scope.read_text())['rows']:
 t=lambda k:datetime.datetime.fromtimestamp(v[k],datetime.timezone.utc)
 rows.append({'sequence':v['sequence'],'date_UTC':t('window_start_unix').date().isoformat(),'start_UTC':t('window_start_unix').isoformat(),'end_UTC':t('window_end_unix').isoformat(),'duration_s':v['window_end_unix']-v['window_start_unix'],'scope':'main preregistered analysis window, not complete file','route_proven':False,'unseen_holdout_proven':False,'source':'RESEARCH_AUDIT_20261006/LEG_INPUT_FEASIBILITY.json'})
for v in csv.DictReader(a.body_summary.open()):
 rows.append({'sequence':v['file'][:-4].upper(),'date_UTC':v['first_utc_interpretation'][:10],'start_UTC':v['first_utc_interpretation'],'end_UTC':v['last_utc_interpretation'],'duration_s':float(v['elapsed_s']),'scope':'complete body file time span','route_proven':False,'unseen_holdout_proven':False,'source':'raw_audit/BODY_AND_SESSION.csv'})
with a.out.open('w',newline='') as f:w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
print('DATE_GROUPS',len(set(r['date_UTC'] for r in rows)))
