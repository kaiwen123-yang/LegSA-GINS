#!/usr/bin/env python3
"""Read saved pilot artifacts only; no estimator, evaluator or raw/reference access."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 plan=json.loads((a.stage/'PLAN.json').read_text());seal=json.loads((a.stage/'ALL_NATIVE_SEALED.json').read_text())
 done=json.loads((a.stage/'EVALUATION_COMPLETE.json').read_text());assert done['evaluations']==12
 rows=pd.read_csv(a.stage/'PILOT_RESULTS.csv');records=seal['records'];info=[];native=[]
 for r in records:
  root=a.stage/'NATIVE'/r['run_id'];err=pd.read_csv(a.stage/'EVALUATION'/r['run_id']/'FROZEN_EVALUATOR/error_series.csv')
  t=err.time.to_numpy();domains={'full':np.ones(len(t),bool)}
  if r['outage']:
   start,end=r['outage'];domains.update(outage=(t>=start)&(t<end),recovery_0_5=(t>end)&(t<=end+5))
  for domain,mask in domains.items():
   q=rows[(rows.run_id==r['run_id'])&(rows.domain==domain)];assert len(q)==1 and q.iloc[0].epochs==mask.sum()
   for col,key in [('horizontal_err_m','H_RMSE_m'),('err_u_m','V_RMSE_m'),('position_3d_err_m','D3_RMSE_m'),('yaw_err_deg','yaw_RMSE_deg')]:
    vals=err[col].to_numpy()[mask];assert abs(float(np.sqrt(np.mean(vals*vals)))-float(q.iloc[0][key]))<1e-10
   info.append({'run_id':r['run_id'],'domain':domain,'first_matched_time_s':t[mask][0],'last_matched_time_s':t[mask][-1],
                'registered_fault_end_s':r['outage'][1] if r['outage'] else None})
  evaluation=json.loads((a.stage/'EVALUATION'/r['run_id']/'EVALUATOR_RESULT.json').read_text());assert evaluation['audit']['trace_open_count']==1 and evaluation['audit']['passed'] and evaluation['capture']['consistency']['passed']
  events=pd.read_csv(root/'AID_EVENTS.csv');trace=pd.read_csv(root/'SOURCE_AWARE_WEIGHT_TRACE.csv')
  nr={'run_id':r['run_id'],'case':r['case'],'mode':r['mode'],'native_seconds':r['runtime_seconds'],'output_rows':r['output_rows'],
      'reference_reads_offline':evaluation['audit']['trace_open_count'],'offline_consistency_passed':evaluation['capture']['consistency']['passed'],'reference_reads_online':r['online_trace_reads'],'nav_sha256':r['nav_sha256'],'std_sha256':r['std_sha256'],
      'independent_tick_count':len(events),'independent_rp_accepted':int(events.rp_accepted.sum()),'independent_hv_accepted':int(events.hv_accepted.sum()),
      'full_total_rp_accepted':int(trace.loc[trace.source_id=='go2_attitude_roll_pitch','accepted'].sum()),
      'full_total_hv_accepted':int(trace.loc[trace.source_id=='go2_horizontal_velocity','accepted'].sum()),
      'covariance_samples':r['covariance']['samples'],'min_active_P_eigenvalue':r['covariance']['min_active_eigen'],'max_relative_asymmetry':r['covariance']['relative_asymmetry'],
      'prior_diagnostic_parity':r.get('prior_diagnostic_parity',{})}
  saved=np.loadtxt(root/'STATE_COVARIANCE_SUPPORT.csv',delimiter=',',skiprows=1,ndmin=2);cov=saved[:,16:].reshape(-1,21,21)
  nr['six_fixed_scale_rows_cols_zero']=bool(np.all(cov[:,15:,:]==0) and np.all(cov[:,:,15:]==0));assert nr['six_fixed_scale_rows_cols_zero']
  for kind,age in [('rp',.02)]+([('hv',.08)] if r['mode']==2 else []):
   accepted=events[events[kind+'_accepted']>0];dt=accepted.state_time-accepted[kind+'_sample_time']
   nr['independent_'+kind+'_max_sample_age_s']=float(dt.max()) if len(dt) else None
   nr['independent_'+kind+'_timestamps_unique']=bool(accepted[kind+'_sample_time'].is_unique)
   if len(dt):assert (dt>=0).all() and (dt<=age+1e-9).all()
  if r['outage']:
   start,end=r['outage'];ev=events[(events.state_time>=start)&(events.state_time<end)]
   nr['fault_independent_rp_accepted']=int(ev.rp_accepted.sum());nr['fault_independent_hv_accepted']=int(ev.hv_accepted.sum())
   nr['fault_covariance_samples']=int(((saved[:,0]>=start)&(saved[:,0]<end)).sum())
  native.append(nr)
 result=rows.merge(pd.DataFrame(info),on=['run_id','domain'],validate='one_to_one')
 # Signed convention: positive clean loss is worse; positive fault reduction is better.
 def pick(case,mode,domain):return result[(result.case==case)&(result['mode']==mode)&(result.domain==domain)].iloc[0]
 clean0,clean2=pick('C00',0,'full'),pick('C00',2,'full')
 bad0,bad1,bad2=[pick('D61_20s_seed_00',m,'outage') for m in range(3)]
 clean_h_loss=float(clean2.H_RMSE_m-clean0.H_RMSE_m);clean_yaw_loss=float(clean2.yaw_RMSE_deg-clean0.yaw_RMSE_deg)
 reduction=float(1-bad2.H_RMSE_m/bad0.H_RMSE_m)
 by={(r['case'],r['mode']):r for r in records}
 no_records={str(m):{'nav_equal':by[('D61_20s_seed_00',m)]['nav_sha256']==by[('D61_NO_RECORDS',m)]['nav_sha256'],
                     'std_equal':by[('D61_20s_seed_00',m)]['std_sha256']==by[('D61_NO_RECORDS',m)]['std_sha256']} for m in range(3)}
 summary={'status':'COMPLETE_PILOT_NOT_ORIGINAL_V3','execution_commit':records[0]['execution_commit'],'binary_sha256':plan['binary_sha256'],
    'plan_sha256':sha(a.stage/'PLAN.json'),'native_seal_sha256':sha(a.stage/'ALL_NATIVE_SEALED.json'),
    'solver_binary_invocations':14,'pre_input_config_rejections':2,'scientific_native_completed':12,'offline_evaluations_completed':12,
    'native_config_checker_processes':1,'native_config_checker_configurations':12,'native_unit_test_processes':2,
    'evaluator_sha256':sha(evaluation['audit']['evaluator_argv'][1]),'offline_reference_reads':sum(r['reference_reads_offline'] for r in native),'online_reference_reads':sum(r['online_trace_reads'] for r in records),'offline_reference_role':'commercial fused reference with shared GNSS; not independent truth',
    'scientific_cases':4,'registered_gnss_outage_s':[196.2,216.2],'fault_terminal_role':'last actual matched epoch strictly before 216.2; not interpolated exact endpoint',
    'same_support_each_case':all(len(set(r['time_keys_sha256'] for r in records if r['case']==case))==1 for case in set(r['case'] for r in records)),
    'invalid_vs_absent_gnss_payload_identity':no_records,'native_rows':native,
    'engineering_criteria':{'clean_h_loss_m':clean_h_loss,'clean_h_tolerance_m':max(.02,.2*float(clean0.H_RMSE_m)),'clean_h_pass':clean_h_loss<=max(.02,.2*float(clean0.H_RMSE_m)),
       'clean_yaw_loss_deg':clean_yaw_loss,'clean_yaw_pass':clean_yaw_loss<=1.,'D61_fault_h_reduction_fraction':reduction,'D61_fault_h_reduction_pass':reduction>=.5,
       'M1_RP_only_D61_H_RMSE_m':float(bad1.H_RMSE_m),'M2_RP_bodyHV_D61_H_RMSE_m':float(bad2.H_RMSE_m),'scope':'engineering prioritization, one fixed placement, not statistical significance or safety certification'},
    'runtime_environment':{'os':'Ubuntu 22.04.5','kernel':'6.6.87.2-microsoft-standard-WSL2','python':'3.10.12','gcc':'11.4.0','cmake':'3.22.1','numpy':'1.26.4','pandas':'2.2.3','pyyaml':'6.0.3'},
    'payload_alias':'<WSL_SCRATCH>/research_audit_20261006/ATTEMPT_03'}
 a.out.mkdir(parents=True,exist_ok=True);result.to_csv(a.out/'PILOT_RESULTS.csv',index=False)
 (a.out/'PILOT_EXECUTION_SUMMARY.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps(summary['engineering_criteria'],indent=2))
 print(result[['case','mode','domain','H_RMSE_m','V_RMSE_m','yaw_RMSE_deg','last_matched_time_s']].to_string(index=False))
if __name__=='__main__':main()
