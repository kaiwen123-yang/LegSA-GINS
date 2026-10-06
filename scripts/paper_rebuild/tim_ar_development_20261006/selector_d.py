#!/usr/bin/env python3
"""D: bounded RP penalty selector, isolated frozen-model development."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,math,os,signal,subprocess,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("frozen_synthetic2",ROOT/"scripts/paper_rebuild/ar_tim_exploration_20261006/synthetic2.py")
s2=importlib.util.module_from_spec(spec);spec.loader.exec_module(s2)
prior=s2.prior
KAPPA=3.0
KAPPA2=9.0
SEEDS={"G121_B0":2610071210,"G121_B90":2610071219,"G1221_B0":2610071220,"G1221_B90":2610071229}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x") as f:json.dump(prior.jsonable(x),f,indent=2,ensure_ascii=False,allow_nan=False)
def choose_d(a,b):
 if not a["candidate_available"] or not b["candidate_available"]:
  return {"available":False,"selected_branch":None,"reason":"BOTH_GLOBAL_CERTIFICATES_REQUIRED"}
 # These are FULL whitened original observation costs, not reduced C-ILS scores.
 fa=float(a["raw_whitened_residual_squared"])+KAPPA2
 fb=float(b["raw_whitened_residual_squared"])+float(b["prior_residual_sigma"])**2
 eta=float(b["raw_whitened_residual_squared"])-float(a["raw_whitened_residual_squared"])
 assert eta>=-1e-6
 branch="B" if fb<fa else "A";x=b if branch=="B" else a
 raw_increase=float(x["raw_whitened_residual_squared"])-float(a["raw_whitened_residual_squared"])
 assert -1e-6<=raw_increase<=KAPPA2+1e-6
 jactual=float(x["raw_whitened_residual_squared"])+min(float(x["prior_residual_sigma"])**2,KAPPA2)
 assert math.isclose(jactual,min(fa,fb),abs_tol=1e-7,rel_tol=1e-9)
 if branch=="B":assert abs(x["prior_residual_sigma"])<=KAPPA+1e-6
 else:assert abs(x["prior_residual_sigma"])>=KAPPA-1e-6
 return {"available":True,"selected_branch":branch,"fault_branch_score":fa,"healthy_branch_score":fb,"healthy_minus_fault_score":fb-fa,"raw_cost_increase_B_vs_A":eta,"selected_raw_cost_increase_vs_A":raw_increase,"full_bounded_objective":jactual,"integer_correct":x["integer_correct"],"ambiguity":x["ambiguity"],"projected_heading_error_deg":x.get("projected_heading_error_deg"),"baseline_angle_error_deg":x.get("baseline_angle_error_deg"),"selected_prior_residual_sigma":x["prior_residual_sigma"],"global_minimum_certified_conditional_on_branch_certificates":True}
def unit(a):
 rng=np.random.default_rng(202610070);n=0
 for _ in range(1000):
  raw=rng.exponential(10,size=50);res=rng.normal(0,5,size=50)
  ia=int(np.argmin(raw));ib=int(np.argmin(raw+res**2))
  def entry(i):
   return {"candidate_available":True,"raw_whitened_residual_squared":float(raw[i]),"prior_residual_sigma":float(res[i]),"integer_correct":True,"ambiguity":[i],"solver_reduced_cost_IGNORED":9999-i}
  answer=choose_d(entry(ia),entry(ib))
  assert math.isclose(answer["full_bounded_objective"],float(np.min(raw+np.minimum(res**2,KAPPA2))),rel_tol=1e-12,abs_tol=1e-12);n+=1
 # A missing branch certificate cannot become a certified D output.
 assert not choose_d({"candidate_available":False},{"candidate_available":True})["available"]
 emit(a.stage/"DESIGN_UNIT.json",{"passed":True,"finite_set_min_interchange_cases":n,"missing_certificate_gate_passed":True,"CILS_calls":0,"parameter_selection_from_validation":False,"kappa":KAPPA,"seed":202610070,"meaning":"Algebra/selector correctness only, not statistical estimator validation"})
 print("DESIGN_UNIT_PASS",n,"CILS=0",flush=True)
def prepare(a):
 old=json.loads((a.previous/"SYNTHETIC2_PLAN.json").read_text())
 s2.pincheck(old,a.code)
 pins=old["source_pins"].copy();pins["scripts/paper_rebuild/tim_ar_development_20261006/selector_d.py"]=sha(Path(__file__))
 inputs={str(a.previous/"SYNTHETIC2_PLAN.json"):sha(a.previous/"SYNTHETIC2_PLAN.json"),old["lambda_library"]:sha(old["lambda_library"])}
 models=[]
 for source in old["models"]:
  clean=json.loads(json.dumps(source));clean["case_id"]=source["case_id"]+"_NEW";clean["seed"]=SEEDS[source["case_id"]];clean["source_group"]=source["case_id"];clean["measurement_fault"]="NONE"
  A=np.array(source["ambiguity_design_m"]);B=np.array(source["baseline_design"]);Q=np.array(source["covariance_m2"]);b=np.array(source["true_baseline_ecef_m"]);N=np.array(source["integer_truth"])
  noise=np.linalg.cholesky(Q)@np.random.default_rng(clean["seed"]).standard_normal(len(Q))
  clean["gaussian_noise_m"]=noise.tolist();clean.pop("gaussian_standard_draw",None);clean["observation_m"]=(B@b+A@N+noise).tolist()
  roll=s2.RP_FAULT if source["baseline_bearing_ned_deg"]==0 else -s2.RP_FAULT
  clean["conditions"]=[{"name":"NOMINAL","reported_roll_rad":0.,"reported_pitch_rad":0.,"vertical_prior_m":0.},{"name":"RP_BIAS","reported_roll_rad":roll,"reported_pitch_rad":0.,"vertical_prior_m":-.350*math.sin(roll)}]
  models.append(clean)
  fault=json.loads(json.dumps(clean));fault["case_id"]=source["case_id"]+"_PHASE";fault["measurement_fault"]="PHASE_NONINTEGER_BIAS_FIRST_NONPIVOT"
  m=A.shape[1];wavelength=float(A[m,0]);assert wavelength>0
  fault["phase_bias_cycles"]=.25;fault["phase_bias_m"]=.25*wavelength;fault["phase_fault_row"]=m;fault["observation_m"][m]+=fault["phase_bias_m"]
  fault["conditions"]=[{"name":"PHASE_BIAS","reported_roll_rad":0.,"reported_pitch_rad":0.,"vertical_prior_m":0.}]
  assert np.array_equal(np.array(clean["gaussian_noise_m"]),np.array(fault["gaussian_noise_m"]))
  models.append(fault)
 assert len(models)==8 and sum(len(m["conditions"]) for m in models)==12
 emit(a.stage/"PLAN.json",{"schema":"bounded_rp_penalty_D.v1","input_pins":inputs,"source_pins":pins,"lambda_library":old["lambda_library"],"models":models,"kappa":KAPPA,"kappa2":KAPPA2,"parameter_origin":"Fixed engineering truncation at 3 normalized residual units; not calibrated risk, not tuned using old/new result errors","prior_sigma_m":.030,"length_m":.350,"max_A_calls":8,"max_B_calls":12,"max_calls_total":20,"max_search_seconds":60,"max_nodes":1000000,"max_process_group_seconds":1500,"truth_known":True,"new_independent_noise_draws":4,"logical_condition_rows":12,"unique_measurement_instances":8,"phase_fault_changes_true_integer":False,"original_raw_reads_allowed":0,"reference_reads_allowed":0,"formal_integer_acceptance_defined":False,"automatic_EKF_integration_allowed":False,"predecessor_plan_sha256":sha(a.previous/"SYNTHETIC2_PLAN.json")})
 print("PREPARED",8,"unique measurements",12,"conditions",20,"calls budget",flush=True)
def run(a):
 plan=json.loads((a.stage/"PLAN.json").read_text());s2.pincheck(plan,a.code)
 assert a.execution_commit==subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip()
 out=a.stage/"RESULTS";out.mkdir(exist_ok=False);ledger=a.stage/"CALL_LEDGER.jsonl";calls=0;rows=[];amap={}
 def log(r):
  with ledger.open("a") as f:f.write(json.dumps(r)+"\n");f.flush();os.fsync(f.fileno())
 def call(model,r,method,d=None,val=None):
  nonlocal calls
  calls+=1;log({"event":"START","call":calls,"case_id":r["case_id"],"method":method});t=time.monotonic()
  try:
   solution=prior.solve(model,plan["lambda_library"],d,val)
   result=s2.evaluate_candidate(solution,r,model,np.array(r["down_row_ecef"]),0. if val is None else val)
  except (prior.raw.RawBackendError,ValueError,np.linalg.LinAlgError) as ex:result={"candidate_available":False,"integer_correct":False,"failure":type(ex).__name__+":"+str(ex)}
  result["elapsed_s"]=time.monotonic()-t;log({"event":"END","call":calls,"candidate":result["candidate_available"]});return result
 for r in plan["models"]:
  model=s2.model_from(r);aa=call(model,r,"A");amap[r["case_id"]]=aa;emit(out/(r["case_id"]+"_A.json"),aa)
  for cond in r["conditions"]:
   d=np.array(r["down_row_ecef"]);value=cond["vertical_prior_m"]
   bb=call(model,r,cond["name"],d,value)
   # Recompute cached A's prior residual for this exact condition; raw objective unchanged.
   ac=json.loads(json.dumps(aa))
   if ac["candidate_available"]:ac["prior_residual_sigma"]=float((d@np.array(ac["baseline_ecef_m"])-value)/.030)
   cc=bool(ac["candidate_available"] and bb["candidate_available"] and ac["ambiguity"]==bb["ambiguity"])
   dd=choose_d(ac,bb);rec={"case_id":r["case_id"],"source_group":r["source_group"],"condition":cond,"measurement_fault":r["measurement_fault"],"integer_truth":r["integer_truth"],"A":ac,"B":bb,"C_retained":cc,"C_correct_retained":bool(cc and bb["integer_correct"]),"C_wrong_retained":bool(cc and not bb["integer_correct"]),"D":dd}
   emit(out/(r["case_id"]+"_"+cond["name"]+".json"),rec);rows.append(rec)
   print(r["case_id"],cond["name"],"A",ac["integer_correct"],"B",bb["integer_correct"],"C",cc,"D",dd.get("selected_branch"),dd.get("integer_correct"),flush=True)
 assert calls==20 and len(rows)==12;s2.pincheck(plan,a.code)
 emit(a.stage/"SEAL.json",{"execution_commit":a.execution_commit,"plan_sha256":sha(a.stage/"PLAN.json"),"calls":calls,"unique_A":amap,"records":rows,"result_hashes":{p.name:sha(p) for p in out.glob("*.json")},"ledger_sha256":sha(ledger),"no_method_parameter_changed":True})
def supervise(a):
 plan=json.loads((a.stage/"PLAN.json").read_text());s2.pincheck(plan,a.code);trace=a.stage/"IO.strace";assert not trace.exists()
 cmd=["strace","-f","-qq","-xx","-s","8192","-e","trace=open,openat,execve","-o",str(trace),sys.executable,str(Path(__file__).resolve()),"run","--code",str(a.code),"--stage",str(a.stage),"--execution-commit",a.execution_commit]
 t=time.monotonic();child=subprocess.Popen(cmd,start_new_session=True)
 try:rc=child.wait(timeout=1500)
 except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();rc=124
 forbidden=[p for p,ro in prior.open_paths(trace) if "/data/raw/" in p or Path(p).name.startswith("trace_vrtk")]
 emit(a.stage/"IO_AUDIT.json",{"passed":rc==0 and not forbidden,"exit_code":rc,"elapsed_s":time.monotonic()-t,"raw_or_reference_open_paths":forbidden,"trace_sha256":sha(trace)})
 assert rc==0 and not forbidden
def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["unit","prepare","run","supervise"]);p.add_argument("--code",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--previous",type=Path);p.add_argument("--execution-commit");a=p.parse_args();assert os.uname().sysname=="Linux";a.stage.mkdir(parents=True,exist_ok=True);globals()[a.phase](a)
if __name__=="__main__":main()
