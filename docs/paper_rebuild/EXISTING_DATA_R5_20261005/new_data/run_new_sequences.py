#!/usr/bin/env python3
"""Local eight-record transfer: prepare, native, then offline evaluation."""
from pathlib import Path
import argparse,ast,csv,datetime,hashlib,importlib.util,json,math,shutil,struct,subprocess,time,zipfile
import numpy as np
import yaml
from legsa_gins.input_generation.imu_txt_builder import euler_rpy_deg_to_matrix
from legsa_gins.paper_rebuild.clean6_sensor_v21.providers import interpolate_a1,rotate_flu_to_ned,K_HV,SIGMA_HV,SIGMA_YAW
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import ecef_to_geodetic
from legsa_gins.paper_rebuild.imu_contract_repair import imu_position_from_antenna
from legsa_gins.paper_rebuild import formal_generation as fg
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
HERE=Path(__file__).resolve().parent
PROFILE=CODE/'docs/paper_rebuild/TIM_EVIDENCE_20261005/data_and_selection'
STAGE=Path('/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB')
OLD=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/IMU_V3_FIX_20261004/stage_07')
RAW=Path('/mnt/g/LegSA-GINS-project/data/raw/XB_PG/2026-01-05')
TOOLS=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD/04_BASE_PROVIDER/FRESH_AUXILIARIES_CLEAN2R2A')
CONVBIN=TOOLS/'tools/RTKLIB_PINNED_B34/app/consapp/convbin/gcc/convbin'
RDHELP=TOOLS/'raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper'
SCALE=1.0308398903907543
DAY=datetime.datetime(2026,1,5,tzinfo=datetime.timezone.utc).timestamp()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(p,rows,fields=None):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def raw_epochs(path):
 pvt={};hp={};gps=None
 for row in csv.DictReader(path.open()):
  n=row['name']
  if n not in ('UBX-NAV-PVT','UBX-NAV-HPPOSECEF','UBX-NAV-TIMEGPS'):continue
  b=ast.literal_eval(row['data']);payload=b[6:-2]
  if len(b)!=struct.unpack_from('<H',b,4)[0]+8:raise ValueError('UBX length')
  a=c=0
  for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
  if b[-2:]!=bytes([a,c]):raise ValueError('UBX checksum')
  if n=='UBX-NAV-TIMEGPS':
   _,_,week,leap,valid,_=struct.unpack_from('<IihbBI',payload)
   if valid&6==6:gps={'gps_week':week,'leap_seconds':leap}
  elif n=='UBX-NAV-PVT':
   itow=struct.unpack_from('<I',payload)[0];valid=payload[11];nano=struct.unpack_from('<i',payload,16)[0]
   dt=datetime.datetime(struct.unpack_from('<H',payload,4)[0],*payload[6:11],tzinfo=datetime.timezone.utc)
   t=dt.timestamp()+nano*1e-9-DAY
   llh=[struct.unpack_from('<i',payload,28)[0]*1e-7,struct.unpack_from('<i',payload,24)[0]*1e-7,struct.unpack_from('<i',payload,32)[0]*.001]
   flags=payload[21];ok=payload[20]==3 and bool(flags&1)
   pvt[itow]={'t':t,'llh':llh,'vel':np.array(struct.unpack_from('<iii',payload,48))*.001,
    'std':[struct.unpack_from('<I',payload,40)[0]*.001]*2+[struct.unpack_from('<I',payload,44)[0]*.001],
    'ok':ok,'fixed':ok and (flags>>6)&3==2,'utc_valid':bool(valid&3==3)}
  else:
   itow=struct.unpack_from('<I',payload,4)[0]
   xyz=np.array(struct.unpack_from('<iii',payload,8))*.01+np.array(struct.unpack_from('<bbb',payload,20))*.0001
   hp[itow]={'xyz':xyz,'valid':payload[23]==0,'pAcc':struct.unpack_from('<I',payload,24)[0]*.0001}
 return pvt,hp,gps

def gnss_inputs(rawroot,out):
 a,x,gps=raw_epochs(rawroot/'gnss1-raw.csv');b,y,_=raw_epochs(rawroot/'gnss2-raw.csv');rows=[];yaw=[]
 for k,p in sorted(a.items(),key=lambda v:v[1]['t']):
  q=x.get(k);llh=p['llh'];valid=p['ok'] and p['utc_valid'] and q is not None and q['valid']
  if q is not None and q['valid']:
   lat,lon,h=ecef_to_geodetic(q['xyz']);llh=[math.degrees(lat),math.degrees(lon),h]
  hv=0;heading=0.;length=None
  if valid and p['fixed'] and k in b and b[k]['fixed'] and k in y and y[k]['valid']:
   lat,lon=np.deg2rad(llh[:2]);sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
   ned=np.array([[-sl*co,-sl*so,cl],[-so,co,0],[-cl*co,-cl*so,-sl]])@(y[k]['xyz']-q['xyz'])
   length=float(np.linalg.norm(ned));heading=(math.degrees(math.atan2(ned[1],ned[0]))+90+180)%360-180
   hv=int(.2<=length<=.6)
   if hv:yaw.append({'time':p['t'],'yaw_deg':heading,'baseline_m':length,'iTOW_ms':k})
  rows.append([p['t'],*llh,*p['std'],*p['vel'],.05,.05,.05,heading,SIGMA_YAW,int(valid),int(p['ok']),hv])
 arr=np.asarray(rows);assert np.all(np.diff(arr[:,0])>0)
 np.savetxt(out/'GNSS18.gnss',arr,fmt='%.17g');table(out/'DUAL_HEADING.csv',yaw,['time','yaw_deg','baseline_m','iTOW_ms'])
 return arr,yaw,gps

def body_inputs(path,out,yaw):
 spec=importlib.util.spec_from_file_location('r5_profile_parser',PROFILE/'profile_candidates.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 frames=[];block=[]
 def consume():
  r,issues=m.parse_block(block)
  if all(k in r for k in ['sec','nanosec','gyroscope','accelerometer','rpy','velocity']) and all(len(r[k])==3 for k in ['gyroscope','accelerometer','rpy','velocity']):
   vals=[r['sec']+r['nanosec']*1e-9-DAY,*r['gyroscope'],*r['accelerometer'],*r['rpy'],*r['velocity']]
   if np.isfinite(vals).all():frames.append(vals)
 with path.open()as f:
  for line in f:
   if line.strip()=='---':consume();block=[]
   else:block.append(line)
  if block:consume()
 a=np.asarray(frames);assert np.all(np.diff(a[:,0])>0)
 rot=np.asarray(euler_rpy_deg_to_matrix(-1,0,0));gyro=(a[:,1:4]*[1,-1,-1])@rot.T;acc=(a[:,4:7]*[1,-1,-1])@rot.T
 bias=np.mean(gyro[:1000],axis=0);dt=np.diff(a[:,0]);valid=(dt>0)&(dt<=.1)
 imu=np.column_stack((a[1:,0],(gyro[1:]-bias)*dt[:,None],SCALE*acc[1:]*dt[:,None],dt))[valid]
 np.savetxt(out/'IMU8.imu',imu,fmt='%.17g')
 rp=[{'time':t,'roll_rad':roll,'pitch_rad':-pitch,'std_roll_rad':math.radians(1.6),'std_pitch_rad':math.radians(1.6),'source_status':'active'}for t,roll,pitch in a[:,[0,7,8]]]
 table(out/'GO2_RP.csv',rp)
 ys,support=interpolate_a1(a[:,0],[v['time']for v in yaw],[v['yaw_deg']for v in yaw])
 v=np.zeros((len(a),2)) if ys is None else K_HV*rotate_flu_to_ned(a[:,10:13],a[:,7],a[:,8],ys)
 hv=[{'time':t,'vn':vel[0],'ve':vel[1],'vd':0,'std_vn':SIGMA_HV,'std_ve':SIGMA_HV,'std_vd':999,'valid':int(ok),'update_flag':bool(ok),'source_status':'active' if ok else 'inactive','confidence_level':'weak_auxiliary','reason_codes':'A1_supported' if ok else 'A1_unavailable'}for t,vel,ok in zip(a[:,0],v,support)]
 table(out/'GO2_HV.csv',hv)
 return a,imu,{'gyro_bias':bias.tolist(),'valid_frames':len(a),'excluded_dt_gt_0p1':int(np.sum(dt>.1)),'warmup_end':float(a[999,0])}

def doppler(rawroot,out):
 backend=out/'RD_BACKEND';backend.mkdir();ubx=backend/'gnss1.ubx';fg.rebuild_csv_to_ubx(rawroot/'gnss1-raw.csv',ubx)
 obs,nav=backend/'gnss1.obs',backend/'gnss1.nav'
 argv=[str(CONVBIN),'-r','ubx','-v','3.04','-od','-os','-oi','-ot','-ol','-o',str(obs),'-n',str(nav),str(ubx)]
 p=subprocess.run(argv,capture_output=True,text=True);(backend/'convbin.log').write_text(p.stdout+p.stderr);p.check_returncode()
 source=fg._first_source_position_and_time(rawroot/'gnss1-status.csv',rawroot/'gnss1-raw.csv')
 h=fg.run_rtklib_doppler_velocity_provider(obs_path=obs,nav_path=nav,helper_exe=RDHELP,approx_position_source={k:source[k]for k in ['lat_deg','lon_deg','height_m']},output_dir=backend/'helper_run',min_sat=5)
 if h['helper_run_status']!='success':raise RuntimeError('Raw Doppler unavailable: '+str(h))
 counts=fg._write_formal_raw_doppler(Path(h['helper_raw_csv_path']),out/'RAW_DOPPLER.csv',source_position=source,obs_hash=sha(obs),nav_hash=sha(nav),conversion_config_hash=sha(backend/'convbin.log'),min_sat=5,std_floor_mps=.2,covariance_policy='conservative_isotropic_max_ecef_std_floor_0p2_mps')
 return {**counts,'helper_executable_hash':sha(RDHELP),'obs_source_hash':sha(obs),'nav_source_hash':sha(nav),'conversion_config_hash':sha(backend/'convbin.log'),'source_time':source}

def prepare():
 STAGE.mkdir(parents=True,exist_ok=True);(STAGE/'INPUTS').mkdir(exist_ok=True);(STAGE/'CONFIGS').mkdir(exist_ok=True)
 prior=json.loads((OLD/'PREREGISTRATION.json').read_text());templates={m:Path(next(r for r in prior['runs']if r['method_id']==m and r['sequence_id']=='BY2')['children'][0]['config']['path'])for m in ['F03','F04']}
 shutil.copyfile(OLD/'SOLVER',STAGE/'SOLVER');(STAGE/'SOLVER').chmod(0o755)
 plan={'stage':'R5_JANUARY8_FIXED_PARAMETER_TRANSFER','binary_sha256':sha(STAGE/'SOLVER'),'implementation_origin':str(OLD),'script_sha256':sha(__file__),'reference_used_for_preparation':False,'offset_s':0,'runs':[],'sequences':{},'numerical_parameters_from':{m:{'path':str(p),'sha256':sha(p)}for m,p in templates.items()}}
 pairing=list(csv.DictReader((PROFILE/'CANDIDATE_PAIRING_SELECTED8.csv').open()));profiles={r['file']:r for r in csv.DictReader((PROFILE/'BODY_TIME_QUALITY_SUMMARY.csv').open())}
 for pair in pairing:
  name=pair['body_file'][:-4];seq=name.upper();out=STAGE/'INPUTS'/seq;out.mkdir(exist_ok=True);prof=profiles[pair['body_file']]
  info={'body':str(RAW/'高层数据'/pair['body_file']),'body_sha256':prof['sha256'],'receiver_folder':pair['receiver_folder'],'expected_observed_epochs':int(prof['complete_all_fields'])-1,'window_utc_day_s':[float(prof['first_t'])-DAY,float(prof['last_t'])-DAY]}
  if name.startswith('xb'):
   info['status']='NO_INIT_NO_VALID_DUAL_HEADING';plan['sequences'][seq]=info
   for method in templates:plan['runs'].append({'run_id':'IMUFIX_R5_'+seq+'_'+method,'sequence':seq,'method':method,'status':info['status'],'native_invoked':False})
   continue
  rawroot=STAGE/'RAW'/name;gnss,yaw,gps=gnss_inputs(rawroot,out);a,imu,bodyinfo=body_inputs(Path(info['body']),out,yaw)
  assert sha(info['body'])==info['body_sha256'];rd=doppler(rawroot,out)
  start=max(a[999,0],gnss[0,0]);end=min(a[-1,0],gnss[-1,0]);init=next(v for v in gnss if start<=v[0]<=end and v[15] and v[17]);seed=imu[np.searchsorted(imu[:,0],init[0])];att=[0,0,float(init[13])]
  info.update(status='PREPARED',window_utc_day_s=[float(a[0,0]),float(a[-1,0])],native_window=[float(seed[0]),float(end)],initialization_gnss_time=float(init[0]),initialization_yaw_deg=att[2],input_gyro_bias=bodyinfo['gyro_bias'],rd_valid_epochs=rd['valid_epoch_count'],heading_epochs=len(yaw),gps=gps)
  info['providers']={p.name:{'path':str(p),'sha256':sha(p)}for p in out.iterdir()if p.is_file()};plan['sequences'][seq]=info
  for method,template in templates.items():
   cfg=yaml.safe_load(template.read_text());rid='IMUFIX_R5_'+seq+'_'+method
   cfg.update(run_id=rid,run_label=rid,imupath=str(out/'IMU8.imu'),gnsspath=str(out/'GNSS18.gnss'),outputpath=str(STAGE/'NATIVE'/rid),starttime=float(seed[0]),endtime=float(end),initpos=imu_position_from_antenna(init[1:4],att,cfg['antlever']),initatt=att,initvel=[0,0,0],common_initialization_source='R5_first_valid_dual_fixed_HP_no_reference',raw_doppler_factor_path=str(out/'RAW_DOPPLER.csv'),go2_attitude_prior_path=str(out/'GO2_RP.csv'),go2_horizontal_velocity_prior_path=str(out/'GO2_HV.csv'),raw_doppler_backend_source_files=[str(rawroot/'gnss1-raw.csv'),str(rawroot/'gnss1-status.csv')],raw_doppler_backend_source_hashes={str(rawroot/k):sha(rawroot/k)for k in ['gnss1-raw.csv','gnss1-status.csv']},**{k:rd[k]for k in ['helper_executable_hash','obs_source_hash','nav_source_hash','conversion_config_hash']})
   p=STAGE/'CONFIGS'/(rid+'.yaml');p.write_text(''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in cfg.items()));plan['runs'].append({'run_id':rid,'sequence':seq,'method':method,'status':'PREPARED','config':str(p),'config_sha256':sha(p)})
  print('PREPARED',seq,'heading',len(yaw),'RD',rd['valid_epoch_count'],'init',seed[0],flush=True)
 save(STAGE/'PLAN.json',plan)
 print('PLAN',STAGE/'PLAN.json',flush=True)

def native():
 plan=json.loads((STAGE/'PLAN.json').read_text());assert sha(__file__)==plan['script_sha256'];assert sha(STAGE/'SOLVER')==plan['binary_sha256'];records=[]
 for run in plan['runs']:
  rec=dict(run)
  if run['status']=='PREPARED':
   seq=plan['sequences'][run['sequence']]
   for v in seq['providers'].values():assert sha(v['path'])==v['sha256']
   assert sha(run['config'])==run['config_sha256'];out=STAGE/'NATIVE'/run['run_id'];out.mkdir(parents=True,exist_ok=False)
   argv=['strace','-f','-qq','-s','4096','-e','trace=openat,execve','-o',str(out/'OPENAT.strace'),str(STAGE/'SOLVER'),'--config',run['config'],'--output-dir',str(out)]
   t=time.monotonic()
   with (out/'stdout.log').open('w')as stdout,(out/'stderr.log').open('w')as stderr:p=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=1200)
   opened=audited_open_records(out/'OPENAT.strace',CODE);refopens=[v for v in opened if any(k in v['path']for k in ['trace_vrtk','poi_odometry','smooth_odometry'])]
   rec.update(exit_code=p.returncode,native_invoked=True,runtime_seconds=time.monotonic()-t,reference_open_count=len(refopens),output_root=str(out),status='COMPLETED' if p.returncode==0 and not refopens else 'FAILED_NATIVE')
   navpath=out/'KF_GINS_Navresult.nav'
   if navpath.exists():
    nav=np.loadtxt(navpath,comments='%',ndmin=2);rec['output_epochs']=len(nav);rec['all_finite']=bool(np.isfinite(nav).all())
    if not rec['all_finite']:rec['status']='FAILED_NONFINITE'
   rec['output_sha256']={p.name:sha(p)for p in out.iterdir()if p.is_file()}
   save(out/'RESULT.json',rec);print(run['run_id'],rec['status'],rec.get('output_epochs'),flush=True)
  records.append(rec)
 save(STAGE/'ALL_NATIVE_SEALED.json',{'status':'SEALED','plan_sha256':sha(STAGE/'PLAN.json'),'script_sha256':sha(__file__),'runs':records,'reference_open_count':sum(r.get('reference_open_count',0)for r in records)})
 table(STAGE/'NATIVE_RESULTS.csv',[{k:r.get(k,'')for k in ['run_id','sequence','method','status','native_invoked','output_epochs','runtime_seconds','reference_open_count']}for r in records])

def retry_inline_configs():
 global STAGE
 old=STAGE;plan=json.loads((old/'PLAN.json').read_text());oldseal=json.loads((old/'ALL_NATIVE_SEALED.json').read_text())
 STAGE=old/'ATTEMPT_02';STAGE.mkdir(exist_ok=False);(STAGE/'CONFIGS').mkdir();shutil.copyfile(old/'SOLVER',STAGE/'SOLVER');(STAGE/'SOLVER').chmod(0o755)
 plan.update(script_sha256=sha(__file__),technical_retry='Inline serialization only; original numerical parameters and providers retained',superseded_native_seal_sha256=sha(old/'ALL_NATIVE_SEALED.json'))
 for run in plan['runs']:
  if run['status']!='PREPARED':continue
  cfg=yaml.safe_load(Path(run['config']).read_text());rid=run['run_id']+'_T02';cfg.update(run_id=rid,run_label=rid,outputpath=str(STAGE/'NATIVE'/rid))
  p=STAGE/'CONFIGS'/(rid+'.yaml');p.write_text(''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in cfg.items()))
  assert yaml.safe_load(p.read_text())==cfg
  run.update(run_id=rid,config=str(p),config_sha256=sha(p))
 save(STAGE/'PLAN.json',plan)
 print('INLINE_RETRY_READY',STAGE,flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','native','retry']);ap.add_argument('--stage',type=Path,default=STAGE);args=ap.parse_args();STAGE=args.stage
 {'prepare':prepare,'native':native,'retry':retry_inline_configs}[args.phase]()
