#!/usr/bin/env python3
"""Known-integer mechanism: reads sealed stage1 geometry; no raw/reference reads."""
from pathlib import Path
from types import SimpleNamespace
import argparse,hashlib,importlib.util,json,math,os,signal,subprocess,sys,time,csv
import numpy as np
SCRIPT_DIR=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("stage1_ar",SCRIPT_DIR/"experiment.py")
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
LENGTH=.350
SIGMA=.030
RP_FAULT=math.asin(.150/LENGTH)
INTEGER_VECTOR=[3,-2,5,-7]
SEEDS={(121,0):2606101210,(121,90):2606101219,(1221,0):2606101220,(1221,90):2606101229}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x") as f:json.dump(prior.jsonable(x),f,indent=2,ensure_ascii=False,allow_nan=False)
def pincheck(plan,code):
 for p,h in plan["source_pins"].items():assert sha(code/p)==h
 for p,h in plan["input_pins"].items():assert sha(p)==h
def model_from(r):
 return SimpleNamespace(observation_m=np.array(r["observation_m"]),baseline_design=np.array(r["baseline_design"]),ambiguity_design_m=np.array(r["ambiguity_design_m"]),covariance_m2=np.array(r["covariance_m2"]),satellites=tuple(r["satellites"]))
def prepare(a):
 stage1=json.loads((a.stage1/"REAL_SEAL.json").read_text());p1=json.loads((a.stage1/"PLAN.json").read_text())
 assert stage1["plan_sha256"]==sha(a.stage1/"PLAN.json")
 # Chronological first/last geometrically buildable records, never sorted by error.
 eligible=[r for r in stage1["epochs"] if "model" in r]
 selected=[eligible[0],eligible[-1]];assert [r["epoch_index"] for r in selected]==[121,1221]
 inputs={str(a.stage1/"REAL_SEAL.json"):sha(a.stage1/"REAL_SEAL.json"),str(a.stage1/"PLAN.json"):sha(a.stage1/"PLAN.json"),p1["lambda_library"]:sha(p1["lambda_library"])}
 for r in selected:
  path=a.stage1/"REAL"/("EPOCH_%03d.json"%r["epoch_index"]);assert sha(path)==stage1["record_hashes"][path.name];inputs[str(path)]=sha(path)
 cases=[]
 for r in selected:
  source=r["model"];anchor=np.asarray(r["spp"]["position_ecef_m"])
  R=np.column_stack([prior._ecef_vector_to_ned(np.eye(3)[i],anchor) for i in range(3)])
  assert np.linalg.norm(R@R.T-np.eye(3))<1e-12
  A=np.array(source["ambiguity_design_m"]);B=np.array(source["baseline_design"]);Q=np.array(source["covariance_m2"]);chol=np.linalg.cholesky(Q)
  m=A.shape[1];N=np.array(INTEGER_VECTOR[:m],dtype=int);assert m in (3,4)
  assert np.linalg.matrix_rank(np.hstack([A,B]))==m+3
  for bearing in (0,90):
   ned=LENGTH*np.array([math.cos(math.radians(bearing)),math.sin(math.radians(bearing)),0.]);ecef=R.T@ned
   assert abs(np.linalg.norm(ecef)-LENGTH)<1e-14
   seed=SEEDS[(r["epoch_index"],bearing)]
   z=np.random.default_rng(seed).standard_normal(len(Q));noise=chol@z;y=B@ecef+A@N+noise
   assert np.max(abs(y-B@ecef-A@N-noise))<1e-12
   cases.append({"case_id":"G%d_B%d"%(r["epoch_index"],bearing),"geometry_epoch_index":r["epoch_index"],"raw_geometry_time_s":r["time_s"],"seed":seed,"baseline_bearing_ned_deg":bearing,"true_body_roll_rad":0.,"true_body_pitch_rad":0.,"true_baseline_ned_m":ned.tolist(),"true_baseline_ecef_m":ecef.tolist(),"integer_truth":N.tolist(),"pivot":source["pivot"],"satellites":source["satellites"],"anchor_ecef_m":anchor.tolist(),"down_row_ecef":R[2].tolist(),"gaussian_standard_draw":z.tolist(),"gaussian_noise_m":noise.tolist(),"observation_m":y.tolist(),"baseline_design":B.tolist(),"ambiguity_design_m":A.tolist(),"covariance_m2":Q.tolist()})
 faults=[{"name":"RP_NOMINAL","roll_rad":0.,"pitch_rad":0.},{"name":"RP_ROLL_POS","roll_rad":RP_FAULT,"pitch_rad":0.},{"name":"RP_ROLL_NEG","roll_rad":-RP_FAULT,"pitch_rad":0.}]
 for f in faults:f["vertical_prior_m"]=-LENGTH*math.sin(f["roll_rad"])*math.cos(f["pitch_rad"])
 assert abs(faults[1]["vertical_prior_m"]+.15)<1e-14 and abs(faults[2]["vertical_prior_m"]-.15)<1e-14
 pins=p1["source_pins"].copy();pins["scripts/paper_rebuild/ar_tim_exploration_20261006/synthetic2.py"]=sha(Path(__file__))
 # Frozen evaluation source is pinned by provenance but never imported/called here.
 emit(a.stage/"SYNTHETIC2_PLAN.json",{"schema":"known_integer_mechanism.v1","stage1_execution_commit":stage1["execution_commit"],"stage1_plan_sha256":stage1["plan_sha256"],"input_pins":inputs,"source_pins":pins,"lambda_library":p1["lambda_library"],"length_m":LENGTH,"prior_sigma_m":SIGMA,"faults":faults,"models":cases,"max_A_calls":4,"max_B_calls":12,"max_C_calls":0,"max_calls_total":16,"per_call_timeout_s":60,"strict_node_limit":1000000,"process_group_timeout_s":1200,"reference_reads_allowed":0,"raw_reads_allowed":0,"formal_integer_acceptance_defined":False,"statistical_risk_estimation":False,"selection":"first and last geometrically buildable real records in chronological schedule; copied matrices and Q only; synthetic y replaces real observations"})
 print("PREPARED_ONLY",len(cases),"models",16,"max calls",flush=True)
def evaluate_candidate(x,r,model,d,val):
 out=prior.evidence(x,model,d,val)
 if not prior.ready(x):out.update(integer_correct=False,projected_heading_error_deg=None,baseline_angle_error_deg=None);return out
 n=x.best.ambiguity;b=x.best.baseline;true=np.array(r["true_baseline_ecef_m"]);ned=prior._ecef_vector_to_ned(b,np.array(r["anchor_ecef_m"]))
 bearing=math.degrees(math.atan2(ned[1],ned[0])) if np.linalg.norm(ned[:2])>1e-8 else None
 out.update(integer_correct=bool(np.array_equal(n,np.array(r["integer_truth"]))),baseline_ned_m=ned.tolist(),projected_heading_error_deg=float((bearing-r["baseline_bearing_ned_deg"]+180)%360-180) if bearing is not None else None,baseline_angle_error_deg=math.degrees(math.acos(np.clip(b@true/LENGTH**2,-1.,1.))))
 return out
def run(a):
 plan=json.loads((a.stage/"SYNTHETIC2_PLAN.json").read_text())
 assert a.execution_commit==subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip()
 pincheck(plan,a.code);out=a.stage/"RESULTS";out.mkdir(exist_ok=False);ledger=a.stage/"CALL_LEDGER.jsonl";rows=[];calls=0
 def log(x):
  with ledger.open("a") as f:f.write(json.dumps(x)+"\n");f.flush();os.fsync(f.fileno())
 def call(model,r,method,d=None,val=None):
  nonlocal calls
  calls+=1;log({"event":"START","call":calls,"case":r["case_id"],"method":method});t=time.monotonic()
  try:
   x=prior.solve(model,plan["lambda_library"],d,val)
   res=evaluate_candidate(x,r,model,np.array(r["down_row_ecef"]),0. if val is None else val)
  except (prior.raw.RawBackendError,ValueError,np.linalg.LinAlgError) as ex:res={"candidate_available":False,"integer_correct":False,"failure":type(ex).__name__+":"+str(ex)}
  res["elapsed_s"]=time.monotonic()-t;log({"event":"END","call":calls,"case":r["case_id"],"method":method,"candidate":res["candidate_available"],"correct":res["integer_correct"]})
  return res
 for r in plan["models"]:
  model=model_from(r);aa=call(model,r,"A")
  emit(out/(r["case_id"]+"_A.json"),aa)
  for f in plan["faults"]:
   bb=call(model,r,f["name"],np.array(r["down_row_ecef"]),f["vertical_prior_m"])
   keep=bool(aa["candidate_available"] and bb["candidate_available"] and aa["ambiguity"]==bb["ambiguity"])
   rec={"case_id":r["case_id"],"fault":f,"integer_truth":r["integer_truth"],"A_cached":aa,"A_cached_prior_residual_reference_m":0.0,"B":bb,"C_retained":keep,"C_correct_retained":bool(keep and bb["integer_correct"]),"C_wrong_retained":bool(keep and not bb["integer_correct"])}
   emit(out/(r["case_id"]+"_"+f["name"]+".json"),rec);rows.append(rec)
   print(r["case_id"],f["name"],"A",aa["integer_correct"],"B",bb["integer_correct"],"C",keep,flush=True)
 assert calls==16 and len(rows)==12;pincheck(plan,a.code)
 unique=[json.loads((out/(r["case_id"]+"_A.json")).read_text()) for r in plan["models"]]
 def counts(rs):
  return {"total":len(rs),"available":sum(x["candidate_available"] for x in rs),"correct_candidates":sum(x["candidate_available"] and x["integer_correct"] for x in rs),"wrong_candidates":sum(x["candidate_available"] and not x["integer_correct"] for x in rs),"unresolved":sum(not x["candidate_available"] for x in rs)}
 summaries={}
 for f in plan["faults"]:
  group=[r for r in rows if r["fault"]["name"]==f["name"]]
  summaries[f["name"]]={"B":counts([r["B"] for r in group]),"C_correct_retained":sum(r["C_correct_retained"] for r in group),"C_wrong_retained":sum(r["C_wrong_retained"] for r in group),"C_rejected":sum(not r["C_retained"] for r in group)}
 emit(a.stage/"SYNTHETIC2_SEAL.json",{"execution_commit":a.execution_commit,"plan_sha256":sha(a.stage/"SYNTHETIC2_PLAN.json"),"calls":calls,"A_unique":counts(unique),"by_prior_condition":summaries,"records":rows,"ledger_sha256":sha(ledger),"result_hashes":{p.name:sha(p) for p in out.glob("*.json")},"risk_rate_estimate":"NOT_ESTIMATED_4_SHARED_NOISE_INSTANCES"})
 print(json.dumps(summaries),flush=True)
def supervise(a):
 plan=json.loads((a.stage/"SYNTHETIC2_PLAN.json").read_text());pincheck(plan,a.code)
 trace=a.stage/"IO.strace";assert not trace.exists()
 command=["strace","-f","-qq","-xx","-s","8192","-e","trace=open,openat,execve","-o",str(trace),sys.executable,str(Path(__file__).resolve()),"run","--code",str(a.code),"--stage",str(a.stage),"--execution-commit",a.execution_commit]
 t=time.monotonic();child=subprocess.Popen(command,start_new_session=True)
 try:rc=child.wait(timeout=1200)
 except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();rc=124
 paths=prior.open_paths(trace)
 forbidden=[p for p,ro in paths if "/data/raw/" in p or Path(p).name.startswith("trace_vrtk")]
 passed=rc==0 and not forbidden
 emit(a.stage/"IO_AUDIT.json",{"passed":passed,"exit_code":rc,"elapsed_s":time.monotonic()-t,"forbidden_raw_or_reference_opens":forbidden,"strace_sha256":sha(trace)})
 assert passed
def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","run","supervise"])
 p.add_argument("--code",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--stage1",type=Path);p.add_argument("--execution-commit");a=p.parse_args()
 assert os.uname().sysname=="Linux";a.stage.mkdir(parents=True,exist_ok=True);globals()[a.phase](a)
if __name__=="__main__":main()
