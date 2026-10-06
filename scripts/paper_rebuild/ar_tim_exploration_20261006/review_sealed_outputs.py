#!/usr/bin/env python3
"""Read sealed AR outputs only; no project backend imports, raw, reference or solve."""
from pathlib import Path
import argparse,collections,csv,hashlib,json,math,re
import numpy as np
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def j(p):return json.loads(Path(p).read_text())
def wrap(x):return (x+180.)%360.-180.
def rotation(anchor):
 x,y,z=np.asarray(anchor);lon=math.atan2(y,x);rho=math.hypot(x,y)
 a=6378137.;e2=6.6943799901413165e-3;lat=math.atan2(z,rho*(1-e2))
 for _ in range(12):
  nn=a/math.sqrt(1-e2*math.sin(lat)**2)
  lat=math.atan2(z+e2*nn*math.sin(lat),rho)
 sl,cl=math.sin(lat),math.cos(lat);so,co=math.sin(lon),math.cos(lon)
 return np.array([[-sl*co,-sl*so,cl],[-so,co,0.],[-cl*co,-cl*so,-sl]])
def stats(a):
 a=np.array(a)
 return dict(count=len(a),rmse_deg=float(np.sqrt(np.mean(a*a))) if len(a) else None,mae_deg=float(np.mean(abs(a))) if len(a) else None,max_absolute_deg=float(np.max(abs(a))) if len(a) else None)
def main(a):
 s=a.stage;p=j(s/"PLAN.json");seal=j(s/"REAL_SEAL.json");ev=j(s/"EVALUATION_SEAL.json")
 assert sha(s/"PLAN.json")==seal["plan_sha256"]
 assert sha(s/"REAL_SEAL.json")==ev["real_seal_sha256"]
 assert sha(s/"CALL_LEDGER.jsonl")==seal["call_ledger_sha256"]
 assert sha(s/"REAL_EVALUATION.csv")==ev["csv_sha256"]
 for name,h in seal["record_hashes"].items():assert sha(s/"REAL"/name)==h,name
 for src,h in p["source_pins"].items():assert sha(a.code/src)==h,src
 audits={}
 for phase,n in [("REAL",0),("EVALUATE",1)]:
  audit=j(s/(phase+"_IO_AUDIT.json"));trace=s/(phase+"_IO.strace")
  assert audit["passed"] and audit["reference_successful_read_opens"]==n and audit["all_raw_inputs_readonly"]
  assert sha(trace)==audit["strace_sha256"]
  found=0
  for line in trace.read_text().splitlines():
   if "openat(" not in line and "open(" not in line:continue
   if not re.search(r"=\s+[0-9]+\s*$",line):continue
   tokens=re.findall(r'"((?:\\x[0-9a-fA-F]{2})+)"',line)
   for tok in tokens:
    path=bytes.fromhex(tok.replace("\\x","")).decode("utf-8","replace")
    if Path(path).name==Path(p["reference"]).name:found+=1;assert "O_RDONLY" in line and "O_RDWR" not in line
  assert found==n
  audits[phase]={"reference_open_count_reparsed":found,"receipt_and_trace_hash_passed":True}
 recs=seal["epochs"];assert len(recs)==12 and len(seal["record_hashes"])==12
 for r,pr in zip(recs,p["rows"]):
  assert all(r[k]==v for k,v in pr.items())
  assert j(s/"REAL"/("EPOCH_%03d.json"%r["epoch_index"]))==r
 ledger=[json.loads(line) for line in (s/"CALL_LEDGER.jsonl").read_text().splitlines()]
 counts=collections.Counter(x["stage"] for x in ledger)
 assert counts=={"SPP_START":12,"CILS_START":18,"CILS_END":18,"EPOCH_END":12}
 assert seal["spp_calls"]==12 and seal["cils_calls"]==18
 for kind in ["SPP_START","EPOCH_END"]:assert sorted(x["epoch_index"] for x in ledger if x["stage"]==kind)==[r["epoch_index"] for r in recs]
 starts=collections.Counter((x["epoch_index"],x["method"]) for x in ledger if x["stage"]=="CILS_START")
 ends=collections.Counter((x["epoch_index"],x["method"]) for x in ledger if x["stage"]=="CILS_END")
 assert starts==ends and all(v==1 for v in starts.values())
 errors=collections.defaultdict(list);details=[];counts_available=collections.Counter();null_frontier=[]
 for r in recs:
  A,B=r["A"],r["B"]
  agree=bool(A and B and A["candidate_available"] and B["candidate_available"] and A["ambiguity"]==B["ambiguity"])
  assert r["C_retained"]==agree
  if r["failure"] is not None:
   assert r["target_s"] in (220,260,280) and "INSUFFICIENT_HALF_CYCLE_VALID" in r["failure"]
   assert A is None and B is None
   continue
  q=np.asarray(r["model"]["covariance_m2"]);y=np.asarray(r["model"]["observation_m"]);H=np.asarray(r["model"]["baseline_design"]);D=np.asarray(r["model"]["ambiguity_design_m"])
  rot=rotation(r["spp"]["position_ecef_m"])
  assert np.linalg.eigvalsh(q).min()>0
  for name,c in [("A",A),("B",B)]:
   assert c["candidate_available"];counts_available[name]+=1
   b=np.array(c["baseline_ecef_m"]);n=np.array(c["ambiguity"]);ned=rot@b
   assert np.all(n==np.rint(n))
   residual=y-H@b-D@n;whitened=np.linalg.solve(np.linalg.cholesky(q),residual);cost=float(whitened@whitened)
   prior=(float(ned[2])-r["vertical_prior_m"])/.03
   solver=c["solver"]
   errors["baseline_length_m"].append(abs(np.linalg.norm(b)-.35))
   errors["ECEF_to_NED_m"].append(float(np.max(abs(ned-np.asarray(c["baseline_ned_m"])))))
   errors["raw_whitened_cost"].append(abs(cost-c["raw_whitened_residual_squared"]))
   errors["prior_standardized_residual"].append(abs(prior-c["prior_residual_sigma"]))
   angle=wrap(math.degrees(math.atan2(ned[1],ned[0]))+90)
   errors["projected_heading_deg"].append(abs(wrap(angle-c["body_yaw_deg"])))
   objective=cost+(prior*prior if name=="B" else 0)
   identity=solver["best"]["objective"]+solver["float_solution"]["residual_objective"]
   errors["objective_identity"].append(abs(objective-identity))
   assert solver["global_optimum_certified"] and solver["termination_reason"]=="GLOBAL_BOUND_CERTIFIED"
   assert not solver["runtime_budget_exhausted"] and not solver["node_limit_exhausted"] and not solver["candidate_cap_applied"]
   bound=solver["frontier_lower_bound_at_termination"]
   if bound is None:
    # Backend exhaustive frontier uses +inf; frozen jsonable serializes nonfinite as null.
    # Do not claim independently proven numerical lower bound for a null value.
    null_frontier.append({"target_s":r["target_s"],"method":name,"serialized_bound":None,"certificate_label":solver["termination_reason"]})
   else:assert bound+1e-8>=solver["second_total_objective"]
   assert solver["ambiguity_acceptance_test_defined"] is False and solver["ambiguity_accepted"] is None
   details.append({"target_s":r["target_s"],"method":name,"C_retained":agree,"horizontal_projection_m":math.hypot(ned[0],ned[1]),"baseline_down_m":float(ned[2]),"raw_cost":cost,"prior_residual_sigma":prior})
 assert counts_available=={"A":9,"B":9}
 maxima={k:max(v) for k,v in errors.items()}
 assert maxima["baseline_length_m"]<1e-10 and maxima["ECEF_to_NED_m"]<1e-9
 assert maxima["raw_whitened_cost"]<1e-6 and maxima["prior_standardized_residual"]<1e-7
 assert maxima["projected_heading_deg"]<1e-7 and maxima["objective_identity"]<1e-4
 rows=list(csv.DictReader((s/"REAL_EVALUATION.csv").open()));assert len(rows)==36
 lookup={(r["method"],int(r["epoch_index"])):r for r in rows};assert len(lookup)==36
 metric_diff=[];reported_error_diff=[]
 for r in recs:
  for name in ("A","B","C"):
   c=(r["B"] if r["C_retained"] else None) if name=="C" else r[name]
   item=lookup[name,r["epoch_index"]];available=bool(c and c["candidate_available"])
   assert (item["candidate_available"]=="True")==available
   assert float(item["time_unix_s"])==r["time_unix_s"] and float(item["time_s"])==r["time_s"]
   if available:
    assert float(item["body_yaw_deg"])==c["body_yaw_deg"]
    e=wrap(float(item["body_yaw_deg"])-float(item["reference_yaw_ned_deg"]))
    reported_error_diff.append(abs(e-float(item["signed_yaw_error_deg"])))
   else:assert item["signed_yaw_error_deg"]==""
 summaries={}
 for name in ("A","B","C"):
  own=[float(r["signed_yaw_error_deg"]) for r in rows if r["method"]==name and r["signed_yaw_error_deg"]]
  summaries[name]=stats(own)
  for key,v in summaries[name].items():metric_diff.append(abs(v-ev["summary"][name]["own_support"][key]))
  common=[float(r["signed_yaw_error_deg"]) for r in rows if r["method"]==name and int(r["epoch_index"]) in ev["common_AB_epoch_indices"] and r["signed_yaw_error_deg"]]
  for key,v in stats(common).items():metric_diff.append(abs(v-ev["summary"][name]["common_AB_support"][key]))
 assert max(metric_diff+reported_error_diff)<1e-10
 omitted=[r for r in recs if r["A"] and r["B"] and not r["C_retained"]]
 rejected_B_errors=[float(lookup["B",r["epoch_index"]]["signed_yaw_error_deg"]) for r in omitted]
 result={"status":"PASS_SEALED_OUTPUT_CONSISTENCY_NOT_INTEGER_TRUTH","execution_commit":seal["execution_commit"],"plan_sha256":sha(s/"PLAN.json"),"review_script_sha256":sha(__file__),"input_pins":{p.name:sha(p) for p in [s/"PLAN.json",s/"REAL_SEAL.json",s/"EVALUATION_SEAL.json",s/"REAL_IO_AUDIT.json",s/"EVALUATE_IO_AUDIT.json",s/"REAL_EVALUATION.csv",s/"CALL_LEDGER.jsonl"]},"source_pins_verified":len(p["source_pins"]),"sealed_epoch_record_pins_verified":12,"scheduled":12,"raw_reference_solver_evaluator_reads_or_calls":[0,0,0,0],"reparsed_io":audits,"ledger_counts":dict(counts),"candidate_counts":{"A":9,"B":9,"C":5},"max_numerical_discrepancies":maxima,"max_statistic_difference":max(metric_diff),"max_saved_error_arithmetic_difference":max(reported_error_diff),"independent_statistics":summaries,"C_rejected_integer_change_targets_s":[r["target_s"] for r in omitted],"B_statistics_on_C_rejected_four":stats(rejected_B_errors),"integer_correctness":"NA","candidate_details":details,"null_frontier_certificate_records":null_frontier,"review_execution_note":"One initial read-only check stopped on null frontier (serialized +infinity). Checker now records the null without inventing a numeric bound; second read-only check completes. No solver/evaluator or simulation rerun."}
 with a.out.open("x",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
 print(json.dumps({k:v for k,v in result.items() if k not in ("candidate_details","input_pins")},ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--code",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);main(p.parse_args())
