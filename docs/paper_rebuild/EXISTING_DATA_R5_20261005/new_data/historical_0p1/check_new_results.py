"""Independent arithmetic check using saved error CSVs; no reference or pipeline imports."""
from pathlib import Path
import csv,hashlib,json,math
HERE=Path(__file__).resolve().parent
STAGE=Path('/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB/ATTEMPT_02')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=list(csv.DictReader((HERE/'RESULTS.csv').open()));checks=[];times={};maxdiff=0.
for row in rows:
 seq=row['sequence'];method=row['method']
 if row['status']!='COMPLETED':
  assert int(row['native_output_epochs'])==int(row['matched_epochs'])==0
  assert all(row[k]==''for k in ['H_RMSE_m','V_RMSE_m','3D_RMSE_m','yaw_RMSE_deg']);continue
 p=STAGE/'EVALUATION'/(seq+'_'+method+'_ERRORS.csv');data=list(csv.DictReader(p.open()));assert len(data)==int(row['matched_epochs']);times[seq,method]=[float(r['time'])for r in data]
 vals=[[float(r[k])for k in ['err_n_m','err_e_m','err_u_m','yaw_err_deg']]for r in data]
 independent={'H_RMSE_m':math.sqrt(math.fsum(n*n+e*e for n,e,u,y in vals)/len(vals)),'V_RMSE_m':math.sqrt(math.fsum(u*u for n,e,u,y in vals)/len(vals)),'3D_RMSE_m':math.sqrt(math.fsum(n*n+e*e+u*u for n,e,u,y in vals)/len(vals)),'yaw_RMSE_deg':math.sqrt(math.fsum(y*y for n,e,u,y in vals)/len(vals))}
 for key,v in independent.items():
  diff=abs(v-float(row[key]));maxdiff=max(maxdiff,diff);assert diff<1e-8;checks.append({'sequence':seq,'method':method,'metric':key,'independent':v,'published':float(row[key]),'abs_difference':diff})
 assert abs(float(row['coverage_fraction'])-len(vals)/int(row['expected_observed_epochs']))<1e-15
 assert float(row['first_time_utc_day_s'])==times[seq,method][0]and float(row['last_time_utc_day_s'])==times[seq,method][-1]
for seq in ['NMB1','NMB2','NMB3','NMB4']:assert times[seq,'F03']==times[seq,'F04']
receipt={'status':'PASS_ARITHMETIC_AND_PAIR_SUPPORT','metrics_checked':len(checks),'max_abs_difference':maxdiff,'all_four_pair_times_exact_equal':True,'eight_no_initialization_rows_not_zero_error':True,'results_sha256':sha(HERE/'RESULTS.csv'),'native_seal_sha256':sha(STAGE/'ALL_NATIVE_SEALED.json'),'review_script_sha256':sha(__file__),'raw_reference_opens':0,'native_calls':0,'evaluator_calls':0,'checks':checks}
(HERE/'NUMERICAL_CHECK.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='checks'}))
