#!/usr/bin/env python3
"""Isolated Ubuntu SDK-aiding pilot; production sources stay immutable."""
from pathlib import Path
import argparse,csv,hashlib,json,os,shutil,subprocess,time
import numpy as np
import pandas as pd
import yaml
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False)
def rep(s,a,b):
 if s.count(a)!=1:raise ValueError('PATCH_ANCHOR:'+a[:80]+':'+str(s.count(a)))
 return s.replace(a,b)
HEADER=r'''
#pragma once
#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include <vector>
namespace legsa_v23_port_core {
inline Matrix pilotBodyH(const NavState& s){
 Matrix H(2,RANK,0.0);const Matrix3 c=transpose(s.cbn);
 const Matrix3 a=scale(multiply(c,Rotation::skewSymmetric(s.vel_ned_mps)),-1.0);
 for(int i=0;i<2;++i)for(int j=0;j<3;++j){H(i,V_ID+j)=c[i][j];H(i,PHI_ID+j)=a[i][j];}return H;
}
template<class T> const T* pilotLatest(const std::vector<T>& rows,double t,double age,double last){
 const T* best=nullptr;
 for(const auto& row:rows)if(row.time<=t && t-row.time<=age && row.time>last && (!best||row.time>best->time))best=&row;
 return best;
}
inline bool pilotTick(double t,double& next){
 if(t+1e-10<next)return false;do{next+=.2;}while(next<=t+1e-10);return true;
}
}
'''
TEST=r'''
#include "legsa_v23_port_core/pilot_aiding.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace legsa_v23_port_core;
int main(){
 double mx=0;const double eps=1e-6;
 for(const Vec3 e:{makeVec3(.1,-.2,1.),makeVec3(-.35,.25,-2.1),makeVec3(0,0,0)}){
 NavState s;s.qbn=Rotation::euler2quaternion(e);s.cbn=Rotation::quaternion2matrix(s.qbn);s.vel_ned_mps=makeVec3(1.3,-.7,.2);
 const Matrix H=pilotBodyH(s);
 for(int j=0;j<6;++j){NavState p=s,m=s;
 if(j<3){p.vel_ned_mps[j]-=eps;m.vel_ned_mps[j]+=eps;}
 else{Vec3 d=makeVec3(0,0,0);d[j-3]=eps;p.cbn=Rotation::quaternion2matrix(Rotation::multiply(Rotation::rotvec2quaternion(d),s.qbn));
 d[j-3]=-eps;m.cbn=Rotation::quaternion2matrix(Rotation::multiply(Rotation::rotvec2quaternion(d),s.qbn));}
 auto hp=multiply(transpose(p.cbn),p.vel_ned_mps),hm=multiply(transpose(m.cbn),m.vel_ned_mps);
 for(int i=0;i<2;++i)mx=std::max(mx,std::fabs(-(hp[i]-hm[i])/(2*eps)-H(i,j<3?V_ID+j:PHI_ID+j-3)));
 }}
 if(mx>1e-8)throw std::runtime_error("body Jacobian");
 struct Row{double time;};std::vector<Row> r{{.1},{.2},{.21},{.5}};
 if(pilotLatest(r,.205,.02,-1)->time!=.2||pilotLatest(r,.205,.02,.2)||pilotLatest(r,.4,.08,-1)||pilotLatest(r,.09,.08,-1))throw std::runtime_error("causal unique fresh samples");
 double next=.2;if(pilotTick(.199,next)||!pilotTick(.201,next)||pilotTick(.201,next)||!pilotTick(.901,next)||pilotTick(.901,next))throw std::runtime_error("timer");
 std::cout<<"{\"status\":\"PASS\",\"max_body_jacobian_error\":"<<mx<<",\"schedule_guards\":5}\n";
}
'''
def build(a):
 st=a.stage;st.mkdir(parents=True,exist_ok=True);dest=st/'SOURCE';dest.mkdir(exist_ok=False)
 src=a.code/'cpp/legsa_v23_port_core';before={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
 shutil.copytree(src,dest/'core')
 hp=dest/'core/include/legsa_v23_port_core/kf_gins/gi_engine.hpp';s=hp.read_text()
 hp.write_text(rep(s,'  bool initialized_ = false;','  int pilot_mode_=0;\n  double pilot_next_=0.0,pilot_last_rp_=-1e100,pilot_last_hv_=-1e100;\n  bool initialized_ = false;'))
 p=dest/'core/src/kf_gins/gi_engine.cpp';s=p.read_text()
 s=rep(s,'#include <algorithm>','#include "legsa_v23_port_core/pilot_aiding.hpp"\n#include <cstdlib>\n#include <algorithm>')
 i=s.index('{',s.index('GIEngine::GIEngine(PortOptions options)'))
 s=s[:i+1]+'''
 const char* pm=std::getenv("LEGSA_PILOT_AID_MODE");pilot_mode_=pm?std::stoi(pm):0;
 if(pilot_mode_<0||pilot_mode_>2)throw std::runtime_error("pilot mode");
 pilot_next_=options_.starttime+.2;
 '''+s[i+1:]
 s=rep(s,'    applyGo2VelocityDiagnosticPriorForTime(policy_gnss.time);','    if(pilot_mode_!=2)applyGo2VelocityDiagnosticPriorForTime(policy_gnss.time);')
 s=rep(s,'    applyGo2AttitudeWeakPriorForTime(policy_gnss.time);','    if(pilot_mode_==0)applyGo2AttitudeWeakPriorForTime(policy_gnss.time);')
 s=rep(s,'  if (!checkCov()) {',r'''
 if(pilot_mode_>0 && pilotTick(timestamp_,pilot_next_)){
 const auto rb=go2_attitude_prior_status_.update_count,hb=go2_velocity_diagnostic_prior_status_.update_count;
 if(pilot_mode_==2)applyGo2VelocityDiagnosticPriorForTime(timestamp_);
 applyGo2AttitudeWeakPriorForTime(timestamp_);
 if(go2_attitude_prior_status_.update_count>rb||go2_velocity_diagnostic_prior_status_.update_count>hb)stateFeedback();
 const char* audit=std::getenv("LEGSA_PILOT_AID_AUDIT");
 if(audit){std::ofstream f(audit,std::ios::app);f<<std::setprecision(17)<<timestamp_<<","<<pilot_last_rp_<<","<<pilot_last_hv_<<","
 <<go2_attitude_prior_status_.update_count-rb<<","<<go2_velocity_diagnostic_prior_status_.update_count-hb<<"\n";}
 }
  if (!checkCov()) {''')
 i=s.index('void GIEngine::applyGo2AttitudeWeakPriorForTime');j=s.index('void GIEngine::applyGo2VelocityDiagnosticPriorForTime');v=s[i:j]
 v=rep(v,'  if (!best) {','  if(pilot_mode_>0)best=pilotLatest(go2_attitude_priors_,update_time,options_.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec,pilot_last_rp_);\n  if (!best) {')
 v=rep(v,'  if (!Go2WeakPriorFactor::isActive(*best)) {','  if(pilot_mode_>0)pilot_last_rp_=best->time;\n  if (!Go2WeakPriorFactor::isActive(*best)) {')
 s=s[:i]+v+s[j:];i=s.index('void GIEngine::applyGo2VelocityDiagnosticPriorForTime');j=s.index('void GIEngine::applyFgoFeedbackForTime');v=s[i:j]
 v=rep(v,'  if (!best) {','  if(pilot_mode_==2)best=pilotLatest(go2_velocity_diagnostic_priors_,update_time,options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec,pilot_last_hv_);\n  if (!best) {')
 v=rep(v,'  if (best->source_status != "active" ||','  if(pilot_mode_==2)pilot_last_hv_=best->time;\n  if (best->source_status != "active" || !best->update_flag ||')
 v=rep(v,'  const Vec3 residual_vec = subtract(pvacur_.vel_ned_mps, best->velocity_ned_mps);','  const Vec3 predicted=pilot_mode_==2?multiply(transpose(pvacur_.cbn),pvacur_.vel_ned_mps):pvacur_.vel_ned_mps;\n  const Vec3 residual_vec = subtract(predicted, best->velocity_ned_mps);')
 v=rep(v,'    H(1, V_ID + 1) = 1.0;','    H(1, V_ID + 1) = 1.0;\n    if(pilot_mode_==2)H=pilotBodyH(pvacur_);')
 p.write_text(s[:i]+v+s[j:])
 (dest/'core/include/legsa_v23_port_core/pilot_aiding.hpp').write_text(HEADER);(dest/'pilot_test.cpp').write_text(TEST)
 writer=dest/'core/src/runtime/port_runtime.cpp';ws=writer.read_text()
 ws=rep(ws,'      if (state.time > states.front().time + 2.0 && state.time < states.back().time - 2.0) continue;','      // Pilot observation only: full-window sparse P, including outages.')
 ws=rep(ws,'      if (state.time < last_written + .05 && i + 1 != states.size()) continue;','      if (state.time < last_written + 1.0 && i + 1 != states.size()) continue;')
 writer.write_text(ws)
 cm='''cmake_minimum_required(VERSION 3.16)
project(pilot LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
file(GLOB_RECURSE sources CONFIGURE_DEPENDS core/src/*.cpp)
list(FILTER sources EXCLUDE REGEX "/demo/port_demo.cpp$")
'''
 cm+='add_library(core STATIC '+chr(36)+'{sources})\n'
 cm+='''target_include_directories(core PUBLIC core/include)
add_executable(SOLVER core/src/demo/port_demo.cpp)
target_link_libraries(SOLVER PRIVATE core)
add_executable(pilot_test pilot_test.cpp)
target_link_libraries(pilot_test PRIVATE core)
'''
 (dest/'CMakeLists.txt').write_text(cm)
 subprocess.run(['cmake','-S',str(dest),'-B',str(st/'BUILD'),'-DCMAKE_BUILD_TYPE=Release'],check=True)
 subprocess.run(['cmake','--build',str(st/'BUILD'),'-j','4'],check=True)
 tests=json.loads(subprocess.check_output([str(st/'BUILD/pilot_test')],text=True));emit(st/'UNIT_TESTS.json',tests)
 emit(st/'BUILD_IDENTITY.json',{'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.code,text=True).strip(),'production_source_sha256':before,'sandbox_source_sha256':{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()},'binary_sha256':sha(st/'BUILD/SOLVER'),'unit_tests':tests})
 assert before=={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
 print('BUILD_UNIT_TESTS_PASS',flush=True)

def prepare(a):
 from legsa_gins.paper_rebuild.imu_contract_repair import clone_fields
 st=a.stage;prior=json.loads((a.prior/'PREREGISTRATION.json').read_text());seq=prior['sequences']['BY2'];inp=st/'INPUTS';inp.mkdir(exist_ok=False)
 raw=Path(seq['raw_body_path']);assert sha(raw)==seq['raw_body_sha256'];samples=[];block=[];raw_errors=[]
 def accept(lines):
  sec=nsec=None;vel=[];reading=False;error_code=None
  for line in lines:
   q=line.strip()
   if q.startswith('sec:'):sec=int(q.split(':',1)[1])
   elif q.startswith('nanosec:'):nsec=int(q.split(':',1)[1])
   elif q.startswith('error_code:'):error_code=int(q.split(':',1)[1])
   elif line.startswith('velocity:'):
    reading=True;value=q.split(':',1)[1].strip()
    if value.startswith('['):vel=[float(x) for x in value.strip('[]').split(',')];reading=False
   elif reading:
    if q.startswith('-'):vel.append(float(q[1:]))
    else:reading=False
  if sec is None or nsec is None or len(vel)!=3:return
  t=sec+nsec*1e-9-seq['base_time']
  assert error_code==0 and np.isfinite(vel).all()
  raw_errors.append(error_code);k=1.0/0.962142
  samples.append((t,k*vel[0],-k*vel[1],-k*vel[2]))
 with raw.open() as f:
  for line in f:
   if line.strip()=='---':accept(block);block=[]
   else:block.append(line.rstrip('\n'))
 if block:accept(block)
 assert len(samples)>50000 and np.all(np.diff(np.asarray(samples)[:,0])>0)
 target=inp/'ROBOT_REPORTED_BODY_HYPOTHESIS.csv'
 with target.open('x',newline='') as f:
  w=csv.writer(f);w.writerow(['time','vn','ve','vd','std_vn','std_ve','std_vd','source_status','quality_flag','frame_candidate','prior_policy','update_flag','diagnostic_only','go2_velocity_truth_claim'])
  for t,x,y,z in samples:w.writerow([format(t,'.12f'),x,y,z,.132838,.132838,999.,'active','conditional_body_frame','conditional_SDK_FLU_to_FRD','conditional_body_forward_right_2d',True,True,False])
 chosen={r['case_id']:r for r in prior['runs'] if r['method_id']=='F04' and r['case_id'] in ('D61_20s_seed_00','D62_20s_seed_00')}
 rp=pd.read_csv(chosen['D61_20s_seed_00']['providers']['go2_attitude_prior_path']['path'])
 assert len(rp)==len(samples) and np.max(np.abs(rp.time.to_numpy()-np.asarray(samples)[:,0]))<1e-6
 # Source validity only, no legacy velocity/yaw payload: prove inherited validity all true.
 valid=pd.read_csv(chosen['D61_20s_seed_00']['providers']['go2_horizontal_velocity_prior_path']['path'],usecols=['time','go2_source_valid'])
 assert len(valid)==len(samples) and valid.go2_source_valid.all() and (np.asarray(raw_errors)==0).all()
 natural=json.loads(Path(prior['natural_IMU_reuse']['preregistration_path']).read_text());clean=next(r for r in natural['runs'] if r['sequence_id']=='BY2' and r['method_id']=='F04')
 chosen={'C00':clean,**chosen};runs=[]
 def add(case,source,gnss=None):
  payload=Path(source['children'][0]['config']['path']).read_bytes()
  for mode in (0,1,2):
   rid=f'{case}_M{mode}';fields={'run_id':rid,'run_label':rid,'protocol_id':'RESEARCH_AUDIT_CAUSAL_AID_PILOT_20261006','outputpath':str(st/'NATIVE'/rid)}
   if mode==2:fields['go2_horizontal_velocity_prior_path']=str(target)
   if gnss:fields['gnsspath']=str(gnss)
   data,changes=clone_fields(payload,fields);cfg=st/'CONFIGS'/f'{rid}.yaml';cfg.parent.mkdir(exist_ok=True);cfg.write_bytes(data)
   runs.append({'run_id':rid,'case':case,'mode':mode,'config':str(cfg),'config_sha256':sha(cfg),'source_config':source['children'][0]['config'],'changes':changes,'outage':None if case=='C00' else [196.2,216.2]})
 for case,source in chosen.items():add(case,source)
 src=chosen['D61_20s_seed_00'];cfg=yaml.safe_load(Path(src['children'][0]['config']['path']).read_text());lines=Path(cfg['gnsspath']).read_text().splitlines(True)
 kept=[l for l in lines if not l.strip() or l.lstrip().startswith('#') or not 196.2<=float(l.split()[0])<216.2];assert len(lines)-len(kept)==100
 missing=inp/'D61_NO_GNSS_RECORDS.gnss';missing.write_text(''.join(kept));add('D61_NO_RECORDS',src,missing)
 pins={}
 for r in runs:
  cfg=yaml.safe_load(Path(r['config']).read_text())
  for k in ('imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path'):pins[cfg[k]]=sha(cfg[k])
 emit(st/'PLAN.json',{'schema':'isolated_sdk_aid.v1','sequence':seq,'runs':runs,'inputs':pins,'raw_velocity':{'path':str(raw),'sha256':sha(raw),'rows':len(samples),'fields':['stamp.sec','stamp.nanosec','velocity'],'inherited_scale':1.0/0.962142,'raw_error_code_all_zero':True,'inherited_go2_source_valid_all_true':True,'frame':'CONDITIONAL_BODY_FLU','timestamp_check':'exact raw timestamps match inherited RP provider','gnss_or_reference_read':False},'native_budget':12,'body_std_mps':.132838,'body_point_offset_assumption_m':[0,0,0],'binary_sha256':sha(st/'BUILD/SOLVER'),'build_identity_sha256':sha(st/'BUILD_IDENTITY.json')})
 print('PREPARED_12_NO_REFERENCE',flush=True)
def native(a):
 from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
 st=a.stage;plan=json.loads((st/'PLAN.json').read_text());assert sha(st/'BUILD/SOLVER')==plan['binary_sha256']
 for p,d in plan['inputs'].items():assert sha(p)==d
 for r in plan['runs']:
  cfg=yaml.safe_load(Path(r['config']).read_text())
  assert r['mode']!=2 or cfg['go2_horizontal_velocity_prior_mode']=='horizontal_2d'
 records=[];commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.code,text=True).strip()
 for r in plan['runs']:
  out=st/'NATIVE'/r['run_id'];out.mkdir(parents=True,exist_ok=False);assert sha(r['config'])==r['config_sha256']
  audit=out/'AID_EVENTS.csv';audit.write_text('state_time,rp_sample_time,hv_sample_time,rp_accepted,hv_accepted\n')
  env={**os.environ,'LEGSA_PILOT_AID_MODE':str(r['mode']),'LEGSA_PILOT_AID_AUDIT':str(audit),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
  argv=['strace','-f','-qq','-s','4096','-e','trace=openat,execve','-o',str(out/'OPENAT.strace'),str(st/'BUILD/SOLVER'),'--config',r['config'],'--output-dir',str(out)];t=time.monotonic()
  with (out/'stdout.log').open('x') as o,(out/'stderr.log').open('x') as e:proc=subprocess.run(argv,cwd=a.code,env=env,stdout=o,stderr=e,timeout=1200)
  opens=audited_open_records(out/'OPENAT.strace',a.code);trace=sum(q['path']==plan['sequence']['trace_path'] for q in opens)
  rec={**r,'returncode':proc.returncode,'runtime_seconds':time.monotonic()-t,'online_trace_reads':trace,'status':'COMPLETED' if proc.returncode==0 and trace==0 else 'FAILED','execution_commit':commit}
  if rec['status']=='COMPLETED':
   nav=np.loadtxt(out/'KF_GINS_Navresult.nav',ndmin=2,comments='%');std=np.loadtxt(out/'KF_GINS_STD.txt',ndmin=2,comments='%')
   assert len(nav)==len(std) and np.isfinite(nav).all() and np.isfinite(std).all();rec['output_rows']=len(nav)
   rec['time_keys_sha256']=hashlib.sha256(nav[:,1].copy().tobytes()).hexdigest()
   if r['mode']==0:
    previous=Path(yaml.safe_load(Path(r['source_config']['path']).read_text())['outputpath'])
    parity={}
    for name,new_array in [('KF_GINS_Navresult.nav',nav),('KF_GINS_STD.txt',std)]:
     old=previous/name
     if old.exists():
      original=np.loadtxt(old,ndmin=2,comments='%');assert original.shape==new_array.shape
      delta=float(np.max(np.abs(original-new_array)))
      parity[name]={'old_sha256':sha(old),'new_sha256':sha(out/name),'max_absolute_difference':delta}
      assert delta<=1e-9
     else:parity[name]={'status':'SAVED_PAYLOAD_UNAVAILABLE'}
    rec['prior_diagnostic_parity']=parity
   saved=np.loadtxt(out/'STATE_COVARIANCE_SUPPORT.csv',delimiter=',',skiprows=1,ndmin=2);cov=saved[:,16:].reshape(-1,21,21)
   scale=np.maximum(1,np.max(np.abs(cov),axis=(1,2)));eig=np.linalg.eigvalsh((cov[:,:15,:15]+cov[:,:15,:15].transpose(0,2,1))*.5)
   asym=float(np.max(np.max(np.abs(cov-cov.transpose(0,2,1)),axis=(1,2))/scale))
   rec['covariance']={'samples':len(cov),'min_active_eigen':float(eig.min()),'relative_asymmetry':asym,'finite':bool(np.isfinite(cov).all())}
   assert rec['covariance']['finite'] and np.all(eig[:,0]>=-1e-10*scale) and asym<1e-8
   ev=pd.read_csv(audit)
   if r['mode']:
    for kind,age in [('rp',.02)]+([('hv',.08)] if r['mode']==2 else []):
     used=ev[ev[kind+'_accepted']>0];dt=used.state_time-used[kind+'_sample_time']
     assert used[kind+'_sample_time'].is_unique and (dt>=0).all() and (dt<=age+1e-9).all()
    rec['aid_events']=len(ev)
    if r['outage']:
     v=ev[(ev.state_time>=r['outage'][0])&(ev.state_time<r['outage'][1])]
     rec['outage_rp_accepted']=int(v.rp_accepted.sum());rec['outage_hv_accepted']=int(v.hv_accepted.sum())
   rec['nav_sha256']=sha(out/'KF_GINS_Navresult.nav');rec['std_sha256']=sha(out/'KF_GINS_STD.txt')
  emit(out/'RESULT.json',rec);records.append(rec);print(r['run_id'],rec['status'],flush=True)
  if rec['status']!='COMPLETED':raise RuntimeError('Native failed, no retry')
 for case in sorted(set(r['case'] for r in records)):
  assert len(set(r['time_keys_sha256'] for r in records if r['case']==case))==1
 emit(st/'ALL_NATIVE_SEALED.json',{'status':'SEALED','plan_sha256':sha(st/'PLAN.json'),'records':records});print('ALL_12_NATIVE_SEALED',flush=True)
def evaluate(a):
 from legsa_gins.paper_rebuild.imu_contract_repair import transform_nav,write_transformed_nav,evaluate as evaluator,EVALUATOR_SHA256
 st=a.stage;plan=json.loads((st/'PLAN.json').read_text());seal=json.loads((st/'ALL_NATIVE_SEALED.json').read_text());seq=plan['sequence']
 assert seal['status']=='SEALED' and len(seal['records'])==12 and seal['plan_sha256']==sha(st/'PLAN.json') and sha(a.evaluator)==EVALUATOR_SHA256
 rows=[];time_keys={}
 for r in seal['records']:
  out=st/'NATIVE'/r['run_id'];nav=out/'KF_GINS_Navresult.nav';assert sha(nav)==r['nav_sha256'];root=st/'EVALUATION'/r['run_id'];root.mkdir(parents=True,exist_ok=False)
  target=root/'EVAL_NAV.nav';write_transformed_nav(nav,target,transform_nav(np.loadtxt(nav,ndmin=2,comments='%'),seq['baseline_median_m']))
  result=evaluator(evaluator=a.evaluator,trace=Path(seq['trace_path']),nav=target,std=out/'KF_GINS_STD.txt',outdir=root/'FROZEN_EVALUATOR',base_time=seq['base_time'],window=seq['window'],trace_sha256=seq['trace_sha256'],code_root=a.code,raw_root=Path(seq['raw_root']),clean_root=a.clean_root,instrument=True,consistency_policy='canonical_v2_wgs84_full_support')
  emit(root/'EVALUATOR_RESULT.json',result);assert result['audit']['passed'] and result['capture']['consistency']['passed']
  errors=pd.read_csv(root/'FROZEN_EVALUATOR/error_series.csv');t=errors.time.to_numpy();time_keys[r['run_id']]=(r['case'],hashlib.sha256(t.copy().tobytes()).hexdigest());domains={'full':np.ones(len(t),bool)}
  if r['outage']:
   start,end=r['outage'];domains.update(outage=(t>=start)&(t<end),recovery_0_5=(t>end)&(t<=end+5))
  for domain,mask in domains.items():
   assert mask.any();row={'run_id':r['run_id'],'case':r['case'],'mode':r['mode'],'domain':domain,'epochs':int(mask.sum())}
   for col,key in [('horizontal_err_m','H_RMSE_m'),('err_u_m','V_RMSE_m'),('position_3d_err_m','D3_RMSE_m'),('yaw_err_deg','yaw_RMSE_deg')]:
    v=errors[col].to_numpy()[mask];row[key]=float(np.sqrt(np.mean(v*v)))
    if domain=='outage':row[key.replace('RMSE','terminal_abs')]=float(abs(v[-1]))
   rows.append(row)
  print('evaluated',r['run_id'],flush=True)
 assert all(len(set(v[1] for v in time_keys.values() if v[0]==case))==1 for case in set(v[0] for v in time_keys.values()))
 pd.DataFrame(rows).to_csv(st/'PILOT_RESULTS.csv',index=False);emit(st/'EVALUATION_COMPLETE.json',{'evaluations':12,'rows':len(rows),'plan_sha256':sha(st/'PLAN.json')})
def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['build','prepare','native','evaluate'])
 for k in ['stage','code','prior','evaluator','clean-root']:p.add_argument('--'+k,type=Path)
 a=p.parse_args();assert os.uname().sysname=='Linux';globals()[a.phase](a)
if __name__=='__main__':main()
