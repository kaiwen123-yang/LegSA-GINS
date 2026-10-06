"""Independent saved-error arithmetic; no estimator, evaluator or reference imports."""
from pathlib import Path
import csv,hashlib,json,math
HERE=Path(__file__).resolve().parent
BASE=Path('/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
checks=[];stage_pins=[];maxdiff=0.
for attempt in ['ATTEMPT_02','ATTEMPT_03']:
 stage=BASE/attempt;primary=list(csv.DictReader((stage/'RESULTS_0P15.csv').open()));rows=list(csv.DictReader((stage/'RESULTS_ALL_SUPPORT_0P15.csv').open()));seal=json.loads((stage/'ALL_NATIVE_SEALED.json').read_text())
 assert len(primary)==16 and len(set(r['run_id']for r in primary))==16
 assert len(seal['runs'])==16 and sum(r['status']=='COMPLETED'for r in seal['runs'])==8 and seal['reference_open_count']==0
 times={};files={}
 for row in rows:
  seq=row['sequence'];method=row['method']
  if row['status']!='COMPLETED':
   assert int(row['native_output_epochs'])==int(row['matched_epochs'])==0
   assert all(row[k]==''for k in ['H_RMSE_m','V_RMSE_m','3D_RMSE_m','yaw_RMSE_deg']);continue
  p=stage/'EVALUATION_0P15'/(seq+'_'+method+'_ERRORS.csv')
  if (seq,method)not in files:files[seq,method]=list(csv.DictReader(p.open()))
  data=files[seq,method];assert len(data)==int(row['matched_epochs']);times[seq,method]=[float(r['time'])for r in data]
  vals=[[float(r[k])for k in ['err_n_m','err_e_m','err_u_m','yaw_err_deg']]for r in data]
  independent={'H_RMSE_m':math.sqrt(math.fsum(n*n+e*e for n,e,u,y in vals)/len(vals)),'V_RMSE_m':math.sqrt(math.fsum(u*u for n,e,u,y in vals)/len(vals)),'3D_RMSE_m':math.sqrt(math.fsum(n*n+e*e+u*u for n,e,u,y in vals)/len(vals)),'yaw_RMSE_deg':math.sqrt(math.fsum(y*y for n,e,u,y in vals)/len(vals))}
  for key,v in independent.items():
   diff=abs(v-float(row[key]));maxdiff=max(maxdiff,diff);assert diff<1e-8;checks.append({'attempt':attempt,'sequence':seq,'method':method,'support':row['support'],'metric':key,'independent':v,'published':float(row[key]),'abs_difference':diff})
  assert abs(float(row['coverage_fraction'])-len(vals)/int(row['expected_observed_epochs']))<1e-15
  assert float(row['first_time_utc_day_s'])==times[seq,method][0]and float(row['last_time_utc_day_s'])==times[seq,method][-1]
 for seq in ['NMB1','NMB2','NMB3','NMB4']:assert times[seq,'F03']==times[seq,'F04']
 stage_pins.append({'attempt':attempt,'native_seal_sha256':sha(stage/'ALL_NATIVE_SEALED.json'),'results_sha256':sha(stage/'RESULTS_0P15.csv'),'all_support_sha256':sha(stage/'RESULTS_ALL_SUPPORT_0P15.csv'),'evaluation_summary_sha256':sha(stage/'EVALUATION_SUMMARY_0P15.json')})
published=list(csv.DictReader((HERE/'RESULTS.csv').open()))
final=list(csv.DictReader((BASE/'ATTEMPT_03/RESULTS_0P15.csv').open()))
assert len(published)==len(final)==16
for left,right in zip(published,final):
 for k,v in right.items():assert left[k]==v,(left['run_id'],k)
receipt={'final_main_results_sha256':sha(HERE/'RESULTS.csv'),'final_main_transcription_exact':True,'status':'PASS_ARITHMETIC_AND_EXACT_PAIR_SUPPORT','metrics_checked':len(checks),'primary_metrics_checked':sum(r['support']=='COMMON_PAIR'for r in checks),'max_abs_difference':maxdiff,'all_eight_cohort_sequence_pair_times_exact_equal':True,'no_init_rows_have_blank_errors':True,'stage_pins':stage_pins,'review_script_sha256':sha(__file__),'raw_reference_opens':0,'native_calls':0,'evaluator_calls':0,'checks':checks}
(HERE/'NUMERICAL_CHECK_0P15.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='checks'}))
