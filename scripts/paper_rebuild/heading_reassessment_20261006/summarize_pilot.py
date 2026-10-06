#!/usr/bin/env python3
"""Derive saved-output summaries only: no raw GNSS, reference, solver or evaluator access."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 plan=json.loads((a.stage/"PLAN.json").read_text());seal=json.loads((a.stage/"ALL_NATIVE_SEALED.json").read_text());done=json.loads((a.stage/"EVALUATION_COMPLETE.json").read_text())
 assert seal["status"]=="SEALED" and done["evaluations"]==6 and done["reused_evaluations"]==6 and seal["plan_sha256"]==sha(a.stage/"PLAN.json")
 allruns=[]
 for r in seal["records"]:
  native=a.stage/"NATIVE"/r["run_id"];ev=a.stage/"EVALUATION"/r["run_id"]
  allruns.append({**r,"origin":"new_T02","native":native,"error":ev/"FROZEN_EVALUATOR/error_series.csv","evaluation":ev/"EVALUATOR_RESULT.json"})
 for r in plan["reused"]:
  native=Path(r["native_dir"]);ev=Path(r["error_path"]).parent.parent
  allruns.append({**r,"origin":"reused_prior_pilot","native":native,"error":Path(r["error_path"]),"evaluation":ev/"EVALUATOR_RESULT.json","outage":None if r["case"]=="C00" else [196.2,216.2]})
 metrics=[];records=[];navkeys=[];errkeys=[];errorframes={}
 for r in allruns:
  native=r["native"];assert sha(native/"KF_GINS_Navresult.nav")==r["nav_sha256"] and sha(native/"KF_GINS_STD.txt")==r["std_sha256"]
  if "error_sha256" in r:assert sha(r["error"])==r["error_sha256"]
  nav=np.loadtxt(native/"KF_GINS_Navresult.nav",comments="%");err=pd.read_csv(r["error"]);t=err.time.to_numpy()
  navkeys.append(nav[:,1]);errkeys.append(t);errorframes[(r["case"],r["mode"])]=err
  domains={"full":np.ones(len(t),bool)}
  if r["outage"]:domains.update(outage=(t>=196.2)&(t<216.2),recovery_0_5=(t>216.2)&(t<=221.2))
  for domain,mask in domains.items():
   row={"case":r["case"],"mode":r["mode"],"origin":r["origin"],"run_id":r["run_id"],"domain":domain,"epochs":int(mask.sum()),"first_matched_time_s":float(t[mask][0]),"last_matched_time_s":float(t[mask][-1])}
   for col,label in [("horizontal_err_m","H"),("err_u_m","V"),("position_3d_err_m","D3"),("yaw_err_deg","yaw")]:
    values=err[col].to_numpy()[mask];unit="deg" if label=="yaw" else "m"
    row[label+"_RMSE_"+unit]=float(np.sqrt(np.mean(values*values)))
    row[label+"_last_supported_abs_"+unit]=float(abs(values[-1]))
    row[label+"_max_abs_"+unit]=float(np.max(abs(values)))
   metrics.append(row)
  evaluation=json.loads(r["evaluation"].read_text());assert evaluation["audit"]["trace_open_count"]==1 and evaluation["audit"]["passed"] and evaluation["capture"]["consistency"]["passed"]
  events=pd.read_csv(native/"AID_EVENTS.csv");trace=pd.read_csv(native/"SOURCE_AWARE_WEIGHT_TRACE.csv");manifest=json.loads((native/"RUN_MANIFEST.json").read_text())
  covdata=np.loadtxt(native/"STATE_COVARIANCE_SUPPORT.csv",delimiter=",",skiprows=1,ndmin=2);cov=covdata[:,16:].reshape(-1,21,21);eig=np.linalg.eigvalsh((cov[:,:15,:15]+cov[:,:15,:15].transpose(0,2,1))*.5)
  scale=np.maximum(1,np.max(abs(cov),axis=(1,2)));asym=np.max(np.max(abs(cov-cov.transpose(0,2,1)),axis=(1,2))/scale)
  assert np.isfinite(cov).all() and np.all(eig[:,0]>=-1e-10*scale) and asym<1e-8
  nr={k:r[k] for k in ("case","mode","run_id","origin","execution_commit","binary_sha256","nav_sha256","std_sha256")}
  nr.update(error_sha256=sha(r["error"]),nav_rows=len(nav),error_rows=len(t),nav_timekey_sha256=hashlib.sha256(nav[:,1].copy().tobytes()).hexdigest(),error_timekey_sha256=hashlib.sha256(t.copy().tobytes()).hexdigest(),covariance_samples=len(cov),fault_covariance_samples=int(np.sum((covdata[:,0]>=196.2)&(covdata[:,0]<216.2))),min_active_P_eigenvalue=float(eig.min()),max_relative_asymmetry=float(asym),frozen_scale_six_rows_cols_zero=bool(np.all(cov[:,15:,:]==0) and np.all(cov[:,:,15:]==0)),effective_velocity_dimension=3 if r["mode"]==3 else 2,effective_velocity_frame="NED_legacy_A1" if r["mode"]==0 else "conditional_body_FRD",effective_vertical_disabled=r["mode"]!=3,independent_ticks=len(events),independent_RP_accepted=int(events.rp_accepted.sum()),independent_HV_accepted=int(events.hv_accepted.sum()),manifest_generic_velocity_accepted=manifest["go2_velocity_prior_update_count"],manifest_horizontal_only_velocity_accepted=manifest["go2_horizontal_velocity_update_count"],offline_reference_reads_in_original_evaluation=1)
  for kind,age in [("rp",.02),("hv",.08)]:
   used=events[events[kind+"_accepted"]>0];dt=used.state_time-used[kind+"_sample_time"]
   if len(used):assert used[kind+"_sample_time"].is_unique and (dt>=0).all() and (dt<=age+1e-9).all()
  ev=events[(events.state_time>=196.2)&(events.state_time<216.2)]
  nr["controlled_window_state_time_independent_RP_accepted"]=int(ev.rp_accepted.sum())
  nr["controlled_window_state_time_independent_HV_accepted"]=int(ev.hv_accepted.sum())
  nr["source_trace_window_time_basis"]="measurement/sample timestamp, not state update time; boundary counts can differ from AID_EVENTS"
  for scope,mask in [("full",np.ones(len(trace),bool)),("fault_source_timestamp",(trace.time>=196.2)&(trace.time<216.2))]:
   sub=trace[mask];nr[scope+"_source_accepted"]={s:int(z.accepted.sum()) for s,z in sub.groupby("source_id")}
  hv=trace[trace.source_id=="go2_horizontal_velocity"]
  assert nr["full_source_accepted"]["go2_horizontal_velocity"]==nr["manifest_generic_velocity_accepted"]
  if r["mode"]>=2:assert nr["independent_HV_accepted"]==nr["manifest_generic_velocity_accepted"]
  if r["mode"]==3:
   assert set(hv.dof)=={3} and nr["manifest_horizontal_only_velocity_accepted"]==0 and not manifest["go2_horizontal_velocity_prior_vertical_disabled"]
   assert hv.metadata_summary.str.contains("active_dimensions=3").all()
  if r["case"]=="H20":
   assert nr["fault_source_timestamp_source_accepted"].get("dual_antenna_yaw",0)==0
   if r["mode"]==0:assert nr["fault_source_timestamp_source_accepted"].get("go2_horizontal_velocity",0)==0
  records.append(nr)
 assert len(allruns)==12 and all(np.array_equal(x,navkeys[0]) for x in navkeys) and all(np.array_equal(x,errkeys[0]) for x in errkeys)
 result=pd.DataFrame(metrics).sort_values(["case","mode","domain"])
 def get(case,mode):return result[(result["case"]==case)&(result["mode"]==mode)&(result["domain"]==("full" if case=="C00" else "outage"))].iloc[0]
 comparisons=[]
 for case in ("C00","D61_20s_seed_00","D62_20s_seed_00","H20"):
  for left,right in ((0,2),(2,3),(0,3)):
   b,c=get(case,left),get(case,right);row={"case":case,"baseline_mode":left,"candidate_mode":right}
   for metric in ("H_RMSE_m","V_RMSE_m","D3_RMSE_m","yaw_RMSE_deg"):
    row[metric+"_change"]=float(c[metric]-b[metric]);row[metric+"_reduction_pct"]=float(100*(1-c[metric]/b[metric]))
   comparisons.append(row)
 controls=[]
 for mode in (0,2,3):
  clean=errorframes[("C00",mode)];fault=errorframes[("H20",mode)]
  mask=(clean.time.to_numpy()>=196.2)&(clean.time.to_numpy()<216.2)
  q={"mode":mode,"epochs":int(mask.sum()),"first_matched_time_s":float(clean.time.to_numpy()[mask][0]),"last_matched_time_s":float(clean.time.to_numpy()[mask][-1])}
  for col,label in (("yaw_err_deg","yaw_RMSE_deg"),("horizontal_err_m","H_RMSE_m"),("err_u_m","V_RMSE_m")):
   before=float(np.sqrt(np.mean(clean[col].to_numpy()[mask]**2)));after=float(np.sqrt(np.mean(fault[col].to_numpy()[mask]**2)))
   q["C00_same_window_"+label]=before;q["H20_"+label]=after;q["H20_minus_C00_"+label]=after-before
  controls.append(q)
 summary={"status":"COMPLETE_CONDITIONAL_DIAGNOSTIC_NOT_PRODUCTION","scientific_execution_commit":seal["records"][0]["execution_commit"],"plan_sha256":sha(a.stage/"PLAN.json"),"native_seal_sha256":sha(a.stage/"ALL_NATIVE_SEALED.json"),"solver_calls_this_round":7,"post_full_propagation_identity_rejections":1,"pre_input_solver_rejections":0,"new_scientific_native_completed":6,"new_evaluations_completed":6,"old_native_and_evaluations_reused":6,"new_online_reference_reads":0,"new_offline_reference_reads":6,"new_config_checker_processes":3,"new_cpp_unit_test_processes":3,"all_12_exact_nav_time_keys_equal":True,"all_12_exact_evaluator_time_keys_equal":True,"registered_fault_interval_s":[196.2,216.2],"fault_terminal_role":"last supported matched epoch strictly before 216.2; not exact endpoint","frame_and_velocity_point_independently_calibrated":False,"reference":"commercial fused reference with shared GNSS lineage; not independent truth","runtime_environment":{"os":"Ubuntu22.04.5 WSL2 on E-drive","python":"3.10.12","gcc":"11.4.0","cmake":"3.22.1","numpy":"1.26.4","pandas":"2.2.3","pyyaml":"6.0.3"},"payload_alias":"<WSL_SCRATCH>/heading_reassessment_20261006/ATTEMPT_02","records":records,"comparisons":comparisons,"H20_same_window_control":controls}
 a.out.mkdir(parents=True,exist_ok=True)
 result.to_csv(a.out/"PILOT_RESULTS.csv",index=False);pd.DataFrame(comparisons).to_csv(a.out/"PILOT_COMPARISONS.csv",index=False)
 pd.DataFrame(controls).to_csv(a.out/"H20_SAME_WINDOW_CONTROL.csv",index=False)
 (a.out/"PILOT_EXECUTION_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
 print(result[(result.domain=="outage")|((result["case"]=="C00")&(result.domain=="full"))][["case","mode","H_RMSE_m","V_RMSE_m","D3_RMSE_m","yaw_RMSE_deg","last_matched_time_s"]].to_string(index=False))
if __name__=="__main__":main()
