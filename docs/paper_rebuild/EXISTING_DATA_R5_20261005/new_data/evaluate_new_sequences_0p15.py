#!/usr/bin/env python3
"""Offline-only paired error calculation for the eight existing records."""
from pathlib import Path
import argparse,csv,hashlib,io,json,math,zipfile
import numpy as np
import yaml
from legsa_gins.paper_rebuild.clean5_parity.evaluation import transform_nav
from run_new_sequences import CODE,HERE,PROFILE,RAW,DAY,sha,save,table
STAGE=Path('/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB/ATTEMPT_03')
REFERENCE_BRACKET_LIMIT_S=0.15
ZIP=RAW/'fixpositon数据/vrtk2_a87c6e_2026-01-05-11-16-59_minimal.zip'

def xyz(llh):
 lat,lon=np.deg2rad(llh[:,0]),np.deg2rad(llh[:,1]);h=llh[:,2];sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon);N=6378137/np.sqrt(1-6.6943799901413165e-3*sl*sl)
 return np.column_stack(((N+h)*cl*co,(N+h)*cl*so,(N*(1-6.6943799901413165e-3)+h)*sl))

def metric(t,e,denom,native_count,identity):
 row={**identity,'expected_observed_epochs':denom,'native_output_epochs':native_count,'matched_epochs':len(t),'coverage_fraction':len(t)/denom,'first_time_utc_day_s':float(t[0])if len(t)else None,'last_time_utc_day_s':float(t[-1])if len(t)else None}
 for k,v in [('H_RMSE_m',np.hypot(e[:,0],e[:,1])),('V_RMSE_m',e[:,2]),('3D_RMSE_m',np.linalg.norm(e[:,:3],axis=1)),('yaw_RMSE_deg',e[:,3])]:row[k]=float(np.sqrt(np.mean(v*v)))if len(v)else None
 return row

def main():
 seal_path=STAGE/'ALL_NATIVE_SEALED.json';sealed=json.loads(seal_path.read_text());plan=json.loads((STAGE/'PLAN.json').read_text())
 assert sealed['status']=='SEALED' and sealed['plan_sha256']==sha(STAGE/'PLAN.json') and len(sealed['runs'])==16 and sealed['reference_open_count']==0
 assert sum(r['status']=='COMPLETED'for r in sealed['runs'])==8
 runtime=[];vectors={'antlever':'antlever_m','initpos':'init_position_geodetic_deg_m','initvel':'init_velocity_ned_mps','initatt':'init_attitude_deg','initgyrbias':'init_gyro_bias_deg_h','initaccbias':'init_accel_bias_mgal','initgyrscale':'init_gyro_scale_ppm','initaccscale':'init_accel_scale_ppm','initposstd':'init_position_std_m','initvelstd':'init_velocity_std_mps','initattstd':'init_attitude_std_deg','initbgstd':'init_gyro_bias_std_deg_h','initbastd':'init_accel_bias_std_mgal','initsgstd':'init_gyro_scale_std_ppm','initsastd':'init_accel_scale_std_ppm','arw':'angle_random_walk_deg_sqrt_h','vrw':'velocity_random_walk_mps_sqrt_h','gbstd':'gyro_bias_std_deg_h','abstd':'accel_bias_std_mgal','gsstd':'gyro_scale_std_ppm','asstd':'accel_scale_std_ppm'}
 for r in sealed['runs']:
  if r['status']!='COMPLETED':continue
  root=Path(r['output_root'])
  for k,v in r['output_sha256'].items():assert sha(root/k)==v
  cfg=yaml.safe_load(Path(r['config']).read_text());actual=json.loads((root/'RUN_MANIFEST.json').read_text())
  for k,v in vectors.items():
   err=float(np.max(np.abs(np.asarray(cfg[k])-actual[v])));assert err<1e-10
   runtime.append({'run_id':r['run_id'],'config_field':k,'manifest_field':v,'max_abs_difference':err})
 table(STAGE/'RUNTIME_PARAMETER_CHECK_0P15.csv',runtime)
 rows=[];refs=[];evidence=[]
 with zipfile.ZipFile(ZIP)as z:
  for seq,info in plan['sequences'].items():
   runs=[r for r in sealed['runs']if r['sequence']==seq]
   if not info['status'].startswith('NO_INIT'):
    info['expected_observed_epochs']=len(np.loadtxt(info['providers']['IMU8.imu']['path'],ndmin=2))
   if info['status'].startswith('NO_INIT'):
    for r in runs:rows.append(metric(np.array([]),np.empty((0,4)),info['expected_observed_epochs'],0,{'sequence':seq,'method':r['method'],'run_id':r['run_id'],'status':r['status'],'support':'COMMON_PAIR'}))
    continue
   member=info['receiver_folder']+'/trace_'+info['receiver_folder']+'.csv'
   payload=z.read(member);raw=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))));ref=np.asarray([[float(r[k])for k in ['time','lat','lon','height','roll','pitch','yaw']]for r in raw]);good=np.isfinite(ref).all(axis=1);ref=ref[good]
   assert np.min(ref[:,0])>1e9;ref[:,0]-=DAY;ref=ref[np.argsort(ref[:,0],kind='stable')];dup=np.r_[False,np.diff(ref[:,0])==0];ref=ref[~dup];assert np.all(np.diff(ref[:,0])>0)
   refs.append({'sequence':seq,'member':member,'sha256':hashlib.sha256(payload).hexdigest(),'raw_rows':len(raw),'clean_unique_rows':len(ref),'duplicate_rows':int(np.sum(dup)),'first_utc_day_s':float(ref[0,0]),'last_utc_day_s':float(ref[-1,0]),'max_gap_s':float(np.max(np.diff(ref[:,0]))),'raw_reference_payload_opens':1})
   yaws=list(csv.DictReader(Path(info['providers']['DUAL_HEADING.csv']['path']).open()));baseline=float(np.median([float(v['baseline_m'])for v in yaws]));truthxyz=xyz(ref[:,1:4]);lat,lon=np.deg2rad(ref[0,1:3]);sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon);M=np.array([[-sl*co,-sl*so,cl],[-so,co,0],[cl*co,cl*so,sl]])
   errors={};navs={}
   for r in runs:
    nav=np.loadtxt(Path(r['output_root'])/'KF_GINS_Navresult.nav',comments='%',ndmin=2);point=transform_nav(nav,baseline);t=point[:,1];j=np.clip(np.searchsorted(ref[:,0],t,side='right'),1,len(ref)-1);gap=ref[j,0]-ref[j-1,0]
    match=(t>=ref[0,0])&(t<=ref[-1,0])&(gap<=REFERENCE_BRACKET_LIMIT_S);tt=t[match];estimated=xyz(point[match,2:5]);truth=np.column_stack([np.interp(tt,ref[:,0],truthxyz[:,i])for i in range(3)]);neu=(estimated-truth)@M.T
    y=np.interp(tt,ref[:,0],np.unwrap(np.deg2rad(90-ref[:,6])));dy=(point[match,10]-np.rad2deg(y)+180)%360-180;err=np.column_stack((neu,dy));errors[r['method']]=(tt,err,r);navs[r['method']]=nav
   common=np.intersect1d(errors['F03'][0],errors['F04'][0]);assert len(common)>0
   for method,(tt,err,r)in errors.items():
    own=metric(tt,err,info['expected_observed_epochs'],len(navs[method]),{'sequence':seq,'method':method,'run_id':r['run_id'],'status':'COMPLETED','support':'OWN'});rows.append(own)
    index=np.searchsorted(tt,common);paired=metric(common,err[index],info['expected_observed_epochs'],len(navs[method]),{'sequence':seq,'method':method,'run_id':r['run_id'],'status':'COMPLETED','support':'COMMON_PAIR'});rows.append(paired)
    target=STAGE/'EVALUATION_0P15'/(seq+'_'+method+'_ERRORS.csv');table(target,[{'time':t,'err_n_m':v[0],'err_e_m':v[1],'err_u_m':v[2],'yaw_err_deg':v[3]}for t,v in zip(tt,err)])
    evidence.append({'sequence':seq,'method':method,'error_csv':str(target),'sha256':sha(target),'point_transform_lever_body_m':[.03,.03-.5*baseline,-.3],'source_baseline_median_m':baseline,'reference_yaw':'NED = 90deg - recorded ENU yaw','reference_interp':'ECEF XYZ linear; angular unwrap; bracket <=0.15s (20 Hz nominal, three periods); no endpoint extrapolation','init_time_utc_day_s':info['native_window'][0],'native_first':float(navs[method][0,1]),'native_last':float(navs[method][-1,1])})
 table(STAGE/'RESULTS_ALL_SUPPORT_0P15.csv',rows);primary=[r for r in rows if r['support']=='COMMON_PAIR'];table(STAGE/'RESULTS_0P15.csv',primary)
 save(STAGE/'EVALUATION_SUMMARY_0P15.json',{'native_seal_sha256':sha(seal_path),'evaluator_script_sha256':sha(__file__),'reference_opens':refs,'point_time_conventions':evidence,'rows':rows,'runtime_parameter_checks':len(runtime),'max_runtime_parameter_abs_diff':max(r['max_abs_difference']for r in runtime),'original_V3_changed':False,'native_invocations_this_adopted_stage':8,'adopted_native_invocations':8,'reference_bracket_limit_s':REFERENCE_BRACKET_LIMIT_S,'body_offset_s':plan['offset_s'],'no_init_registered':8})
 for row in primary:print(row,flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,default=STAGE);args=ap.parse_args();STAGE=args.stage;main()
