#!/usr/bin/env python3
"""Compact engineering results; no raw/reference access or algorithm calls."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,json
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def main():
 p=argparse.ArgumentParser();p.add_argument("--trial",action="append",type=Path,required=True)
 p.add_argument("--docs",type=Path,required=True);a=p.parse_args();a.docs.mkdir(parents=True,exist_ok=True)
 summary={"trials":[],"real_integer_truth_available":False,"reference_reads":0,
          "navigation_integration":False,"cross_family_objective_comparison_valid":False}
 table=[];future=[];receipts={}
 for trial in a.trial:
  plan=json.loads((trial/"PLAN.json").read_text());receipts[trial.name+"/PLAN.json"]=digest(trial/"PLAN.json")
  events=json.loads((trial/"ARC_EVENTS.json").read_text())
  item={"trial":trial.name,"window_s":plan["window_s"],"source_commit":plan["source_commit"],
     "source_pins":plan.get("source_sha256"),
     "prepare_snapshot_status":"CAPTURED" if "source_sha256" in plan else "INITIAL_DEVELOPMENT_OVERLAY_NOT_CAPTURED_AT_IMPORT",
     "pairing":plan["pairing"],"actual_groups_by_epoch":[],
     "arc_event_reason_counts":dict(Counter(x for e in events for x in e["reasons"])),
     "arc_rules":{"maximum_gap_s":plan["max_gap_s"],"tdcp_bound_cycles":plan["tdcp_limit_cycles"]},
     "runs":[]}
  for row in plan["records"]:
   item["actual_groups_by_epoch"].append({"time_s":row["time_s"],"families":{
    name:{"status":entry["status"],"groups":[g["key"] for g in entry.get("groups",[])],
    "rows":entry.get("rows"),"ambiguities":entry.get("ambiguities"),"reason":entry.get("reason")}
    for name,entry in row["families"].items()}})
  for mode in ("SOLVE","SOLVE_ACTIVE"):
   source=trial/mode/"RESULTS.json"
   if not source.exists():continue
   full=json.loads(source.read_text());receipts[trial.name+"/"+mode+"/RESULTS.json"]=digest(source)
   write(a.docs/(trial.name+"_"+mode+".json"),full)
   for rec in full["records"]:
    cert=rec.get("certificate",{});best=rec.get("best");second=rec.get("second")
    compact={"trial":trial.name,"mode":mode,"family_requested":rec["family"],"prefix_epochs":rec["prefix_epochs"],
      "actual_group_keys":rec.get("actual_group_keys_by_epoch",[]),
      "status":rec["status"],"failure":rec.get("failure"),
      "integer_dimension":rec.get("ambiguities"),"observations":rec.get("observations"),
      "active_class_dimension":len(cert.get("distinct_ambiguity_labels",[])) if mode=="SOLVE_ACTIVE" else None,
      "best_full_cost":None if best is None else best["full_residual_cost"],
      "second_full_cost":None if second is None else second["full_residual_cost"],
      "objective_gap":None if second is None or best is None else second["full_residual_cost"]-best["full_residual_cost"],
      "objective_identity_error":None if best is None else best["objective_identity_error"],
      "length_error_m":None if best is None else best["maximum_length_error_m"],
      "elapsed_s":cert.get("elapsed_s"),"nodes":cert.get("expanded_nodes"),"termination":cert.get("termination_reason"),
      "global_objective_certificate":cert.get("global_optimum_certified",False),
      "accepted_integer_measurement":False}
    item["runs"].append(compact);table.append({k:(json.dumps(v) if isinstance(v,(list,dict)) else v) for k,v in compact.items()})
  for mode in ("FUTURE_CHECK_CATEGORIZED","FUTURE_ACTIVE"):
   path=trial/mode/"FUTURE_RESULTS.json"
   if not path.exists():continue
   full=json.loads(path.read_text());receipts[trial.name+"/"+mode+"/FUTURE_RESULTS.json"]=digest(path)
   for row in full["records"]:
    one=row["candidate_results"].get("best",{});two=row["candidate_results"].get("second",{})
    future.append({"trial":trial.name,"mode":mode,"family_requested":row["family"],
      "decision_prefix":row["decision_prefix"],"status":row.get("comparison_status"),
      "best_scored_epochs":one.get("scored_epochs"),"second_scored_epochs":two.get("scored_epochs"),
      "best_cost":one.get("residual_cost_sum"),"second_cost":two.get("residual_cost_sum"),
      "future_gap":row.get("future_cost_gap_second_minus_best"),
      "common_support":row.get("common_support_comparison"),
      "accepted_integer_measurement":False})
  summary["trials"].append(item)
 summary["real_solver_calls"]=len(table);summary["global_objective_certificates"]=sum(r["global_objective_certificate"] for r in table)
 summary["future_comparisons"]=future
 summary["input_result_sha256"]=receipts
 write(a.docs/"REAL_SUMMARY.json",summary)
 for name,rows in (("REAL_METRICS.csv",table),("FUTURE_METRICS.csv",[{k:(json.dumps(v) if isinstance(v,dict) else v) for k,v in x.items()} for x in future])):
  if rows:
   with (a.docs/name).open("w",newline="") as f:
    w=csv.DictWriter(f,list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 print(json.dumps({"solver_calls":summary["real_solver_calls"],"objective_certificates":summary["global_objective_certificates"],"future_comparisons":len(future)}))
if __name__=="__main__":main()
