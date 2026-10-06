#!/usr/bin/env python3
"""Read-only aggregate of sealed D validation; no solver or reference access."""
from pathlib import Path
import argparse,csv,hashlib,json,math
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stats(values):
 return {"count":len(values),"rmse_deg":math.sqrt(sum(v*v for v in values)/len(values)) if values else None,"max_absolute_deg":max(map(abs,values)) if values else None}
def main():
 p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 seal=json.loads((a.stage/"SEAL.json").read_text());plan=json.loads((a.stage/"PLAN.json").read_text());io=json.loads((a.stage/"IO_AUDIT.json").read_text())
 assert io["passed"] and seal["plan_sha256"]==sha(a.stage/"PLAN.json") and seal["ledger_sha256"]==sha(a.stage/"CALL_LEDGER.jsonl")
 for name,h in seal["result_hashes"].items():assert sha(a.stage/"RESULTS"/name)==h
 ledger=[json.loads(x) for x in (a.stage/"CALL_LEDGER.jsonl").read_text().splitlines()]
 assert sum(x["event"]=="START" for x in ledger)==sum(x["event"]=="END" for x in ledger)==seal["calls"]==20
 rows=[];summaries={}
 for r in seal["records"]:
  row={"case_id":r["case_id"],"source_group":r["source_group"],"condition":r["condition"]["name"],"measurement_fault":r["measurement_fault"],"reported_roll_rad":r["condition"]["reported_roll_rad"],"reported_pitch_rad":r["condition"]["reported_pitch_rad"],"vertical_prior_m":r["condition"]["vertical_prior_m"],"integer_truth":json.dumps(r["integer_truth"],separators=(",",":"))}
  for m in ("A","B"):
   for k in ("candidate_available","integer_correct","projected_heading_error_deg","baseline_angle_error_deg","raw_whitened_residual_squared","prior_residual_sigma","elapsed_s"):row[m+"_"+k]=r[m].get(k)
   row[m+"_ambiguity"]=json.dumps(r[m].get("ambiguity"),separators=(",",":"))
  for k in ("C_retained","C_correct_retained","C_wrong_retained"):row[k]=r[k]
  for k in ("available","selected_branch","integer_correct","projected_heading_error_deg","baseline_angle_error_deg","fault_branch_score","healthy_branch_score","healthy_minus_fault_score","full_bounded_objective","raw_cost_increase_B_vs_A","selected_raw_cost_increase_vs_A","selected_prior_residual_sigma"):row["D_"+k]=r["D"].get(k)
  row["D_ambiguity"]=json.dumps(r["D"].get("ambiguity"),separators=(",",":"));rows.append(row)
 for cond in ("NOMINAL","RP_BIAS","PHASE_BIAS"):
  group=[r for r in seal["records"] if r["condition"]["name"]==cond];assert len(group)==4
  out={}
  for m in ("A","B","C","D"):
   def get(r):
    if m=="C":return r["C_retained"],r["B"]
    if m=="D":return r["D"]["available"],r["D"]
    return r[m]["candidate_available"],r[m]
   items=[get(r) for r in group];valid=[x for ok,x in items if ok]
   out[m]={"scheduled":4,"available":len(valid),"correct":sum(x["integer_correct"] for x in valid),"wrong":sum(not x["integer_correct"] for x in valid),"unresolved":4-len(valid),"own_angle_support":stats([x["projected_heading_error_deg"] for x in valid if x.get("projected_heading_error_deg") is not None])}
  useful=[r for r in group if r["A"]["candidate_available"] and r["B"]["candidate_available"] and not r["A"]["integer_correct"] and r["B"]["integer_correct"]]
  def ids(test):return [r["case_id"] for r in group if test(r)]
  out["mechanisms"]={"available_B_corrections_to_wrong_A":[r["case_id"] for r in useful],"D_kept_B_corrections":[r["case_id"] for r in useful if r["D"].get("selected_branch")=="B" and r["D"].get("integer_correct")],"D_missed_B_corrections":[r["case_id"] for r in useful if not(r["D"].get("selected_branch")=="B" and r["D"].get("integer_correct"))],"D_fallback_A":ids(lambda r:r["D"].get("selected_branch")=="A"),"D_fallback_A_still_wrong":ids(lambda r:r["D"].get("selected_branch")=="A" and not r["D"].get("integer_correct")),"D_selected_B_wrong":ids(lambda r:r["D"].get("selected_branch")=="B" and not r["D"].get("integer_correct")),"D_wrong_after_correct_A":ids(lambda r:r["A"]["candidate_available"] and r["A"]["integer_correct"] and r["D"]["available"] and not r["D"]["integer_correct"]),"C_wrong_retained":ids(lambda r:r["C_wrong_retained"])}
  summaries[cond]=out
 a.out.mkdir(parents=True,exist_ok=True)
 with (a.out/"D_EPOCH_METRICS.csv").open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 report={"execution_commit":seal["execution_commit"],"payload_stage":"<TIM_AR_SCRATCH>/D_PREP02","plan_sha256":seal["plan_sha256"],"calls":seal["calls"],"new_noise_draws":4,"unique_observation_instances":8,"logical_rows":12,"summaries":summaries,"io":io,"source_receipts":{n:sha(a.stage/n) for n in ("PLAN.json","SEAL.json","IO_AUDIT.json","CALL_LEDGER.jsonl")},"csv_sha256":sha(a.out/"D_EPOCH_METRICS.csv"),"summary_script_sha256":sha(Path(__file__)),"original_raw_reference_reads":0,"formal_integer_acceptance_defined":False,"EKF_integration_qualified":False,"parameter_retuned":False}
 with (a.out/"D_RESULT_SUMMARY.json").open("x") as f:json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False)
 print(json.dumps(summaries,indent=2))
if __name__=="__main__":main()
