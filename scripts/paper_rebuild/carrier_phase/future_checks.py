#!/usr/bin/env python3
"""Score two previously selected integer candidates on strictly future epochs."""
from pathlib import Path
import argparse,json,os,subprocess
import numpy as np
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,TemporalModelError
from legsa_gins.paper_rebuild.carrier_phase.validation import score_future_epoch
from real_trial import emit,revision

def run(a):
 plan=json.loads((a.trial/"PLAN.json").read_text())
 a.output.mkdir(parents=True,exist_ok=False);records=[]
 for family in (a.families or plan["families"]):
  for prefix in a.prefixes:
   source=json.loads((a.trial/a.solve_directory/f"{family}_{prefix:02d}.json").read_text())
   decision=source["endpoint_time_s"]
   record={"family":family,"decision_prefix":prefix,"decision_time_s":decision,
      "integer_selection_uses_future":False,"accepted_integer_measurement":False,
      "future_epoch_count":len(plan["records"])-prefix,"candidate_results":{}}
   for name in ("best","second"):
    if source.get(name) is None:continue
    integers=dict(zip(source["ambiguity_labels"],map(int,source[name]["ambiguity"])))
    scores=[]
    for row in plan["records"][prefix:]:
     entry=row["families"].get(family,{})
     try:
      if entry.get("status")!="BUILT":raise TemporalModelError("FUTURE_MODEL_UNAVAILABLE")
      with np.load(a.trial/entry["file"]) as z:
       block=EpochBlock(row["time_s"],z["y"],z["A"],z["B"],z["Q"],tuple(entry["ambiguity_labels"]))
      score=score_future_epoch(block,integers,decision_time_s=decision,length_m=plan["baseline_length_m"])
      scores.append({"status":"SCORED","score":score})
     except (ValueError,np.linalg.LinAlgError) as exc:
      scores.append({"status":"UNAVAILABLE","time_s":row["time_s"],"reason":str(exc)})
    record["candidate_results"][name]={
      "scored_epochs":sum(s["status"]=="SCORED" for s in scores),
      "residual_cost_sum":sum(s["score"].residual_cost for s in scores if s["status"]=="SCORED"),
      "known_phase_rows":sum(s["score"].known_phase_rows for s in scores if s["status"]=="SCORED"),
      "scores":scores}
   both=record["candidate_results"]
   if len(both)==2:
    future_labels={label for row in plan["records"][prefix:] for label in row["families"].get(family,{}).get("ambiguity_labels",[])}
    differing=[label for label,one,two in zip(source["ambiguity_labels"],source["best"]["ambiguity"],source["second"]["ambiguity"]) if one!=two]
    active_differences=[label for label in differing if label in future_labels]
    delta=both["second"]["residual_cost_sum"]-both["best"]["residual_cost_sum"]
    record["differing_labels_visible_in_future"]=active_differences
    record["comparison_status"]=("HISTORICAL_ONLY_DIFFERENCE" if not active_differences else
        ("FUTURE_SUPPORTS_ORIGINAL_BEST" if delta>1e-8 else "FUTURE_SUPPORTS_SECOND" if delta < -1e-8 else "TIED"))
    record["original_best_has_lower_future_cost"]=delta>1e-8
    record["future_cost_gap_second_minus_best"]=both["second"]["residual_cost_sum"]-both["best"]["residual_cost_sum"]
   records.append(record)
   print(json.dumps({k:v for k,v in record.items() if k!="candidate_results"}),flush=True)
 emit(a.output/"FUTURE_RESULTS.json",{"execution_commit":revision(a.code),"raw_payload_reads":0,"reference_reads":0,
    "integer_search_calls":0,"real_integer_truth_available":False,"threshold_calibrated":False,"records":records})
def main():
 p=argparse.ArgumentParser();p.add_argument("--trial",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
 p.add_argument("--solve-directory",default="SOLVE");p.add_argument("--prefixes",nargs="+",type=int,default=[1,5]);p.add_argument("--families",nargs="+")
 p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3]);a=p.parse_args()
 if os.uname().sysname!="Linux":raise RuntimeError("use Ubuntu WSL")
 run(a)
if __name__=="__main__":main()
