#!/usr/bin/env python3
"""Causal raw-carrier window frontend with full/partial fixed-class comparison.

Reusable saved raw models; immutable per-window outcomes; no reference access.
Each successful output is the last validation epoch at its decision time.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,json,os,time
import numpy as np
from shadow_replay import load_model,candidate_pair
from real_trial import emit,serial,revision,source_snapshot,digest
from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal
from legsa_gins.paper_rebuild.carrier_phase.partial import PartialPolicy,prepare_partial_search,solve_partial,freeze_partial_candidates
from legsa_gins.paper_rebuild.carrier_phase.admission import AdmissionConfig,CausalAdmissionSession
from legsa_gins.paper_rebuild.carrier_phase.measurement import CSV_FIELDS,unavailable_measurement,diagnose_validated_window,qualify_current_baseline

def verify_solver_backend(result, backend):
    certificate = result.certificate
    expected = "python" if backend["kind"] == "python_sphere" else "native_scalar"
    if (certificate.sphere_backend != expected
            or certificate.sphere_library_sha256 != backend.get("library_sha256")):
        raise RuntimeError("requested sphere backend identity changed during frontend execution")

def selected_windows(plan,starts):
    for start in starts:
        rows=[row for row in plan["records"] if start<=row["time_s"]<start+2.]
        yield start,rows

def run(a):
    plan=json.loads((a.trial/"PLAN.json").read_text())
    a.output.mkdir(parents=True,exist_ok=True);cases_dir=a.output/"cases";cases_dir.mkdir(exist_ok=True)
    policy=PartialPolicy(max_ambiguities=a.partial_max_ambiguities)
    if a.likelihood == "selected-support" and a.modes != ["partial"]:
        raise ValueError("selected-support likelihood requires partial mode alone")
    if a.likelihood == "selected-support":
        from legsa_gins.paper_rebuild.carrier_phase.selected_likelihood import (
            prepare_selected_likelihood, solve_selected_likelihood,
            freeze_selected_likelihood_candidates)
    backend = {"kind": "python_sphere"}
    solver_options = {}
    if a.sphere_library is not None:
        backend = {"kind": "native_sphere", "library_sha256": digest(a.sphere_library)}
        solver_options["sphere_library"] = a.sphere_library
    sources=source_snapshot(a.code);sources[str(Path(__file__).relative_to(a.code))]=digest(__file__)
    identity={"model_plan_sha256":digest(a.trial/"PLAN.json"),"family":a.family,
      "length_m":plan["baseline_length_m"],"partial_policy":serial(policy),
      "nodes":a.nodes,"timeout_s":a.timeout,"alpha":.01,"angular_floor_deg":1.5,
      "likelihood":a.likelihood,"sphere_backend":backend,
      "source_files":sources,"data_mode":"real_by2_raw","trace_used_online":False}
    contract=a.output/"INPUT_CONTRACT.json"
    if contract.exists():
        if json.loads(contract.read_text())!=identity:raise ValueError("existing frontend inputs/algorithm contract differs")
    else:emit(contract,identity)
    calls=0;reused=0;terminal=[]
    for start,rows in selected_windows(plan,a.starts):
        for mode in a.modes:
            case=f"{mode}_{start:07.2f}"
            dest=cases_dir/(case+".json")
            if dest.exists():
                record=json.loads(dest.read_text())
                if record["input_contract"]!=identity["model_plan_sha256"]:
                    raise ValueError("saved case has different prepared input")
                reused+=1;terminal.append(case);continue
            began=time.monotonic()
            event_time=float(rows[-1]["time_s"]) if rows else float(start+2.)
            record={"case_id":case,"mode":mode,"window_start_s":start,
              "input_contract":identity["model_plan_sha256"],"execution_commit":revision(a.code),
              "status":"UNAVAILABLE","integer_truth_available":False,"search_called":False}
            measurement=unavailable_measurement(event_time,"UNAVAILABLE_INPUT")
            try:
                if len(rows)!=10:raise ValueError("fixed window requires exactly ten real epochs")
                selection=[load_model(a.trial,row,a.family) for row in rows[:5]]
                if mode=="partial":
                    prepare = (prepare_selected_likelihood if a.likelihood == "selected-support"
                               else prepare_partial_search)
                    search=prepare(selection,length_m=plan["baseline_length_m"],policy=policy)
                    record["subset_selection"]=serial(search.selection)
                    record["likelihood"]=a.likelihood
                    if a.likelihood == "selected-support":
                        record["selection_support"]=serial(search.supports)
                        record["selected_likelihood_plan_fingerprint"]=search.fingerprint if search.ready else None
                    if not search.selection.ready:
                        raise ValueError(search.selection.status)
                    problem=search.problem
                    record["search_called"]=True;calls+=1
                    print(json.dumps({"event":"SEARCH_START","case":case,"call":calls,
                                      "nuisance_and_selected_integers":problem.ambiguity_count,
                                      "selected":len(search.selection.selected_labels)}),flush=True)
                    if a.likelihood == "selected-support":
                        selected_result=solve_selected_likelihood(search,plan["lambda_library"],
                            node_limit=a.nodes,timeout_s=a.timeout,**solver_options)
                        result=selected_result.result
                    else:
                        result=solve_partial(search,plan["lambda_library"],node_limit=a.nodes,
                            timeout_s=a.timeout,**solver_options)
                    verify_solver_backend(result,backend)
                    record["search"]={"certificate":serial(result.certificate),"best":serial(result.best),
                                      "second":serial(result.second),"all_labels":problem.ambiguity_labels}
                    pair=(freeze_selected_likelihood_candidates(search,selected_result,source_id=case)
                          if a.likelihood == "selected-support"
                          else freeze_partial_candidates(search,result,source_id=case))
                else:
                    problem=assemble_epochs(selection,length_m=plan["baseline_length_m"])
                    active=selection[-1].ambiguity_labels
                    record["search_called"]=True;calls+=1
                    print(json.dumps({"event":"SEARCH_START","case":case,"call":calls,
                                      "nuisance_and_selected_integers":problem.ambiguity_count,
                                      "selected":len(active)}),flush=True)
                    result=solve_temporal(problem,plan["lambda_library"],distinct_ambiguity_labels=active,
                                          node_limit=a.nodes,timeout_s=a.timeout,**solver_options)
                    verify_solver_backend(result,backend)
                    source={"certificate":serial(result.certificate),"best":serial(result.best),
                            "second":serial(result.second),"ambiguity_labels":problem.ambiguity_labels}
                    record["search"]=source
                    pair=candidate_pair(source,active,selection[-1].time_s,case)
                record["frozen_candidates"]=[serial(c) for c in pair]
                future=[load_model(a.trial,row,a.family) for row in rows[5:]]
                session=CausalAdmissionSession(*pair,AdmissionConfig(length_m=plan["baseline_length_m"]))
                for model in future:session.observe(model)
                decision=session.finalize();record["admission"]=serial(decision)
                if decision.shadow_accepted:
                    diagnostic=diagnose_validated_window(future,pair[0],decision)
                    record["phase_diagnosis"]=serial(diagnostic)
                    measurement=qualify_current_baseline(future[-1],pair[0],decision,diagnostic,
                          length_m=plan["baseline_length_m"],angular_floor_rad=np.deg2rad(1.5),
                          availability_time_s=future[-1].time_s)
                else:
                    measurement=unavailable_measurement(event_time,decision.status)
                record["status"]=measurement.status
            except (ValueError,np.linalg.LinAlgError) as ex:
                record["failure"]=type(ex).__name__+":"+str(ex)
                measurement=unavailable_measurement(event_time,"UNAVAILABLE:"+str(ex))
                record["status"]=measurement.status
            record["measurement"]=serial(measurement);record["csv_row"]=measurement.csv_row()
            record["elapsed_s"]=time.monotonic()-began
            emit(dest,record);terminal.append(case)
            print(json.dumps({"event":"WINDOW_END","case":case,"status":record["status"],
                              "valid":measurement.valid,"elapsed_s":record["elapsed_s"]}),flush=True)
    # Each snapshot preserves previous reports and includes all completed cases.
    index=1
    while (a.output/f"SUMMARY_{index:04d}.json").exists():index+=1
    all_records=[json.loads(p.read_text()) for p in sorted(cases_dir.glob("*.json"))]
    summaries={}
    for mode in a.modes:
        selected=sorted((r for r in all_records if r["mode"]==mode),key=lambda x:x["window_start_s"])
        target=a.output/f"CARRIER_{mode.upper()}_{index:04d}.csv"
        with target.open("x",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=CSV_FIELDS,lineterminator="\n");writer.writeheader()
            for row in selected:writer.writerow(row["csv_row"])
        summaries[mode]={"cases":len(selected),"valid_experimental_measurements":sum(r["measurement"]["valid"] for r in selected),
                        "search_calls":sum(r["search_called"] for r in selected),
                        "statuses":dict(Counter(r["status"] for r in selected)),"csv":str(target),
                        "decision_times_s":[r["measurement"]["decision_available_time"] for r in selected if r["measurement"]["valid"]]}
    summary={"execution_commit":revision(a.code),"input_contract":identity,"new_search_calls":calls,
             "reused_cases":reused,"attempted_case_ids":terminal,"modes":summaries,
             "reference_reads":0,"production_measurement_validated":False}
    emit(a.output/f"SUMMARY_{index:04d}.json",summary)
    print(json.dumps({"event":"FRONTEND_COMPLETE","snapshot":index,"new_calls":calls,"reused":reused,"modes":summaries}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--trial",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--starts",type=float,nargs="+",required=True)
    p.add_argument("--modes",choices=("full","partial"),nargs="+",default=["full","partial"])
    p.add_argument("--family",default="GPS_GAL_BDS_DUAL")
    p.add_argument("--partial-max-ambiguities",type=int,default=8)
    p.add_argument("--likelihood",choices=("original","selected-support"),default="original")
    p.add_argument("--sphere-library",type=Path,
                   help="opt-in native sphere kernel; omitted uses the original Python backend")
    p.add_argument("--nodes",type=int,default=100000);p.add_argument("--timeout",type=float,default=30.)
    p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3])
    a=p.parse_args()
    if os.uname().sysname!="Linux":raise RuntimeError("run carrier algorithms in Ubuntu WSL")
    if len(set(a.starts))!=len(a.starts) or len(set(a.modes))!=len(a.modes):raise ValueError("duplicate windows/modes")
    run(a)
if __name__=="__main__":main()
