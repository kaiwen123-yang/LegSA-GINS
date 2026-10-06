from pathlib import Path
import csv,gzip,json,hashlib,collections,datetime,math,shutil
import numpy as np
C=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001');B=C/'docs/paper_rebuild/V3_STORY_20261004';X=Path('/mnt/g/LegSA-GINS-project/修复_20261004/V3_STORY_SOURCE_READ_03')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def j(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def wc(name,rows):
 rows=list(rows);assert rows; p=B/name;assert not p.exists();p.parent.mkdir(exist_ok=True)
 with p.open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return len(rows)
before={str(p.relative_to(B)):sha(p) for p in B.iterdir() if p.is_file() and p.name not in ['TASK_LEDGER.csv','METRIC_LEDGER.csv','NATIVE_ACTION_LEDGER.csv']};assert len(before)==29
with gzip.open(B/'TASK_LEDGER.csv.gz','rt') as f:tasks=list(csv.DictReader(f))
with gzip.open(B/'METRIC_LEDGER.csv.gz','rt') as f:metrics=list(csv.DictReader(f))
cases=list(csv.DictReader((B/'CASE_LEDGER.csv').open()));names={r['internal_method_id']:r['paper_reader_name'] for r in csv.DictReader((B/'METHOD_READER_NAME_MAP.csv').open())}
idx={r['relative_path']:r for r in csv.DictReader((B/'AGGREGATE_SOURCE_INDEX.csv').open())};count={};pins={};checks=[]
for version in ['V3','V2']:
 mr=[r for r in metrics if r['evaluator_contract']=='evaluator_contract_'+version.lower()];assert len(mr)==6468
 for base,domain,groupfield,subset in [('CORE_541_SUMMARY','CORE',None,False),('CORE_541_FAMILY_SUMMARY','CORE','case_family',False),('CORE_541_TYPE_SUMMARY','CORE','degradation_id',False),('SUBSET61_SUMMARY','CORE',None,True),('ADDENDUM_SUMMARY','ADDENDUM',None,False),('ADDENDUM_FAMILY_SUMMARY','ADDENDUM','case_family',False)]:
  n=base+'_'+version+'.csv';p=Path(idx[n]['actual_path']);assert sha(p)==idx[n]['sha256'];pins[str(p)]=sha(p);rr=list(csv.DictReader(p.open()));groups=collections.defaultdict(list)
  for r in mr:
   if r['domain']!=domain or (subset and not(r['case_id']=='C00_clean_normal' or r['case_id'].endswith('seed_00'))):continue
   key=(r['internal_method_id'],r[groupfield] if groupfield and groupfield in r else r['degradation_type_id'] if groupfield=='degradation_id' else None);groups[key].append(r)
  for line,r in enumerate(rr,2):
   g=groups[r['method_id'],r[groupfield] if groupfield else None];complete=[a for a in g if a['evaluation_status']=='COMPLETED'];v=np.asarray([float(a[r['metric']]) for a in complete],float);assert np.isfinite(v).all();tail=math.ceil(.05*len(v));fail=sum(a['evaluation_status']!='COMPLETED' for a in g)
   expected={'registered_count':len(g),'finite_count':len(v),'algorithm_failure_count':fail,'unavailable_count':0,'not_applicable_count':0,'failure_rate':fail/len(g),'mean':np.mean(v) if len(v) else None,'median':np.median(v) if len(v) else None,'p95':np.percentile(v,95) if len(v) else None,'maximum':np.max(v) if len(v) else None,'worst_5pct_mean':np.mean(np.sort(v)[-tail:]) if tail else None,'worst_5pct_count':tail}
   for k,val in expected.items():
    if val is None:assert r[k] in ['','UNAVAILABLE'],(n,line,k,r[k])
    else:assert math.isclose(float(r[k]),float(val),rel_tol=2e-14,abs_tol=1e-13),(n,line,k,r[k],val)
   checks.append({'table':n,'source_line':line,'method_id':r['method_id'],'group':r.get(groupfield,'ALL') if groupfield else 'ALL','metric':r['metric'],'stat_fields_checked':len(expected),'passed':True})
  q=B/'RESULT_SUMMARIES'/n;assert not q.exists();q.parent.mkdir(exist_ok=True);q.write_bytes(p.read_bytes());assert sha(q)==sha(p);count['RESULT_SUMMARIES/'+n]=len(rr)
# Other complete frozen small table copies, exact original bytes; machine token read only.
for n in ['T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv','FAILURE_COMPARISON.csv','BY2O_SEGMENT_TABLE.csv','PAIRWISE_SUMMARY_V3.csv','PAIRWISE_SUMMARY_V2.csv']:
 p=Path(idx[n]['actual_path']);assert sha(p)==idx[n]['sha256'];pins[str(p)]=sha(p);rr=list(csv.DictReader(p.open()));q=B/'RESULT_SUMMARIES'/n;assert not q.exists();q.write_bytes(p.read_bytes());assert sha(q)==sha(p);count['RESULT_SUMMARIES/'+n]=len(rr)
# 68 condition types include 61 CORE, five ADD duration types, two extra natural sequences.
cgroups=collections.defaultdict(list)
for r in cases:
 typ=('C00' if r['case_id']=='C00_clean_normal' else r['degradation_type_id']) if r['domain']=='CORE' else r['case_id'].rsplit('_seed_',1)[0] if r['domain']=='ADDENDUM' else r['sequence_id']+'_C00'
 cgroups[r['sequence_id'],r['domain'],typ].append(r)
assert len(cgroups)==68
catalog=[]
for (seq,domain,typ),rr in sorted(cgroups.items()):
 meta=[json.loads(r['case_meta_json']) for r in rr];ids={r['case_id'] for r in rr};tt=[t for t in tasks if t['sequence_id']==seq and t['domain']==domain and t['case_id'] in ids];assert len(tt)==11*len(rr)
 catalog.append({'sequence_id':seq,'domain':domain,'condition_type':typ,'case_family':rr[0]['case_family'],'description':meta[0].get('degradation_type_name',meta[0].get('case_family','natural_sequence')),'registered_cells':len(rr),'registered_methods':11,'native_tasks':len(tt),'completed':sum(t['native_status']=='COMPLETED' for t in tt),'diverged':sum(t['native_status']=='ALGORITHM_FAILURE_DIVERGED' for t in tt),'no_valid_heading':sum(t['native_status']=='ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT' for t in tt),'data_modes_json':j(sorted({r['data_mode'] for r in rr})),'case_ids_json':j(sorted(ids)),'seed_values_json':j([m.get('seed_value','') for m in meta]),'source_declared_independent_realizations':sum(str(m.get('independent_realization',False)).lower()=='true' for m in meta),'exact_parameters_by_cell_json':j({r['case_id']:m for r,m in zip(rr,meta)}),'scientific_interpretation':'Actual registered frozen exposures. Nine placements/draws are controlled descriptive conditions, not nine independent real traversals.'})
count['CASE_TYPE_STORY.csv']=wc('CASE_TYPE_STORY.csv',catalog)
out=[]
for s,d in [('BY2','CORE'),('BY2','ADDENDUM'),('BY2H','SEQUENCE'),('BY2O','SEQUENCE'),('ALL','ALL')]:
 for m in names:
  tt=[r for r in tasks if r['internal_method_id']==m and (d=='ALL' or r['domain']==d and r['sequence_id']==s)];assert tt
  out.append({'sequence_id':s,'domain':d,'paper_reader_name':names[m],'internal_method_id':m,'registered_count':len(tt),'completed':sum(r['native_status']=='COMPLETED' for r in tt),'diverged':sum(r['native_status']=='ALGORITHM_FAILURE_DIVERGED' for r in tt),'no_valid_heading':sum(r['native_status']=='ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT' for r in tt),'v3_v2_evaluation_slots':2*len(tt),'admitted_slots':2*sum(r['native_status']=='COMPLETED' for r in tt),'metricless_failure_slots':2*sum(r['native_status']!='COMPLETED' for r in tt),'failed_case_ids_json':j(sorted(r['case_id'] for r in tt if r['native_status']!='COMPLETED')),'failure_denominator':'all registered tasks; conditional numerical summary uses completed finite tasks only'})
count['FULL_MATRIX_OUTCOME_LEDGER.csv']=wc('FULL_MATRIX_OUTCOME_LEDGER.csv',out)
count['SUMMARY_ARITHMETIC_CHECKS.csv']=wc('SUMMARY_ARITHMETIC_CHECKS.csv',checks)
# Case-level paired directions are descriptive counts, no new tests, confidence intervals or evaluator.
pp=[]
for version in ['V3','V2']:
 mr=[r for r in metrics if r['domain']=='CORE' and r['evaluator_contract']=='evaluator_contract_'+version.lower()];mi={(r['case_id'],r['internal_method_id']):r for r in mr}
 for comparison,candidate,reference in [('LegSA-GINS_vs_without_RD','F04','A03'),('LegSA-GINS_vs_without_SA','F04','A04'),('LegSA-GINS_vs_without_RP','F04','A05'),('LegSA-GINS_vs_without_HV','F04','A06')]:
  for field in ['horizontal_rmse_m','position_3d_rmse_m','up_rmse_m','yaw_rmse_deg','yaw_p95_absolute_deg','roll_rmse_deg','pitch_rmse_deg']:
   ds=[];nf=rf=both=0
   for case in sorted({r['case_id'] for r in mr}):
    a,b=mi[case,candidate],mi[case,reference];ac=a['evaluation_status']=='COMPLETED';bc=b['evaluation_status']=='COMPLETED'
    if ac and bc:ds.append(float(a[field])-float(b[field]))
    elif ac:nf+=1
    elif bc:rf+=1
    else:both+=1
   pp.append({'evaluator_contract':'evaluator_contract_'+version.lower(),'comparison':comparison,'metric':field,'registered_case_count':541,'paired_completed_count':len(ds),'full_completed_ablation_failed':nf,'full_failed_ablation_completed':rf,'both_failed':both,'full_lower_count':sum(d < -1e-12 for d in ds),'tie_count':sum(abs(d)<=1e-12 for d in ds),'full_higher_count':sum(d > 1e-12 for d in ds),'mean_full_minus_ablation':float(np.mean(ds)),'median_full_minus_ablation':float(np.median(ds)),'interpretation':'Same case-key conditional paired descriptive direction. Failure membership retained; cases reuse one recorded route; no independent-realization p-value claim.'})
count['SINGLE_MODULE_PAIRED_DIRECTION.csv']=wc('SINGLE_MODULE_PAIRED_DIRECTION.csv',pp)
# Reader-side metadata only. Original 29 files and all source summaries immutable.
assert all(sha(B/n)==h for n,h in before.items());assert all(sha(p)==h for p,h in pins.items())
rec={'schema':'v3_story.third_block.data.v1','captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_checks_passed':True,'original_science_freeze':'7d43b9af26120ed5dde21f53e515386361072ba6','previous_blocks_commits':['baf4e9157c7b82d611271f15ae9b7e68f3014ab3','db4d106427f307db47fe7f018ba36c107c11098f'],'prior29_before_pins':before,'prior29_after_pins':{n:sha(B/n) for n in before},'source_before_pins':pins,'source_after_pins':{p:sha(p) for p in pins},'statistic_rows_checked':len(checks),'statistic_scalar_fields_checked':sum(r['stat_fields_checked'] for r in checks),'statistic_tolerance':{'relative':2e-14,'absolute':1e-13},'copied_summaries_exact_bytes':True,'output_rows':count,'science_calls':{'native':0,'evaluator':0,'provider_generator':0,'raw_or_trace_payload_reads':0,'legsa_package_imports':0},'reader_helper_sha256':sha(__file__),'limitations':['All structured fields checked by machine; semantic reads separately recorded.','No new native result, evaluator result, fault injection, failure reclassification or confidence-interval computation.','Cross-chain FC01 unified classification remains unexecuted; original matrix own outcomes are preserved.']}
p=B/'THIRD_BLOCK_DATA_RECEIPT.json';assert not p.exists();p.write_text(json.dumps(rec,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q=B/'build_third_story_block.py';assert not q.exists();q.write_bytes(Path(__file__).read_bytes())
print('THIRD_DATA_PASS',count,'checks',len(checks),'scalarfields',sum(r['stat_fields_checked'] for r in checks))
