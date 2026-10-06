#!/usr/bin/env python3
"""Derive compact AR receipts from sealed payload only; never read a reference."""
import argparse,csv,hashlib,json,platform
from pathlib import Path
import numpy as np
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,indent=2,ensure_ascii=False,allow_nan=False)
def main():
 p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 seal=json.loads((a.stage/"REAL_SEAL.json").read_text());ev=json.loads((a.stage/"EVALUATION_SEAL.json").read_text())
 assert ev["real_seal_sha256"]==sha(a.stage/"REAL_SEAL.json") and ev["csv_sha256"]==sha(a.stage/"REAL_EVALUATION.csv")
 for name,h in seal["record_hashes"].items():assert sha(a.stage/"REAL"/name)==h
 with (a.stage/"REAL_EVALUATION.csv").open(newline="") as f:erows=list(csv.DictReader(f))
 assert len(erows)==36 and len({(r["epoch_index"],r["method"]) for r in erows})==36
 errors={(int(r["epoch_index"]),r["method"]):float(r["signed_yaw_error_deg"]) for r in erows if r["signed_yaw_error_deg"]}
 for m in ("A","B","C"):assert [r["time_unix_s"] for r in erows if r["method"]==m]==[r["time_unix_s"] for r in erows if r["method"]=="A"]
 kept={r["epoch_index"] for r in seal["epochs"] if r["C_retained"]};changed={i for i,m in errors if m=="A"}-kept
 def stats(indices,m):
  values=[errors[(i,m)] for i in sorted(indices) if (i,m) in errors]
  return {"count":len(values),"rmse_deg":float(np.sqrt(np.mean(np.square(values)))) if values else None,"mae_deg":float(np.mean(np.abs(values))) if values else None,"max_absolute_deg":max(map(abs,values)) if values else None}
 rows=[]
 for r in seal["epochs"]:
  row={"target_s":r["target_s"],"time_s":r["time_s"],"time_unix_s":r["time_unix_s"],"epoch_index":r["epoch_index"],"C_retained":r["C_retained"],"failure":r["failure"],"rp_age_s":r["rp_age_s"],"prior_down_m":r["vertical_prior_m"]}
  for m in ("A","B"):
   x=r[m] or {};row[m+"_candidate"]=x.get("candidate_available",False)
   for field in ("body_yaw_deg","raw_whitened_residual_squared","prior_residual_sigma","constrained_objective_ratio_diagnostic","elapsed_s"):
    row[m+"_"+field]=x.get(field)
   row[m+"_signed_yaw_error_deg"]=errors.get((r["epoch_index"],m))
   row[m+"_ambiguity"]=json.dumps(x.get("ambiguity"),separators=(",",":")) if x.get("candidate_available") else None
   for j,k in enumerate(("north_m","east_m","down_m")):row[m+"_"+k]=(x.get("baseline_ned_m") or [None]*3)[j]
  if r["A"] and r["B"] and r["A"]["candidate_available"] and r["B"]["candidate_available"]:
   ba=np.array(r["A"]["baseline_ned_m"]);bb=np.array(r["B"]["baseline_ned_m"])
   row["AB_baseline_delta_m"]=float(np.linalg.norm(bb-ba))
   row["AB_yaw_change_deg"]=float((r["B"]["body_yaw_deg"]-r["A"]["body_yaw_deg"]+180)%360-180)
  else:row["AB_baseline_delta_m"]=row["AB_yaw_change_deg"]=None
  rows.append(row)
 a.out.mkdir(parents=True,exist_ok=True)
 with (a.out/"REAL_EPOCH_METRICS.csv").open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 with (a.out/"REAL_EVALUATION.csv").open("xb") as f:f.write((a.stage/"REAL_EVALUATION.csv").read_bytes())
 io={k:json.loads((a.stage/(k+"_IO_AUDIT.json")).read_text()) for k in ("REAL","EVALUATE")}
 assert io["REAL"]["passed"] and io["EVALUATE"]["passed"]
 ledger=[json.loads(s) for s in (a.stage/"CALL_LEDGER.jsonl").read_text().splitlines()]
 assert sum(r["stage"]=="SPP_START" for r in ledger)==12 and sum(r["stage"]=="CILS_START" for r in ledger)==sum(r["stage"]=="CILS_END" for r in ledger)==18
 summary={"execution_commit":seal["execution_commit"],"payload_stage":"<AR_SCRATCH>/PREP04","plan_sha256":seal["plan_sha256"],"phase":"COMPLETED_BOUNDED_QUALIFICATION_NOT_ACCEPTED_INTEGER_FIX","counts":{"scheduled_epochs":12,"cold_code_spp_calls":12,"cils_calls":18,"A_candidates":9,"B_candidates":9,"C_retained":5,"model_failure_epochs":3,"real_retry":0,"offline_reference_read_opens":1,"online_reference_read_opens":0},"summary":ev["summary"],"C_retained_same_five_support":{m:stats(kept,m) for m in ("A","B","C")},"C_rejected_changed_same_four_support":{m:stats(changed,m) for m in ("A","B")},"C_retained_indices":sorted(kept),"C_rejected_changed_indices":sorted(changed),"io":io,"all_method_scheduled_timekeys_exact_equal":True,"real_integer_correctness":"NA","body_yaw_field_semantics":"lateral projected heading; compared approximately with commercial Euler yaw","source_receipts":{n:sha(a.stage/n) for n in ("PLAN.json","REAL_SEAL.json","REAL_IO_AUDIT.json","REAL_EVALUATION.csv","EVALUATION_SEAL.json","EVALUATE_IO_AUDIT.json","CALL_LEDGER.jsonl")},"summary_script_sha256":sha(Path(__file__)),"environment":{"python":platform.python_version(),"numpy":np.__version__,"system":platform.platform()}}
 dump(a.out/"AR_RESULT_SUMMARY.json",summary)
 print(json.dumps({"same_five":summary["C_retained_same_five_support"],"changed_four":summary["C_rejected_changed_same_four_support"]},indent=2))
if __name__=="__main__":main()
