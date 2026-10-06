#!/usr/bin/env python3
"""Six-run conditional body-z and heading-source-loss pilot; isolated WSL only."""
from pathlib import Path
import argparse,csv,hashlib,json,os,shutil,subprocess,time,importlib.util
import numpy as np
import pandas as pd
import yaml
OLD_BINARY="3805d2d2b0f52063da48d52b23fca2f88c4b5f9ef19adc9bfd48f5fe920701e7"
ROLES=("imupath","gnsspath","raw_doppler_factor_path","go2_attitude_prior_path","go2_horizontal_velocity_prior_path")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x") as f:json.dump(x,f,indent=2,ensure_ascii=False,allow_nan=False)
def rep(s,a,b):
 if s.count(a)!=1:raise ValueError("PATCH_ANCHOR:"+a[:50]+":"+str(s.count(a)))
 return s.replace(a,b)
def load_old(a):
 spec=importlib.util.spec_from_file_location("old_pilot",a.code/"scripts/paper_rebuild/research_audit_20261006/pilot.py")
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def build(a):
 old=a.prior.parent;identity=json.loads((old/"BUILD_IDENTITY.json").read_text())
 for name,d in identity["sandbox_source_sha256"].items():assert sha(old/"SOURCE"/name)==d
 assert sha(a.prior/"BUILD/SOLVER")==OLD_BINARY
 dest=a.stage/"SOURCE";dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(old/"SOURCE",dest)
 p=dest/"core/src/kf_gins/gi_engine.cpp";s=p.read_text()
 s=rep(s,'if(pilot_mode_<0||pilot_mode_>2)','if(pilot_mode_<0||pilot_mode_>3)')
 # Mode 3 explicitly overrides the inherited horizontal-only transport after parser admission.
 # The loader is untouched; all reports identify this as a new exploratory model.
 anchor=' pilot_next_=options_.starttime+.2;'
 s=rep(s,anchor,anchor+'''
 if(pilot_mode_==3){
   auto& cfg=options_.go2_velocity_prior_diagnostic_config;
   if(cfg.go2_horizontal_velocity_prior_mode!="horizontal_2d"||!cfg.go2_horizontal_velocity_prior_vertical_disabled)
     throw std::runtime_error("M3 expected unchanged horizontal transport");
   cfg.go2_horizontal_velocity_prior_mode="conditional_body_3d_pilot";
   cfg.go2_horizontal_velocity_prior_vertical_disabled=false;
 }
 ''')
 s=s.replace('pilot_mode_==2','pilot_mode_>=2').replace('pilot_mode_!=2','pilot_mode_<2')
 s=rep(s,'    setBlockIdentity(H, 0, V_ID);\n    R = diagonalMatrix(cwiseProduct(stdv, stdv));','    setBlockIdentity(H, 0, V_ID);\n    if(pilot_mode_==3)H=pilotBodyH(pvacur_,3);\n    R = diagonalMatrix(cwiseProduct(stdv, stdv));')
 p.write_text(s)
 runtime=dest/"core/src/runtime/port_runtime.cpp";rs=runtime.read_text()
 rs=rep(rs,"#include <algorithm>","#include <algorithm>\n#include <cstdlib>")
 rs=rep(rs,"  const bool go2_horizontal_active = options.go2_horizontal_velocity_update_count > 0;",r"""
  const char* research_mode=std::getenv("LEGSA_PILOT_AID_MODE");
  const bool research_body3d=research_mode && std::string(research_mode)=="3";
  if(research_body3d && (options.algorithm_id!="LegSA_Paper_V1" ||
      (options.run_id.rfind("IMUFIX_HEADING_",0)!=0 && options.run_id.rfind("IMUFIX_CLAIM_HEADING_",0)!=0)))
    throw std::runtime_error("RESEARCH_BODY3D_IDENTITY_MISMATCH");
  // Diagnostic model identity only: keep true 3D and horizontal counters distinct.
  const auto& velocity_status=options.go2_velocity_prior_diagnostic_status;
  const bool go2_horizontal_active = research_body3d
      ? (options.algorithm_id=="LegSA_Paper_V1" &&
         (options.run_id.rfind("IMUFIX_HEADING_",0)==0 || options.run_id.rfind("IMUFIX_CLAIM_HEADING_",0)==0) &&
         velocity_status.solver_enabled && velocity_status.update_count>0 &&
         options.go2_horizontal_velocity_update_count==0 &&
         velocity_status.horizontal_update_count==0 &&
         !velocity_status.horizontal_only && !velocity_status.vertical_disabled)
      : options.go2_horizontal_velocity_update_count>0;""")
 runtime.write_text(rs)
 p=dest/"core/include/legsa_v23_port_core/pilot_aiding.hpp";s=p.read_text()
 s=rep(s,'pilotBodyH(const NavState& s)','pilotBodyH(const NavState& s,int dim=2)')
 s=rep(s,'Matrix H(2,RANK,0.0)','Matrix H(dim,RANK,0.0)')
 s=rep(s,'for(int i=0;i<2;++i)for(int j=0;j<3;++j)','for(int i=0;i<dim;++i)for(int j=0;j<3;++j)');p.write_text(s)
 test=dest/"pilot_test.cpp";s=test.read_text()
 s=rep(s,'const Matrix H=pilotBodyH(s);','const Matrix H=pilotBodyH(s,3);const Matrix H2=pilotBodyH(s);for(int r=0;r<2;++r)for(int c=0;c<RANK;++c)if(H(r,c)!=H2(r,c))throw std::runtime_error("unchanged xy Jacobian");')
 s=rep(s,'for(int i=0;i<2;++i)mx','for(int i=0;i<3;++i)mx');test.write_text(s)
 subprocess.run(["cmake","-S",str(dest),"-B",str(a.stage/"BUILD"),"-DCMAKE_BUILD_TYPE=Release"],check=True)
 subprocess.run(["cmake","--build",str(a.stage/"BUILD"),"-j","4"],check=True)
 unit=json.loads(subprocess.check_output([str(a.stage/"BUILD/pilot_test")],text=True));emit(a.stage/"UNIT_TESTS.json",unit)
 checker=a.code/"scripts/paper_rebuild/research_audit_20261006/config_check.cpp"
 subprocess.run(["c++","-O2","-std=c++17","-I",str(dest/"core/include"),str(checker),str(a.stage/"BUILD/libcore.a"),"-o",str(a.stage/"BUILD/config_check")],check=True)
 emit(a.stage/"BUILD_IDENTITY.json",{"parent_build_identity_sha256":sha(old/"BUILD_IDENTITY.json"),"parent_binary_sha256":OLD_BINARY,"base_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip(),"sandbox_source_sha256":{str(p.relative_to(dest)):sha(p) for p in dest.rglob("*") if p.is_file()},"binary_sha256":sha(a.stage/"BUILD/SOLVER"),"unit_tests":unit,"effective_M3_model":"3D body velocity; std_z=.132838; inherited parser transport horizontal_2d overridden only inside isolated GIEngine constructor"})
 print("BUILD_AND_3D_JACOBIAN_PASS",flush=True)
def prepare(a):
 from legsa_gins.paper_rebuild.imu_contract_repair import clone_fields
 from legsa_gins.paper_rebuild.clean6_sensor_v21.providers import interpolate_a1
 old=json.loads((a.prior/"PLAN.json").read_text());sealed=json.loads((a.prior/"ALL_NATIVE_SEALED.json").read_text())
 assert sealed["status"]=="SEALED" and sha(a.prior/"PLAN.json")==sealed["plan_sha256"]
 chosen={(r["case"],r["mode"]):r for r in old["runs"]}
 inp=a.stage/"INPUTS";inp.mkdir(parents=True,exist_ok=False)
 body=Path(yaml.safe_load(Path(chosen[("C00",2)]["config"]).read_text())["go2_horizontal_velocity_prior_path"])
 assert sha(body)==old["inputs"][str(body)]
 b=pd.read_csv(body);assert np.isfinite(b[["vn","ve","vd"]]).all().all() and b.update_flag.all()
 body3=inp/"SDK_BODY_3D.csv"
 with body.open(newline="") as f:
  reader=csv.DictReader(f);fields=reader.fieldnames;tokens=list(reader)
 for row in tokens:row["std_vd"]="0.132838";row["prior_policy"]="conditional_body_3d_fixed_isotropic_sigma"
 with body3.open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(tokens)
 clean=yaml.safe_load(Path(chosen[("C00",0)]["config"]).read_text())
 gnss=Path(clean["gnsspath"]);assert sha(gnss)==old["inputs"][str(gnss)]
 lines=gnss.read_bytes().splitlines(keepends=True);new=[];changed=0
 import re
 for line in lines:
  tokens=list(re.finditer(rb"\S+",line))
  if len(tokens)==18 and 196.2<=float(tokens[0].group())<216.2:
   j=tokens[17];line=line[:j.start()]+b"0"+line[j.end():];changed+=1
  new.append(line)
 assert changed==100
 h20=inp/"H20_SOURCE_LOSS.gnss";h20.write_bytes(b"".join(new))
 aa=np.loadtxt(gnss);bb=np.loadtxt(h20);assert np.array_equal(aa[:,:17],bb[:,:17])
 # Recover old 1 Hz A1 support from the exact base GNSS18 table associated with the old HV.
 legacy=Path(clean["go2_horizontal_velocity_prior_path"]);base=legacy.parent/"GNSS18.gnss"
 base_table=np.loadtxt(base);a1=base_table[base_table[:,17]==1,0];assert np.allclose(np.diff(a1),1.)
 kept=a1[~((a1>=196.2)&(a1<216.2))]
 hv=pd.read_csv(legacy);t=hv.time.to_numpy();_,support=interpolate_a1(t,kept,np.zeros(len(kept)),maximum_gap_s=1.2)
 original=hv.update_flag.astype(str).str.lower().isin(["true","1"]).to_numpy()
 hv["update_flag"]=original&support;hv["a1_heading_valid"]=support
 if "valid" in hv:hv["valid"]=original&support
 hv.loc[~support,"reason_codes"]="H20_A1_source_unavailable_no_interpolation"
 hvpath=inp/"H20_LEGACY_HV_SOURCE_MASK.csv"
 with legacy.open(newline="") as f:
  reader=csv.DictReader(f);fields=reader.fieldnames;tokens=list(reader)
 for i,row in enumerate(tokens):
  row["update_flag"]=str(bool(original[i]&support[i]));row["a1_heading_valid"]=str(bool(support[i]))
  if "valid" in row:row["valid"]=str(bool(original[i]&support[i]))
  if not support[i]:row["reason_codes"]="H20_A1_source_unavailable_no_interpolation"
 with hvpath.open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(tokens)
 inside=(t>=196.2)&(t<216.2);assert not hv.update_flag[inside].any()
 # The legacy nearest-sample tolerance cannot pull supported HV across this fault.
 active=t[hv.update_flag.to_numpy()]
 assert all(np.min(abs(active-x))>.08 for x in bb[(bb[:,0]>=196.2)&(bb[:,0]<216.2),0])
 runs=[];reused=[]
 for case in ("C00","D61_20s_seed_00","D62_20s_seed_00"):
  for mode in (0,2):
   r=chosen[(case,mode)];saved=next(x for x in sealed["records"] if x["run_id"]==r["run_id"])
   d=a.prior/"NATIVE"/r["run_id"];assert sha(d/"KF_GINS_Navresult.nav")==saved["nav_sha256"] and sha(d/"KF_GINS_STD.txt")==saved["std_sha256"]
   err=a.prior/"EVALUATION"/r["run_id"]/"FROZEN_EVALUATOR/error_series.csv";assert err.exists()
   reused.append({"case":case,"mode":mode,"run_id":r["run_id"],"native_dir":str(d),"error_path":str(err),"error_sha256":sha(err),"nav_sha256":saved["nav_sha256"],"std_sha256":saved["std_sha256"],"execution_commit":saved["execution_commit"],"binary_sha256":OLD_BINARY})
 def add(case,mode):
  source=chosen[(case,2)] if case!="H20" else chosen[("D61_20s_seed_00",mode if mode in(0,2) else 2)]
  rid=("IMUFIX_HEADING_" if case=="C00" else "IMUFIX_CLAIM_HEADING_")+case+"_M"+str(mode)+"_T02"
  fields={"run_id":rid,"run_label":rid,"outputpath":str(a.stage/"NATIVE"/rid)}
  if case=="H20":
   fields.update({k:clean[k] for k in ROLES});fields["gnsspath"]=str(h20);fields["go2_horizontal_velocity_prior_path"]=str(hvpath if mode==0 else body)
  if mode==3:fields["go2_horizontal_velocity_prior_path"]=str(body3)
  payload,changes=clone_fields(Path(source["config"]).read_bytes(),fields)
  cfg=a.stage/"CONFIGS"/(rid+".yaml");cfg.parent.mkdir(exist_ok=True);cfg.write_bytes(payload)
  binary=a.stage/"BUILD/SOLVER" if mode==3 else a.prior/"BUILD/SOLVER"
  runs.append({"run_id":rid,"case":case,"mode":mode,"config":str(cfg),"config_sha256":sha(cfg),"binary":str(binary),"binary_sha256":sha(binary),"outage":None if case=="C00" else [196.2,216.2],"changes":changes,"source_config_sha256":sha(source["config"]),"effective_velocity_dimension":3 if mode==3 else 2,"effective_velocity_frame":"NED_legacy_A1" if mode==0 else "conditional_body_FRD","effective_vertical_disabled":mode!=3})
 for case in ("C00","D61_20s_seed_00","D62_20s_seed_00"):add(case,3)
 for mode in (0,2,3):add("H20",mode)
 pins={}
 for r in runs:
  cfg=yaml.safe_load(Path(r["config"]).read_text())
  for k in ROLES:pins[cfg[k]]=sha(cfg[k])
 check=subprocess.run([str(a.stage/"BUILD/config_check")]+[r["config"] for r in runs],capture_output=True,text=True)
 emit(a.stage/"CONFIG_LOADER_ADMISSION.json",{"returncode":check.returncode,"configs":len(runs),"native_solver_calls":0,"stdout":check.stdout,"stderr":check.stderr,"checker_sha256":sha(a.stage/"BUILD/config_check")})
 assert check.returncode==0 and len(check.stdout.splitlines())==6
 emit(a.stage/"PLAN.json",{"schema":"heading_reassessment.v1","sequence":old["sequence"],"runs":runs,"reused":reused,"inputs":pins,"native_budget":6,"prior_post_runtime_rejected_solver_calls":1,"total_solver_call_target":7,"prior_failed_invocation_sha256":sha(a.stage.parent/"NATIVE/IMUFIX_HEADING_C00_M3/INVOCATION.json"),"parent_plan_sha256":sha(a.prior/"PLAN.json"),"parent_seal_sha256":sha(a.prior/"ALL_NATIVE_SEALED.json"),"build_identity_sha256":sha(a.stage/"BUILD_IDENTITY.json"),"body_std_xyz_mps":[.132838]*3,"new_z_calibrated":False,"body_point_offset_assumption_m":[0,0,0],"H20":{"semantics":"A1 source loss; all non-yaw GNSS18 bytes retained; legacy HV support re-gated, no interpolation through removed A1 epochs","masked_gnss_rows":changed,"legacy_a1_source":str(base),"legacy_a1_source_sha256":sha(base),"removed_a1_rows":int(len(a1)-len(kept)),"hv_disabled_rows":int(np.sum(original&~support)),"maximum_interpolation_gap_s":1.2,"fault_HV_tolerance_guard_passed":True}})
 print("PREPARED_6_NEW_6_REUSED_NO_REFERENCE",flush=True)
def native(a):
 from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
 plan=json.loads((a.stage/"PLAN.json").read_text())
 for p,d in plan["inputs"].items():assert sha(p)==d
 commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip();records=[]
 assert a.execution_commit and commit==a.execution_commit
 for r in plan["runs"]:
  assert sha(r["binary"])==r["binary_sha256"] and sha(r["config"])==r["config_sha256"]
  out=a.stage/"NATIVE"/r["run_id"];out.mkdir(parents=True,exist_ok=False);audit=out/"AID_EVENTS.csv";audit.write_text("state_time,rp_sample_time,hv_sample_time,rp_accepted,hv_accepted\n")
  env={**os.environ,"LEGSA_PILOT_AID_MODE":str(r["mode"]),"LEGSA_PILOT_AID_AUDIT":str(audit),"OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1"}
  cmd=["strace","-f","-qq","-s","4096","-e","trace=openat,execve","-o",str(out/"OPENAT.strace"),r["binary"],"--config",r["config"],"--output-dir",str(out)]
  t=time.monotonic()
  with (out/"stdout.log").open("x") as o,(out/"stderr.log").open("x") as e:p=subprocess.run(cmd,cwd=a.code,env=env,stdout=o,stderr=e,timeout=1200)
  opens=audited_open_records(out/"OPENAT.strace",a.code);tr=sum(x["path"]==plan["sequence"]["trace_path"] for x in opens)
  rec={**r,"returncode":p.returncode,"runtime_seconds":time.monotonic()-t,"online_trace_reads":tr,"execution_commit":commit}
  emit(out/"INVOCATION.json",rec)
  if p.returncode or tr:raise RuntimeError("Native failed; no retry or evaluator")
  nav=np.loadtxt(out/"KF_GINS_Navresult.nav",comments="%");std=np.loadtxt(out/"KF_GINS_STD.txt",comments="%")
  assert len(nav)==len(std)==56642 and np.isfinite(nav).all() and np.isfinite(std).all()
  covdata=np.loadtxt(out/"STATE_COVARIANCE_SUPPORT.csv",delimiter=",",skiprows=1,ndmin=2);cov=covdata[:,16:].reshape(-1,21,21)
  scale=np.maximum(1,np.max(abs(cov),axis=(1,2)));eig=np.linalg.eigvalsh((cov[:,:15,:15]+cov[:,:15,:15].transpose(0,2,1))*.5);asym=float(np.max(np.max(abs(cov-cov.transpose(0,2,1)),axis=(1,2))/scale))
  assert np.isfinite(cov).all() and np.all(eig[:,0]>=-1e-10*scale) and asym<1e-8
  rec["covariance"]={"samples":len(cov),"fault_samples":int(np.sum((covdata[:,0]>=196.2)&(covdata[:,0]<216.2))),"min_active_eigen":float(eig.min()),"relative_asymmetry":asym,"finite":True}
  ev=pd.read_csv(audit)
  if r["mode"]>=2:
   for kind,age in [("rp",.02),("hv",.08)]:
    used=ev[ev[kind+"_accepted"]>0];dt=used.state_time-used[kind+"_sample_time"];assert used[kind+"_sample_time"].is_unique and (dt>=0).all() and (dt<=age+1e-9).all()
   fault=ev[(ev.state_time>=196.2)&(ev.state_time<216.2)];rec["independent_fault_accepts"]={"RP":int(fault.rp_accepted.sum()),"HV":int(fault.hv_accepted.sum())}
  rec.update(status="SEALED",output_rows=len(nav),nav_sha256=sha(out/"KF_GINS_Navresult.nav"),std_sha256=sha(out/"KF_GINS_STD.txt"),time_keys_sha256=hashlib.sha256(nav[:,1].copy().tobytes()).hexdigest())
  emit(out/"RESULT.json",rec);records.append(rec);print(r["run_id"],"SEALED",flush=True)
 assert len(records)==6 and len(set(r["time_keys_sha256"] for r in records))==1
 emit(a.stage/"ALL_NATIVE_SEALED.json",{"status":"SEALED","plan_sha256":sha(a.stage/"PLAN.json"),"records":records})
 print("ALL_6_NATIVE_SEALED",flush=True)
def evaluate(a):
 from legsa_gins.paper_rebuild.imu_contract_repair import transform_nav,write_transformed_nav,evaluate as evaluator,EVALUATOR_SHA256
 plan=json.loads((a.stage/"PLAN.json").read_text());seal=json.loads((a.stage/"ALL_NATIVE_SEALED.json").read_text());seq=plan["sequence"]
 assert seal["status"]=="SEALED" and len(seal["records"])==6 and seal["plan_sha256"]==sha(a.stage/"PLAN.json") and sha(a.evaluator)==EVALUATOR_SHA256
 for r in seal["records"]:
  out=a.stage/"NATIVE"/r["run_id"];nav=out/"KF_GINS_Navresult.nav";assert sha(nav)==r["nav_sha256"]
  root=a.stage/"EVALUATION"/r["run_id"];root.mkdir(parents=True,exist_ok=False);target=root/"EVAL_NAV.nav"
  write_transformed_nav(nav,target,transform_nav(np.loadtxt(nav,ndmin=2,comments="%"),seq["baseline_median_m"]))
  result=evaluator(evaluator=a.evaluator,trace=Path(seq["trace_path"]),nav=target,std=out/"KF_GINS_STD.txt",outdir=root/"FROZEN_EVALUATOR",base_time=seq["base_time"],window=seq["window"],trace_sha256=seq["trace_sha256"],code_root=a.code,raw_root=Path(seq["raw_root"]),clean_root=a.clean_root,instrument=True,consistency_policy="canonical_v2_wgs84_full_support")
  emit(root/"EVALUATOR_RESULT.json",result);assert result["audit"]["passed"] and result["capture"]["consistency"]["passed"]
  print("evaluated",r["run_id"],flush=True)
 emit(a.stage/"EVALUATION_COMPLETE.json",{"evaluations":6,"reused_evaluations":6,"plan_sha256":sha(a.stage/"PLAN.json")})
def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["build","prepare","native","evaluate"])
 for key in ("code","stage","prior","evaluator","clean-root"):p.add_argument("--"+key,type=Path)
 p.add_argument("--execution-commit");a=p.parse_args();assert os.uname().sysname=="Linux";globals()[a.phase](a)
if __name__=="__main__":main()
