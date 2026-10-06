#!/usr/bin/env python3
"""Shadow admission on saved raw models: frozen candidates, fixed future slots."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import argparse,json,os,time
import numpy as np
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import SignalIdentity
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,assemble_epochs,TemporalModelError
from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate,AdmissionConfig,CausalAdmissionSession
from legsa_gins.paper_rebuild.carrier_phase.faults import build_phase_fault_map,stack_phase_fault_maps,fixed_integer_gls,single_fault_glrt
from real_trial import serial,emit,revision,source_snapshot,digest

def load_model(trial,row,family):
 entry=row["families"].get(family,{})
 if entry.get("status")!="BUILT":raise TemporalModelError("MODEL_UNAVAILABLE:"+str(entry.get("reason")))
 with np.load(trial/entry["file"]) as z:y,A,B,Q=[z[k] for k in ("y","A","B","Q")]
 labels=tuple(entry["ambiguity_labels"]);m=len(labels);groups=[];offset=0
 for saved in entry["groups"]:
  pivot=SignalIdentity(**saved["pivot"]);satellites=tuple(SignalIdentity(**s) for s in saved["satellites"])
  columns=tuple(range(offset,offset+len(satellites)));rows=columns+tuple(i+m for i in columns)
  groups.append(GroupDD(tuple(saved["key"]),pivot,satellites,y[list(rows)],A[np.ix_(rows,columns)],
    B[list(rows)],Q[np.ix_(rows,rows)],tuple(labels[i] for i in columns),rows,columns))
  offset+=len(satellites)
 if offset!=m:raise TemporalModelError("saved group dimensions mismatch")
 return MultiGnssEpoch(row["time_s"],y,A,B,Q,labels,tuple(groups),entry["metadata"])

def candidate_pair(source,active,selected_at,source_id):
 labels=tuple(source["ambiguity_labels"])
 if len(set(labels))!=len(labels) or not labels:raise TemporalModelError("INVALID_SELECTION_LABELS")
 for name in ("best","second"):
  candidate=source.get(name)
  if candidate is None or len(candidate["ambiguity"])!=len(labels):
   raise TemporalModelError("CANDIDATE_INTEGER_DIMENSION_MISMATCH")
 if not source.get("certificate",{}).get("global_optimum_certified") or source.get("best") is None or source.get("second") is None:
  raise TemporalModelError("SELECTION_NOT_GLOBALLY_CERTIFIED")
 return tuple(FrozenCandidate.from_mapping(name,selected_at,dict(zip(source["ambiguity_labels"],source[name]["ambiguity"])),
     tuple(active),source_id) for name in ("best","second"))

def validate(models,pair,length):
 session=CausalAdmissionSession(*pair,AdmissionConfig(length_m=length))
 issues=[]
 for model in models:
  try:session.observe(EpochBlock(model.time_s,model.y,model.A,model.B,model.Q,model.ambiguity_labels,model.metadata))
  except (ValueError,np.linalg.LinAlgError) as ex:issues.append({"time_s":model.time_s,"reason":str(ex)})
 decision=session.finalize()
 diagnosis={"status":"UNAVAILABLE"}
 try:
  problem=assemble_epochs(models,length_m=length)
  maps=[build_phase_fault_map(model) for model in models]
  stacked=stack_phase_fault_maps(maps,persistent=True)
  fit=fixed_integer_gls(problem,pair[0].integers)
  result=single_fault_glrt(fit,stacked,family_alpha=.01)
  diagnosis={"status":"DIAGNOSTIC_ONLY","residual_cost":fit.residual_cost,"df":fit.residual_df,
     "retained_rows":fit.rows_retained,"unknown_labels":fit.unknown_labels,"diagnosis":result,
     "physical_cause_certified":False,"working_model":"correct fixed N, Gaussian known Q, independent epochs"}
 except (ValueError,np.linalg.LinAlgError) as ex:diagnosis={"status":"UNAVAILABLE","reason":str(ex)}
 return decision,diagnosis,issues

def run(a):
 a.output.mkdir(parents=True,exist_ok=False)
 plan=json.loads((a.trial/"PLAN.json").read_text());length=plan["baseline_length_m"]
 execution=revision(a.code);pins=source_snapshot(a.code);pins[str(Path(__file__).relative_to(a.code))]=__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest()
 records=[];calls=0
 inputs={"PLAN.json":digest(a.trial/"PLAN.json")}
 jobs=[(family,None) for family in plan["families"]] if a.mode=="reuse" else [(family,start) for start in a.starts for family in plan["families"]]
 for family,start in jobs:
  case=f"{family}_"+("REUSED_PREFIX5" if start is None else f"{start:06.1f}")
  record={"case_id":case,"family_requested":family,"window_start_s":start,
     "selection_mode":a.mode,"status":"UNAVAILABLE","production_FIX":False,"false_fix_probability":None}
  began=time.monotonic()
  try:
   rows=plan["records"][:10] if start is None else [row for row in plan["records"] if start<=row["time_s"]<start+2.]
   if len(rows)!=10:raise TemporalModelError("FIXED_WINDOW_REQUIRES_EXACTLY_TEN_EPOCHS")
   for row in rows:
    entry=row["families"].get(family,{})
    if entry.get("status")=="BUILT":inputs[entry["file"]]=digest(a.trial/entry["file"])
   selection=[load_model(a.trial,row,family) for row in rows[:5]]
   future=[];future_unavailable=[]
   for row in rows[5:]:
    try:future.append(load_model(a.trial,row,family))
    except TemporalModelError as exc:future_unavailable.append({"time_s":row["time_s"],"reason":str(exc)})
   active=selection[-1].ambiguity_labels;selected_at=selection[-1].time_s
   if a.mode=="reuse":
    candidate_path=a.trial/"SOLVE_ACTIVE"/f"{family}_05.json"
    manifest_path=a.trial/"SOLVE_ACTIVE/RESULTS.json"
    source=json.loads(candidate_path.read_text());old_manifest=json.loads(manifest_path.read_text())
    expected_problem=assemble_epochs(selection,length_m=length)
    if (source["family"]!=family or source["prefix_epochs"]!=5
        or source["endpoint_time_s"]!=selected_at
        or tuple(source["ambiguity_labels"])!=expected_problem.ambiguity_labels):
     raise TemporalModelError("REUSED_CANDIDATE_CASE_OR_MODEL_IDENTITY_MISMATCH")
    inputs[str(candidate_path.relative_to(a.trial))]=digest(candidate_path)
    inputs[str(manifest_path.relative_to(a.trial))]=digest(manifest_path)
    record["selection_source"]={"candidate_sha256":digest(candidate_path),
       "execution_commit":old_manifest["execution_commit"],
       "source_sha256":old_manifest["source_sha256"],
       "selection_manifest_sha256":digest(manifest_path)}

   else:
    problem=assemble_epochs(selection,length_m=length)
    print(json.dumps({"event":"SELECTION_START","case_id":case,"call":calls+1,"integer_dimension":problem.ambiguity_count}),flush=True)
    calls+=1
    result=solve_temporal(problem,plan["lambda_library"],distinct_ambiguity_labels=active,node_limit=a.nodes,timeout_s=a.timeout)
    source={"certificate":serial(result.certificate),"best":serial(result.best),"second":serial(result.second),
        "ambiguity_labels":problem.ambiguity_labels}
   record["selection"]=source
   pair=candidate_pair(source,active,selected_at,record.get("selection_source",{}).get("candidate_sha256",case))
   decision,diagnosis,issues=validate(future,pair,length)
   record.update(status=decision.status,decision=decision,phase_diagnosis=diagnosis,issues=issues,future_model_unavailable=future_unavailable,
       selected_at=selected_at,active_labels=active,candidate_fingerprints=[x.fingerprint for x in pair],
       actual_group_keys_by_epoch=[[group.key for group in model.groups] for model in selection+future])
  except (ValueError,np.linalg.LinAlgError) as ex:record["failure"]=type(ex).__name__+":"+str(ex)
  record["elapsed_s"]=time.monotonic()-began
  emit(a.output/(case+".json"),record);records.append(serial(record))
  print(json.dumps({"event":"SHADOW_END","case_id":case,"status":record["status"],"failure":record.get("failure"),"elapsed_s":record["elapsed_s"]}),flush=True)
 emit(a.output/"RESULTS.json",{"execution_commit":execution,"source_pins":pins,"input_trial":a.trial.name,
    "mode":a.mode,"input_sha256":inputs,"solver_calls":calls,"reference_reads":0,"raw_payload_reads":0,
    "real_integer_truth_available":False,"counts":dict(Counter(r["status"] for r in records)),
    "records":records,"thresholds_fitted_on_real":False})
def main():
 p=argparse.ArgumentParser();p.add_argument("mode",choices=["reuse","stream"]);p.add_argument("--trial",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
 p.add_argument("--starts",type=float,nargs="+",default=list(range(120,140,2)))
 p.add_argument("--nodes",type=int,default=100000);p.add_argument("--timeout",type=float,default=30.)
 p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3]);a=p.parse_args()
 if os.uname().sysname!="Linux":raise RuntimeError("run algorithms in Ubuntu WSL")
 run(a)
if __name__=="__main__":main()
