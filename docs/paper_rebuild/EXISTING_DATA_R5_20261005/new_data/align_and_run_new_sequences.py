#!/usr/bin/env python3
"""Existing records: one fixed -1.1 s body alignment, frozen F03/F04 parameters."""
from pathlib import Path
import argparse,csv,json,math,shutil,subprocess,time
import numpy as np
import yaml
import run_new_sequences as base
from run_new_sequences import CODE,HERE,sha,save,table,body_inputs,imu_position_from_antenna,interpolate_a1,rotate_flu_to_ned,K_HV,SIGMA_HV,audited_open_records
OLD=base.STAGE/'ATTEMPT_02'
STAGE=base.STAGE/'ATTEMPT_03'
OFFSET=-1.1

def prepare():
 old=json.loads((OLD/'PLAN.json').read_text());oldseal=json.loads((OLD/'ALL_NATIVE_SEALED.json').read_text())
 assert oldseal['status']=='SEALED' and oldseal['reference_open_count']==0
 STAGE.mkdir(exist_ok=False);(STAGE/'CONFIGS').mkdir();(STAGE/'INPUTS').mkdir()
 shutil.copyfile(OLD/'SOLVER',STAGE/'SOLVER');(STAGE/'SOLVER').chmod(0o755)
 plan={**old,'script_sha256':sha(__file__),'offset_s':OFFSET,'alignment':'Effective input-event alignment from GNSS/IMU and GNSS/SDK velocity; not hardware clock calibration','zero_offset_plan_sha256':sha(OLD/'PLAN.json'),'zero_offset_native_seal_sha256':sha(OLD/'ALL_NATIVE_SEALED.json'),'runs':[],'sequences':{}}
 for seq,oldinfo in old['sequences'].items():
  info=dict(oldinfo)
  if info['status'].startswith('NO_INIT'):
   info['body_offset_s']=OFFSET;plan['sequences'][seq]=info
   for method in ['F03','F04']:plan['runs'].append({'run_id':'IMUFIX_R5_'+seq+'_'+method+'_T03','sequence':seq,'method':method,'status':info['status'],'native_invoked':False})
   continue
  out=STAGE/'INPUTS'/seq;out.mkdir();providers={}
  for name in ['GNSS18.gnss','DUAL_HEADING.csv','RAW_DOPPLER.csv']:
   origin=Path(oldinfo['providers'][name]['path']);assert sha(origin)==oldinfo['providers'][name]['sha256']
   target=out/name;shutil.copyfile(origin,target);assert sha(target)==sha(origin)
  yaw=list(csv.DictReader((out/'DUAL_HEADING.csv').open()))
  yaw=[{**v,'time':float(v['time']),'yaw_deg':float(v['yaw_deg'])}for v in yaw]
  a,imu,bi=body_inputs(Path(info['body']),out,yaw)
  assert sha(info['body'])==info['body_sha256']
  a[:,0]+=OFFSET;imu[:,0]+=OFFSET;np.savetxt(out/'IMU8.imu',imu,fmt='%.17g')
  rp=list(csv.DictReader((out/'GO2_RP.csv').open()))
  for v in rp:v['time']=float(v['time'])+OFFSET
  table(out/'GO2_RP.csv',rp)
  ys,support=interpolate_a1(a[:,0],[v['time']for v in yaw],[v['yaw_deg']for v in yaw])
  vel=np.zeros((len(a),2)) if ys is None else K_HV*rotate_flu_to_ned(a[:,10:13],a[:,7],a[:,8],ys)
  hv=[{'time':t,'vn':v[0],'ve':v[1],'vd':0,'std_vn':SIGMA_HV,'std_ve':SIGMA_HV,'std_vd':999,'valid':int(ok),'update_flag':bool(ok),'source_status':'active' if ok else 'inactive','confidence_level':'weak_auxiliary','reason_codes':'A1_supported' if ok else 'A1_unavailable'}for t,v,ok in zip(a[:,0],vel,support)]
  table(out/'GO2_HV.csv',hv)
  oldimu=np.loadtxt(oldinfo['providers']['IMU8.imu']['path'],ndmin=2)
  assert np.array_equal(imu[:,1:],oldimu[:,1:]) and np.max(np.abs(imu[:,0]-oldimu[:,0]-OFFSET))<1e-10
  gnss=np.loadtxt(out/'GNSS18.gnss',ndmin=2);start=max(a[999,0],gnss[0,0]);end=min(a[-1,0],gnss[-1,0]);init=next(v for v in gnss if start<=v[0]<=end and v[15] and v[17]);seed=imu[np.searchsorted(imu[:,0],init[0])];att=[0,0,float(init[13])]
  info.update(body_offset_s=OFFSET,expected_observed_epochs=len(a)-1,window_utc_day_s=[float(a[0,0]),float(a[-1,0])],native_window=[float(seed[0]),float(end)],initialization_gnss_time=float(init[0]),initialization_yaw_deg=att[2],input_gyro_bias=bi['gyro_bias'],hv_a1_reassociated_at_shifted_body_time=True)
  info['providers']={p.name:{'path':str(p),'sha256':sha(p)}for p in out.iterdir()if p.is_file()};plan['sequences'][seq]=info
  for method in ['F03','F04']:
   oldrun=next(r for r in old['runs']if r['sequence']==seq and r['method']==method);cfg=yaml.safe_load(Path(oldrun['config']).read_text());rid='IMUFIX_R5_'+seq+'_'+method+'_T03'
   changes=dict(run_id=rid,run_label=rid,imupath=str(out/'IMU8.imu'),gnsspath=str(out/'GNSS18.gnss'),outputpath=str(STAGE/'NATIVE'/rid),starttime=float(seed[0]),endtime=float(end),initpos=imu_position_from_antenna(init[1:4],att,cfg['antlever']),initatt=att,go2_attitude_prior_path=str(out/'GO2_RP.csv'),go2_horizontal_velocity_prior_path=str(out/'GO2_HV.csv'),raw_doppler_factor_path=str(out/'RAW_DOPPLER.csv'))
   cfg.update(changes);target=STAGE/'CONFIGS'/(rid+'.yaml');target.write_text(''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n'for k,v in cfg.items()))
   before=yaml.safe_load(Path(oldrun['config']).read_text());assert all(cfg[k]==v for k,v in before.items()if k not in changes)
   plan['runs'].append({'run_id':rid,'sequence':seq,'method':method,'status':'PREPARED','config':str(target),'config_sha256':sha(target),'changed_config_fields':list(changes)})
  print('ALIGNED_PREPARED',seq,'seed',seed[0],'body_offset',OFFSET,flush=True)
 save(STAGE/'PLAN.json',plan)

def native():
 plan=json.loads((STAGE/'PLAN.json').read_text());assert sha(__file__)==plan['script_sha256'];assert sha(STAGE/'SOLVER')==plan['binary_sha256'];records=[]
 for run in plan['runs']:
  rec=dict(run)
  if run['status']=='PREPARED':
   for v in plan['sequences'][run['sequence']]['providers'].values():assert sha(v['path'])==v['sha256']
   assert sha(run['config'])==run['config_sha256'];out=STAGE/'NATIVE'/run['run_id'];out.mkdir(parents=True,exist_ok=False)
   argv=['strace','-f','-qq','-s','4096','-e','trace=openat,execve','-o',str(out/'OPENAT.strace'),str(STAGE/'SOLVER'),'--config',run['config'],'--output-dir',str(out)]
   t=time.monotonic()
   with (out/'stdout.log').open('w')as stdout,(out/'stderr.log').open('w')as stderr:p=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=1200)
   opened=audited_open_records(out/'OPENAT.strace',CODE);refs=[v for v in opened if any(k in v['path']for k in ['trace_vrtk','poi_odometry','smooth_odometry'])]
   rec.update(exit_code=p.returncode,native_invoked=True,runtime_seconds=time.monotonic()-t,reference_open_count=len(refs),output_root=str(out),status='COMPLETED' if p.returncode==0 and not refs else 'FAILED_NATIVE')
   nav=np.loadtxt(out/'KF_GINS_Navresult.nav',comments='%',ndmin=2);rec.update(output_epochs=len(nav),all_finite=bool(np.isfinite(nav).all()))
   if not rec['all_finite']:rec['status']='FAILED_NONFINITE'
   rec['output_sha256']={p.name:sha(p)for p in out.iterdir()if p.is_file()};save(out/'RESULT.json',rec);print(run['run_id'],rec['status'],len(nav),flush=True)
  records.append(rec)
 save(STAGE/'ALL_NATIVE_SEALED.json',{'status':'SEALED','plan_sha256':sha(STAGE/'PLAN.json'),'script_sha256':sha(__file__),'runs':records,'reference_open_count':sum(r.get('reference_open_count',0)for r in records)})
 table(STAGE/'NATIVE_RESULTS.csv',[{k:r.get(k,'')for k in ['run_id','sequence','method','status','native_invoked','output_epochs','runtime_seconds','reference_open_count']}for r in records])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','native']);args=p.parse_args();{'prepare':prepare,'native':native}[args.phase]()
