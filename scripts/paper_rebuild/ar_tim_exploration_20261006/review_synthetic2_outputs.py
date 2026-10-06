#!/usr/bin/env python3
"""Independent arithmetic audit of sealed synthetic2 outputs. No solver/backend."""
from pathlib import Path
import argparse,collections,hashlib,json,math,re
import numpy as np
from review_sealed_outputs import rotation
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def wrap(x):return (x+180)%360-180
def main(a):
 s=a.stage;plan=read(s/"SYNTHETIC2_PLAN.json");seal=read(s/"SYNTHETIC2_SEAL.json");audit=read(s/"IO_AUDIT.json")
 assert seal["plan_sha256"]==sha(s/"SYNTHETIC2_PLAN.json")
 assert seal["ledger_sha256"]==sha(s/"CALL_LEDGER.jsonl")
 assert audit["passed"] and audit["strace_sha256"]==sha(s/"IO.strace")
 for n,h in plan["source_pins"].items():assert sha(a.code/n)==h,n
 for n,h in plan["input_pins"].items():assert sha(n)==h,n
 for n,h in seal["result_hashes"].items():assert sha(s/"RESULTS"/n)==h,n
 forbidden=[]
 for line in (s/"IO.strace").read_text().splitlines():
  if not ("openat(" in line or "open(" in line) or not re.search(r"=\s+[0-9]+\s*$",line):continue
  for token in re.findall(r'"((?:\\x[0-9a-fA-F]{2})+)"',line):
   name=bytes.fromhex(token.replace("\\x","")).decode("utf-8","replace")
   if "/data/raw/" in name or Path(name).name.startswith("trace_vrtk"):forbidden.append(name)
 assert not forbidden
 ledger=[json.loads(x) for x in (s/"CALL_LEDGER.jsonl").read_text().splitlines()]
 counts=collections.Counter(x["event"] for x in ledger);assert counts=={"START":16,"END":16}
 starts=collections.Counter((x["call"],x["case"],x["method"]) for x in ledger if x["event"]=="START")
 ends=collections.Counter((x["call"],x["case"],x["method"]) for x in ledger if x["event"]=="END")
 assert starts==ends and all(n==1 for n in starts.values()) and seal["calls"]==16
 assert sum(x["event"]=="START" and x["method"]=="A" for x in ledger)==4
 models={m["case_id"]:m for m in plan["models"]};faults={f["name"]:f for f in plan["faults"]}
 maxima=collections.defaultdict(float);checked=set()
 def delta(key,x):maxima[key]=max(maxima[key],float(abs(x)))
 def verify(c,m,value,key):
  if key in checked:return
  checked.add(key);assert c["candidate_available"] and c["solver"]["global_optimum_certified"]
  n=np.array(c["ambiguity"]);b=np.array(c["baseline_ecef_m"]);nt=np.array(m["integer_truth"]);bt=np.array(m["true_baseline_ecef_m"])
  assert c["integer_correct"]==bool(np.array_equal(n,nt))
  H=np.array(m["baseline_design"]);A=np.array(m["ambiguity_design_m"]);Q=np.array(m["covariance_m2"]);y=np.array(m["observation_m"])
  rot=rotation(m["anchor_ecef_m"]);ned=rot@b
  err=y-H@b-A@n;w=np.linalg.solve(np.linalg.cholesky(Q),err);cost=float(w@w);prior=(ned[2]-value)/.03
  delta("length_m",np.linalg.norm(b)-.35);delta("NED_m",np.max(abs(ned-c["baseline_ned_m"])))
  delta("raw_cost",cost-c["raw_whitened_residual_squared"]);delta("prior_residual_sigma",prior-c["prior_residual_sigma"])
  if key[1]=="A":obj=cost
  else:obj=cost+prior*prior
  delta("objective_identity",obj-c["solver"]["best"]["objective"]-c["solver"]["float_solution"]["residual_objective"])
  angle=wrap(math.degrees(math.atan2(ned[1],ned[0]))-m["baseline_bearing_ned_deg"])
  delta("projected_angle_deg",wrap(angle-c["projected_heading_error_deg"]))
  angle3=math.degrees(math.acos(float(np.clip(b@bt/.35**2,-1,1))))
  delta("three_dim_angle_deg",angle3-c["baseline_angle_error_deg"])
 truthconstruction=0.
 for m in models.values():
  H=np.array(m["baseline_design"]);A=np.array(m["ambiguity_design_m"]);Q=np.array(m["covariance_m2"])
  y=np.array(m["observation_m"]);b=np.array(m["true_baseline_ecef_m"]);n=np.array(m["integer_truth"]);noise=np.array(m["gaussian_noise_m"])
  truthconstruction=max(truthconstruction,float(np.max(abs(y-H@b-A@n-noise))),float(np.max(abs(np.linalg.cholesky(Q)@m["gaussian_standard_draw"]-noise))))
 Aresults={name:read(s/"RESULTS"/(name+"_A.json")) for name in models}
 for name,c in Aresults.items():verify(c,models[name],0.,(name,"A"))
 groups={name:dict(B_correct=0,B_wrong=0,C_correct_retained=0,C_wrong_retained=0,C_rejected=0,rejected_correct_B=0,rejected_wrong_B=0) for name in faults}
 for r in seal["records"]:
  name=r["case_id"];fault=r["fault"];m=models[name];assert fault==faults[fault["name"]]
  assert read(s/"RESULTS"/(name+"_"+fault["name"]+".json"))==r
  assert r["A_cached"]==Aresults[name]
  value=-.35*math.sin(fault["roll_rad"])*math.cos(fault["pitch_rad"])
  assert abs(value-fault["vertical_prior_m"])<1e-14
  verify(r["B"],m,value,(name,fault["name"]))
  keep=r["A_cached"]["ambiguity"]==r["B"]["ambiguity"]
  correct=r["B"]["integer_correct"];assert r["C_retained"]==keep and r["C_correct_retained"]==(keep and correct) and r["C_wrong_retained"]==(keep and not correct)
  g=groups[fault["name"]];g["B_correct" if correct else "B_wrong"]+=1
  if keep:g["C_correct_retained" if correct else "C_wrong_retained"]+=1
  else:g["C_rejected"]+=1;g["rejected_correct_B" if correct else "rejected_wrong_B"]+=1
 assert len(checked)==16 and len(seal["records"])==12 and len(seal["result_hashes"])==16
 assert maxima["objective_identity"]<1e-5 and maxima["length_m"]<1e-10 and maxima["NED_m"]<1e-9
 assert maxima["raw_cost"]<1e-6 and maxima["prior_residual_sigma"]<1e-7 and maxima["projected_angle_deg"]<1e-7 and maxima["three_dim_angle_deg"]<1e-7 and truthconstruction<1e-12
 for name,g in groups.items():
  ref=seal["by_prior_condition"][name];assert g["B_correct"]==ref["B"]["correct_candidates"] and g["B_wrong"]==ref["B"]["wrong_candidates"]
  for k in ["C_correct_retained","C_wrong_retained","C_rejected"]:assert g[k]==ref[k]
 result={"status":"PASS_SEALED_SYNTHETIC_MECHANISM_ARITHMETIC_NOT_RISK_VALIDATION","execution_commit":seal["execution_commit"],"source_pins_verified":len(plan["source_pins"]),"input_pins_verified":len(plan["input_pins"]),"result_pins_verified":16,"unique_noise_instances":4,"A_unique_calls":4,"B_condition_calls":12,"C_calls":0,"total_solver_calls":16,"reviewer_solver_reference_raw_calls_or_reads":[0,0,0],"IO_raw_reference_payload_opens_reparsed":0,"max_arithmetic_discrepancies":dict(maxima),"max_synthetic_y_construction_discrepancy":truthconstruction,"A_unique_correct":sum(x["integer_correct"] for x in Aresults.values()),"A_unique_wrong":sum(not x["integer_correct"] for x in Aresults.values()),"by_prior_condition":groups,"risk_estimate":"NA: only four shared-noise instances; designed after stage1 real results","pins":{p.name:sha(p) for p in [s/"SYNTHETIC2_PLAN.json",s/"SYNTHETIC2_SEAL.json",s/"CALL_LEDGER.jsonl",s/"IO_AUDIT.json"]},"review_script_sha256":sha(__file__),"rotation_helper_sha256":sha(Path(__file__).with_name("review_sealed_outputs.py"))}
 with a.out.open("x",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--code",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);main(p.parse_args())
