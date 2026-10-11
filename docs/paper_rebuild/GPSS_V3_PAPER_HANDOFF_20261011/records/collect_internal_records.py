"""Read existing V3 ledgers/configuration records; write review tables only."""
from pathlib import Path
import csv, gzip, json
from collections import Counter

REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
STORY=REPO/'docs/paper_rebuild/V3_STORY_20261004'
OUT=Path(__file__).resolve().parent/'internal'
OUT.mkdir(exist_ok=True)
sources=[]

def readcsv(path):
    path=Path(path)
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    sources.append({'path':str(path),'read_depth':'FULL_CSV_PARSE','rows':len(rows),'purpose':'existing evidence recovery'})
    return rows

def writecsv(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

tasks=readcsv(STORY/'TASK_LEDGER.csv.gz')
metrics=readcsv(STORY/'METRIC_LEDGER.csv.gz')
actions=readcsv(STORY/'NATIVE_ACTION_LEDGER.csv.gz')
natural=readcsv(STORY/'NATURAL_METHOD_RESULTS.csv')
contexts=readcsv(STORY/'CONFIG_CONTEXT_STORY.csv')
model_path=STORY/'CONFIG_MODEL_FACTORS.json'
models=json.loads(model_path.read_text())
sources.append({'path':str(model_path),'read_depth':'FULL_JSON_PARSE','rows':len(models),'purpose':'configuration comparison'})
maps=readcsv(STORY/'METHOD_READER_NAME_MAP.csv')
module_pairs=readcsv(STORY/'SINGLE_MODULE_PAIRED_DIRECTION.csv')

group=Counter((x['domain'],x['internal_method_id'],x['native_status']) for x in tasks)
writecsv('RUN_COVERAGE.csv',[dict(domain=a,method=b,status=c,count=n) for (a,b,c),n in sorted(group.items())])
writecsv('NATURAL_RESULTS.csv',[x for x in natural if x['evaluator_contract']=='evaluator_contract_v3'])
writecsv('METHOD_CONFIGURATION_MAP.csv',maps)
writecsv('SINGLE_MODULE_RESULTS.csv',[x for x in module_pairs if x['evaluator_contract']=='evaluator_contract_v3'])
real={x['run_id']:x for x in tasks if x['data_mode']=='real_clean'}
writecsv('NATURAL_ACTIONS.csv',[x for x in actions if x['run_id'] in real])
bindings=[]
for rid,t in real.items():
    cp=Path(t['actual_v3_retained_config_path']); rp=Path(t['native_archive_receipt'])
    fields={}
    if cp.exists():
        for line in cp.read_text().splitlines():
            if ':' in line and not line.lstrip().startswith('#'):
                key,val=line.split(':',1);fields[key.strip()]=val.strip()
        sources.append({'path':str(cp),'read_depth':'FULL_CONFIG_TEXT','rows':len(fields),'purpose':'actual retained configuration'})
    if rp.exists():
        receipt=json.loads(rp.read_text())
        sources.append({'path':str(rp),'read_depth':'FULL_JSON_PARSE','rows':'','purpose':'native archive record'})
    manifest_path=rp.parent/'RUN_MANIFEST.json'
    manifest=json.loads(manifest_path.read_text())
    sources.append({'path':str(manifest_path),'read_depth':'FULL_JSON_PARSE','rows':'','purpose':'actual runtime role and active input roles'})
    timeline_path=rp.parent/'PORT_INPUT_TIMELINE_SNAPSHOT.json'
    timeline=json.loads(timeline_path.read_text())
    sources.append({'path':str(timeline_path),'read_depth':'FULL_JSON_PARSE','rows':'','purpose':'actual input and evaluation window'})
    e=Path(t['v3_error_series_location'])
    files=list(e.glob('*.csv*')) if e.exists() else []
    bindings.append({'run_id':rid,'sequence':t['sequence_id'],'method':t['internal_method_id'],
      'native_status':t['native_status'],'config_path':str(cp),'config_present':cp.exists(),
      'archive_receipt':str(rp),'receipt_present':rp.exists(),'error_series_directory':str(e),
      'series_files':json.dumps([str(f) for f in files]),'online_heading_config':fields.get('enable_dual_yaw',''),
      'runtime_role':fields.get('runtime_role',''),'actual_manifest_port_role':manifest.get('port_role'),
      'actual_imu_rows':timeline.get('imu_row_count'),'actual_gnss_rows_in_overlap':timeline.get('gnss_rows_in_overlap'),
      'native_nav_payload_retained':t['native_nav_payload_retained']})
writecsv('NATURAL_SOURCE_BINDINGS.csv',bindings)
diffs=[]
ctx={(x['sequence_id'],x['internal_method_id']):x for x in contexts}
for seq in ['BY2','BY2H','BY2O']:
    for lhs,rhs in [('F01','F03'),('F01','F04'),('A03','F04'),('A04','F04'),('A05','F04'),('A06','F04')]:
        a=models[ctx[seq,lhs]['config_model_id']]['values'];b=models[ctx[seq,rhs]['config_model_id']]['values']
        diff={k:{lhs:a.get(k),rhs:b.get(k)} for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)}
        diffs.append({'sequence':seq,'lhs':lhs,'rhs':rhs,'changed_fields':json.dumps(diff,ensure_ascii=False),
          'lhs_runtime_role':ctx[seq,lhs]['original_transport_runtime_role'],'rhs_runtime_role':ctx[seq,rhs]['original_transport_runtime_role']})
writecsv('CONFIGURATION_CONTRASTS.csv',diffs)

primary=[x for x in metrics if x['evaluator_contract']=='evaluator_contract_v3']
add=[x for x in primary if x['domain']=='ADDENDUM' and x['internal_method_id'] in ['F03','F04','A04','A05','A06','A07']]
cols=['run_id','internal_method_id','case_id','degradation_type_id','seed_index','data_mode','evaluation_status','horizontal_rmse_m','roll_rmse_deg','pitch_rmse_deg','yaw_rmse_deg','registered_table_path','registered_table_line']
writecsv('ADDENDUM_RELEVANT_RESULTS.csv',[{k:x[k] for k in cols} for x in add])
original_tables={}
checks=[]
for x in natural:
    if x['evaluator_contract']!='evaluator_contract_v3':continue
    path=x['registered_table_path']
    if path not in original_tables:original_tables[path]=readcsv(path)
    original=original_tables[path][int(x['registered_table_line'])-2]
    keys=['horizontal_rmse_m','up_rmse_m','position_3d_rmse_m','roll_rmse_deg','pitch_rmse_deg','yaw_rmse_deg']
    available=[k for k in keys if k in original]
    differences={k:[x[k],original[k]] for k in available if x[k]!=original[k]}
    checks.append({'run_id':x['run_id'],'source':path,'line':x['registered_table_line'],'metrics_checked':len(available),'differences':json.dumps(differences)})
writecsv('SOURCE_ROW_CHECKS.csv',checks)
writecsv('SOURCES_READ.csv',sources)
summary={'task_rows':len(tasks),'unique_runs':len({x['run_id'] for x in tasks}),'status_counts':dict(Counter(x['native_status'] for x in tasks)),
 'domain_counts':dict(Counter(x['domain'] for x in tasks)),'metric_rows_two_contracts':len(metrics),
 'primary_contract_status':dict(Counter(x['evaluation_status'] for x in primary)),
 'natural_results':len(real),'natural_configs_present':sum(x['config_present'] for x in bindings),
 'natural_receipts_present':sum(x['receipt_present'] for x in bindings),'configuration_comparisons':len(diffs),
 'original_natural_rows_checked':len(checks),'source_row_differences':sum(x['differences']!='{}' for x in checks),
 'scientific_solver_calls':0,'scientific_evaluator_calls':0,'provider_calls':0}
(OUT/'RECOVERY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
