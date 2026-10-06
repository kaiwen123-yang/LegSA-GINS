#!/usr/bin/env python3
"""Aggregate sealed synthetic2 records; no solver and no original raw/reference."""
import argparse,csv,hashlib,json,math
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 seal=json.loads((a.stage/"SYNTHETIC2_SEAL.json").read_text());plan=json.loads((a.stage/"SYNTHETIC2_PLAN.json").read_text());io=json.loads((a.stage/"IO_AUDIT.json").read_text())
 assert io["passed"] and seal["plan_sha256"]==sha(a.stage/"SYNTHETIC2_PLAN.json") and seal["ledger_sha256"]==sha(a.stage/"CALL_LEDGER.jsonl")
 for name,h in seal["result_hashes"].items():assert sha(a.stage/"RESULTS"/name)==h
 ledger=[json.loads(s) for s in (a.stage/"CALL_LEDGER.jsonl").read_text().splitlines()]
 assert sum(r["event"]=="START" for r in ledger)==sum(r["event"]=="END" for r in ledger)==16
 rows=[]
 for r in seal["records"]:
  q={"case_id":r["case_id"],"rp_case":r["fault"]["name"],"reported_roll_rad":r["fault"]["roll_rad"],"reported_pitch_rad":r["fault"]["pitch_rad"],"bD_prior_m":r["fault"]["vertical_prior_m"],"integer_truth":json.dumps(r["integer_truth"],separators=(",",":")),"C_retained":r["C_retained"],"C_correct_retained":r["C_correct_retained"],"C_wrong_retained":r["C_wrong_retained"],"A_cached_prior_residual_reference_m":0.}
  for label,x in (("A",r["A_cached"]),("B",r["B"])):
   for k in ("candidate_available","integer_correct","projected_heading_error_deg","baseline_angle_error_deg","raw_whitened_residual_squared","prior_residual_sigma","constrained_objective_ratio_diagnostic","elapsed_s"):q[label+"_"+k]=x.get(k)
   q[label+"_ambiguity"]=json.dumps(x.get("ambiguity"),separators=(",",":"))
  rows.append(q)
 assert len(rows)==12
 with (a.out/"SYNTHETIC2_EPOCH_METRICS.csv").open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 def angle_stats(selected,label):
  values=[r[label+"_projected_heading_error_deg"] for r in selected if r[label+"_projected_heading_error_deg"] is not None]
  return {"available":len(values),"rmse_deg":math.sqrt(sum(v*v for v in values)/len(values)) if values else None,"max_absolute_deg":max(map(abs,values)) if values else None}
 summary={"execution_commit":seal["execution_commit"],"payload_stage":"<AR_SCRATCH>/SYNTHETIC2_PREP02","plan_sha256":seal["plan_sha256"],"calls":seal["calls"],"A_unique":seal["A_unique"],"by_prior_condition":seal["by_prior_condition"],"four_shared_noise_instances":True,"risk_rate_estimation":False,"formal_integer_acceptance_defined":False,"angles_by_condition":{f["name"]:{m:angle_stats([r for r in rows if r["rp_case"]==f["name"]],m) for m in ("A","B")} for f in plan["faults"]},"io":io,"pins":{n:sha(a.stage/n) for n in ("SYNTHETIC2_PLAN.json","SYNTHETIC2_SEAL.json","IO_AUDIT.json","CALL_LEDGER.jsonl")},"summary_script_sha256":sha(Path(__file__)),"csv_sha256":sha(a.out/"SYNTHETIC2_EPOCH_METRICS.csv")}
 with (a.out/"SYNTHETIC2_RESULT_SUMMARY.json").open("x") as f:json.dump(summary,f,indent=2,allow_nan=False)
 print(json.dumps(summary["angles_by_condition"],indent=2))
if __name__=="__main__":main()
