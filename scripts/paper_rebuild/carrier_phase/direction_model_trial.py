#!/usr/bin/env python3
"""Three projection-model trials using the already sealed PVT-control binary.

Explicit prepare/native/evaluate/compare commands only. Never compile, re-run
Euler controls, change legacy globals or open reference before all native seals.
Native source identity belongs to the reused execution, not current C++.
"""
from __future__ import annotations
import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import full_window_navigation as transport
require,sha,read,emit,pin,check,clone,launch,seal_files=(
    transport.require,transport.sha,transport.read,transport.emit,transport.pin,
    transport.check,transport.clone,transport.launch,transport.seal_files)
PLAN_REL="docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/MODEL_TRIAL_PLAN.json"
SOURCE_REL="scripts/paper_rebuild/carrier_phase/direction_model_trial.py"
SEQUENCES=("BY2","BY2H","BY2O")
ARM="LATERAL_PROJECTION"
IDS=tuple(s+"__"+ARM for s in SEQUENCES)
WINDOWS={"BY2":[66.,340.],"BY2H":[413.,683.],"BY2O":[3186.,3563.]}
EDIT_KEYS=("stage_id","protocol_id","case_id","run_id","run_label","outputpath","dual_yaw_prediction_model")

def registered(commit):
    reg=read(ROOT/PLAN_REL)
    require(reg["status"]=="REGISTERED_READY","model trial remains DRAFT")
    require(tuple(reg["run_ids"])==IDS and reg["window_s"]==WINDOWS,"fixed trial identities/windows")
    require(reg["budgets"]["new_native"]==reg["budgets"]["new_evaluator_max"]==3 and
            reg["budgets"]["config_checker"]==3 and reg["budgets"]["compile"]==0,"registered three-call budget")
    for rel in (PLAN_REL,SOURCE_REL):
        saved=subprocess.run(["git","show",commit+":"+rel],cwd=ROOT,check=True,capture_output=True).stdout
        require(saved==(ROOT/rel).read_bytes(),"registered payload changed: "+rel)
    for rel,h in reg["source_pins"].items():check({"path":str(ROOT/rel),"sha256":h})
    return reg

def reserve(stage,kind,run_id):
    require(kind in ("native","evaluator","loader") and run_id in IDS,"unregistered invocation")
    with (stage/(kind.upper()+"_LEDGER.jsonl")).open("a+") as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX);f.seek(0)
        rows=[json.loads(x) for x in f if x.strip()]
        require(len(rows)<3 and all(x["run_id"]!=run_id for x in rows),"budget/duplicate: no retry")
        row={"kind":kind,"run_id":run_id,"ordinal":len(rows)+1,"budget":3,
             "reserved_unix":time.time(),"retry":0}
        f.write(json.dumps(row)+"\n");f.flush();os.fsync(f.fileno())
    return row

def untouched(payload):
    return b"".join(line for line in payload.splitlines(keepends=True)
        if not any(re.match(rb"^[ \t]*"+re.escape(k.encode())+rb"[ \t]*:",line) for k in EDIT_KEYS))

def previous_metadata(baseline,reg):
    baseline=Path(baseline).resolve()
    pins={n:pin(check({"path":str(baseline/n),"sha256":h})) for n,h in reg["reused_stage_pins"].items()}
    old=read(baseline/"PLAN.json");ns=read(baseline/"ALL_NATIVE_SEALED.json")
    es=read(baseline/"EVALUATION_COMPLETE.json")
    require(old["schema"]=="trusted_heading.full_window_navigation.v1","reused schema")
    require(old["registration_commit"]==reg["native_execution_registration_commit"],"old native source registration")
    require(read(baseline/"PREPARED.json")["plan_sha256"]==sha(baseline/"PLAN.json") and
            ns["status"]=="SEALED" and ns["solver_calls"]==6 and
            es["status"]=="COMPLETE" and es["registered_run_count"]==6 and
            ns["plan_sha256"]==es["plan_sha256"]==sha(baseline/"PLAN.json") and
            es["native_seal_sha256"]==sha(baseline/"ALL_NATIVE_SEALED.json"),"reused seal chain")
    require(tuple(x["run_id"] for x in old["runs"])==transport.IDS and
            tuple(x["run_id"] for x in ns["records"])==transport.IDS and
            tuple(x["run_id"] for x in es["records"])==transport.IDS,"six historical identities")
    require(old["binary"]["sha256"]==reg["binary_sha256"] and
            old["checker"]["sha256"]==reg["checker_sha256"] and
            old["v3_lock"]["sha256"]==reg["v3_lock_sha256"] and
            old["evaluator"]["sha256"]==reg["evaluator_sha256"],"reused executable/evaluation identity")
    return old,ns,es,pins

def prepare(a):
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    reg=registered(a.registration_commit)
    baseline=Path(a.baseline_stage).resolve()
    old,ns,es,oldpins=previous_metadata(baseline,reg)
    aliases=old["aliases"]
    require(Path(aliases["<CODE_ROOT>"]).resolve()==ROOT,"code-root identity")
    require(transport.expand(reg["reused_stage"],aliases).resolve()==baseline,"registered reused stage")
    binary=check(old["binary"]);checker=check(old["checker"]);evaluator=check(old["evaluator"])
    lock=read(check(old["v3_lock"]));check(old["input_map"])
    stage=Path(a.stage).resolve()
    require(stage.is_relative_to(Path(aliases["<SCRATCH_ROOT>"]).resolve()),"new scratch output required")
    require(stage==transport.expand(reg["new_stage"],aliases).resolve(),"single registered output stage")
    stage.mkdir(parents=True,exist_ok=False);emit(stage/"REGISTERED_PLAN.json",reg)
    runs=[];inputs={}
    for sid in SEQUENCES:
        rid=sid+"__"+ARM
        prior=next(x for x in old["runs"] if x["run_id"]==sid+"__PVT_CONTROL")
        spec=next(x for x in old["sequences"] if x["sequence_id"]==sid)
        v3=next(x for x in lock["sequences"] if x["sequence_id"]==sid)
        require(prior["window"]==spec["full_window_s"]==v3["full_window_s"]==WINDOWS[sid],"full-window identity")
        require(prior["original_config"]["sha256"]==v3["configuration"]["sha256"] and
                spec["initialization"]==v3["initialization"] and
                spec["evaluation"]["baseline_median_m"]==v3["evaluation"]["baseline_median_m"] and
                spec["base_time_unix_s"]==v3["base_time_unix_s"],"unchanged V3 evaluation/init")
        src=check(prior["config"]);payload=src.read_bytes();cfg=frozen._runtime_mapping(payload)
        require(cfg["dual_yaw_prediction_model"]=="euler_yaw" and
                cfg["heading_source_policy"]=="pvt_priority_control" and
                cfg["runtime_contract"]=="research_experiment" and cfg["imudatalen"]==7 and
                cfg["imudatarate"]==500 and [cfg["starttime"],cfg["endtime"]]==WINDOWS[sid],"original Euler control contract")
        for key,item in prior["providers"].items():
            path=check(item);require(cfg[key]==str(path),"provider path changed")
            inputs[str(path)]=item
        path=check(prior["carrier"])
        require(cfg["external_carrier_baseline_path"]==str(path),"same bypassed carrier CSV")
        inputs[str(path)]=prior["carrier"]
        fields={"stage_id":reg["stage_id"],"protocol_id":reg["protocol_id"],"case_id":rid,
                "run_id":rid,"run_label":rid,"outputpath":str(stage/"NATIVE"/rid),
                "dual_yaw_prediction_model":"lateral_projection"}
        cloned,changes=clone(payload,fields);new=frozen._runtime_mapping(cloned)
        require(set(fields)==set(EDIT_KEYS) and untouched(cloned)==untouched(payload),"unapproved config line change")
        require({k:v for k,v in new.items() if k not in fields}=={k:v for k,v in cfg.items() if k not in fields},
                "unapproved scientific field change")
        cpath=stage/"CONFIGS"/(rid+".yaml");cpath.parent.mkdir(exist_ok=True);cpath.write_bytes(cloned)
        out=stage/"CHECKS"/rid;out.mkdir(parents=True)
        call=[str(checker),str(cpath),str(out/"ECHO")]
        reservation=reserve(stage,"loader",rid)
        emit(out/"INVOCATION.json",{"argv":call,"reservation":reservation,"solver_calls":0,"compile_calls":0})
        result=launch(call,out,60);emit(out/"RESULT.json",result)
        require(result["returncode"]==0 and not result["timed_out"],"loader failed; retain and stop")
        echo=read(out/"ECHO/RUN_MANIFEST.json")
        require(echo["dual_yaw_prediction_model"]=="lateral_projection" and
                echo["heading_source_policy"]=="pvt_priority_control","checker model/source echo")
        runs.append({"run_id":rid,"sequence_id":sid,"arm":ARM,"config":pin(cpath),
            "reused_control_run_id":prior["run_id"],"reused_control_config":prior["config"],
            "original_config":prior["original_config"],"changes":changes,
            "all_other_config_line_bytes_identical":True,"providers":prior["providers"],
            "carrier":prior["carrier"],"window":prior["window"],"checker_echo":pin(out/"ECHO/RUN_MANIFEST.json")})
        print("PREPARED",rid,flush=True)
    plan={"schema":"trusted_heading.direction_model_trial.v1","registration_commit":a.registration_commit,
        "registered_plan_sha256":sha(ROOT/PLAN_REL),"source_pins":reg["source_pins"],
        "native_source_registration_commit":old["registration_commit"],
        "native_source_identity":"Reused sealed executable; current C++ is not its source snapshot",
        "native_original_source_pins":old["source_pins"],
        "aliases":aliases,"binary":old["binary"],"checker":old["checker"],"evaluator":old["evaluator"],
        "input_map":old["input_map"],"v3_lock":old["v3_lock"],"sequences":old["sequences"],
        "reused_stage":str(baseline),"reused_stage_pins":oldpins,"runs":runs,"inputs":list(inputs.values()),
        "native_budget":3,"evaluator_budget":3,"config_checker_calls":3,"compile_calls":0,
        "reference_parent_reads":0,"raw_reads":0}
    emit(stage/"PLAN.json",plan)
    emit(stage/"PREPARED.json",{"status":"PREPARED","plan_sha256":sha(stage/"PLAN.json")})

def checked_plan(a):
    reg=registered(a.registration_commit)
    stage=Path(a.stage).resolve();plan=read(stage/"PLAN.json")
    require(stage==transport.expand(reg["new_stage"],plan["aliases"]).resolve(),"single registered output stage")
    require(plan["registration_commit"]==a.registration_commit and
            plan["registered_plan_sha256"]==sha(ROOT/PLAN_REL) and
            read(stage/"PREPARED.json")["plan_sha256"]==sha(stage/"PLAN.json"),"prepared registration chain")
    require(tuple(x["run_id"] for x in plan["runs"])==IDS,"three registered identities")
    previous_metadata(plan["reused_stage"],reg)
    for item in [plan["binary"],plan["checker"],plan["evaluator"],plan["v3_lock"],plan["input_map"],
                 *plan["inputs"],*(x["config"] for x in plan["runs"]),*(x["checker_echo"] for x in plan["runs"])]:
        check(item)
    return stage,plan

def heading_event_counts(path):
    """Separate derived counters; never overwrite known-buggy runtime manifest."""
    with Path(path).open(newline="") as f:rows=list(csv.DictReader(f))
    require(rows,"missing heading event ledger")
    last=-math.inf
    counts={"event_rows":len(rows),"pvt_attempts":0,"pvt_accepted":0,"carrier_attempts":0,"carrier_accepted":0}
    for row in rows:
        t=float(row["time"]);require(math.isfinite(t) and t>last,"heading event order");last=t
        values=[row[k] for k in ("pvt_attempted","carrier_attempted","accepted")]
        require(all(v in ("0","1") for v in values),"heading boolean domain")
        pa,ca,accepted=map(int,values)
        require(pa+ca<=1 and (not accepted or pa+ca==1),"accepted source identity")
        counts["pvt_attempts"]+=pa;counts["carrier_attempts"]+=ca
        counts["pvt_accepted"]+=pa*accepted;counts["carrier_accepted"]+=ca*accepted
    require(counts["carrier_attempts"]==counts["carrier_accepted"]==0,"PVT-control attempted carrier")
    return {"source":"HEADING_SOURCE_EVENTS.csv","counts":counts,
            "runtime_manifest_counter_bug_preserved":True,"does_not_rewrite_runtime_outputs":True}

def native(a):
    import numpy as np
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    stage,plan=checked_plan(a);records=[]
    require(not (stage/"NATIVE").exists(),"native exists: no retry")
    prior=read(Path(plan["reused_stage"])/"ALL_NATIVE_SEALED.json")
    for run in plan["runs"]:
        rid=run["run_id"];out=stage/"NATIVE"/rid;out.mkdir(parents=True)
        reservation=reserve(stage,"native",rid)
        argv=["strace","-f","-yy","-s","4096","-e","trace=openat,execve","-o",str(out/"OPENAT.strace"),
              plan["binary"]["path"],"--config",run["config"]["path"],"--output-dir",str(out)]
        emit(out/"INVOCATION.json",{"argv":argv,"reservation":reservation,"plan_sha256":sha(stage/"PLAN.json")})
        rec={k:run[k] for k in ("run_id","sequence_id","arm")}
        try:
            rec.update(launch(argv,out,1200))
            rec["access_audit"]=transport.native_access(out/"OPENAT.strace",plan,run,out)
            require(rec["access_audit"]["passed"],"passive native access audit")
            require(rec["returncode"]==0 and not rec["timed_out"],"native failed without retry")
            manifest=read(out/"RUN_MANIFEST.json");echo=read(check(run["checker_echo"]))
            for key in ("run_id","stage_id","protocol_id","case_id","algorithm_id","data_mode","runtime_contract",
                        "heading_source_policy","dual_yaw_prediction_model","actual_solver_input_paths","actual_solver_input_roles",
                        "heading_pvt_freshness_s","heading_accepted_cross_source_exclusion_s"):
                require(manifest.get(key)==echo.get(key),"runtime/loader identity: "+key)
            nav=pin(out/"KF_GINS_Navresult.nav");std=pin(out/"KF_GINS_STD.txt")
            numeric,_=frozen.read_native_numeric(nav["path"],columns=11)
            st,_=frozen.read_native_numeric(std["path"]);frozen._support(numeric,run["window"])
            require(st.ndim==2 and st.shape[1]>=10 and len(st)==len(numeric) and np.isfinite(st).all(),"STD shape/finite")
            require(np.array_equal(st[:,0],numeric[:,1]),"NAV/STD exact time keys")
            bound=frozen.bounded_lla_native(nav["path"],expected_sha256=nav["sha256"])
            timehash=hashlib.sha256(np.asarray(numeric[:,1],dtype="<f8").tobytes()).hexdigest()
            old=next(x for x in prior["records"] if x["run_id"]==run["reused_control_run_id"])
            # Retain mismatch as coverage evidence; do not trim or force a rerun.
            rec.update(status="COMPLETED" if bound["passed"] else "ALGORITHM_FAILURE_DIVERGED",
                nav=nav,std=std,bound=bound,output_rows=len(numeric),first_time=float(numeric[0,1]),
                last_time=float(numeric[-1,1]),time_keys_sha256=timehash,
                time_key_encoding="little-endian float64 C-order bytes",
                same_time_keys_as_reused_euler=timehash==old["time_keys_sha256"],
                heading_counts_raw_manifest={k:v for k,v in manifest.items() if k.startswith("heading_") and k.endswith("_count")},
                heading_events=pin(out/"HEADING_SOURCE_EVENTS.csv"),
                heading_counts_derived=heading_event_counts(out/"HEADING_SOURCE_EVENTS.csv"),
                manifest=pin(out/"RUN_MANIFEST.json"))
            emit(out/"RESULT.json",rec);records.append(rec)
        except BaseException as exc:
            rec.update(status="FAILED_TECHNICAL",error=repr(exc),traceback=traceback.format_exc())
            emit(out/"FAILED.json",rec);raise
        print("NATIVE",rid,rec["status"],flush=True)
    emit(stage/"ALL_NATIVE_SEALED.json",{"status":"SEALED","plan_sha256":sha(stage/"PLAN.json"),
        "solver_calls":3,"records":records,"reference_reads":0,"files":seal_files(stage/"NATIVE",stage)})

def evaluate(a):
    import numpy as np
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    from legsa_gins.paper_rebuild.protocol_v3.evaluation_process import evaluate as evaluator
    stage,plan=checked_plan(a);seal=read(stage/"ALL_NATIVE_SEALED.json")
    require(seal["status"]=="SEALED" and seal["plan_sha256"]==sha(stage/"PLAN.json") and
            tuple(r["run_id"] for r in seal["records"])==IDS,"all three native outputs must be sealed")
    for rel,h in seal["files"].items():check({"path":str(stage/rel),"sha256":h})
    records=[];calls=0
    require(not (stage/"EVALUATION").exists(),"evaluation directory already exists: no retry")
    for record in seal["records"]:
        rid=record["run_id"];out=stage/"EVALUATION"/rid;out.mkdir(parents=True)
        spec=next(s for s in plan["sequences"] if s["sequence_id"]==record["sequence_id"])
        identity={"run_id":rid,"sequence_id":record["sequence_id"],"dataset_id":record["sequence_id"],"arm":record["arm"],
                  "evaluator_contract":"evaluator_contract_v3","evaluator_sha256":plan["evaluator"]["sha256"],
                  "source_nav_sha256":record["nav"]["sha256"],"std_sha256":record["std"]["sha256"],
                  "reference_is_independent_ground_truth":False}
        if record["status"]!="COMPLETED":
            result={"row":{**identity,"status":"NOT_RUN_ALGORITHM_FAILURE","metrics_admitted":False},
                    "error_series":None,"output_support":record}
        else:
            try:
                nav=check(record["nav"]);std=check(record["std"])
                original,_=frozen.read_native_numeric(nav,columns=11);window=frozen._support(original,spec["full_window_s"])
                actual=out/"EVAL_NAV_V3.nav"
                baseline=spec["evaluation"]["baseline_median_m"]
                frozen.write_transformed_nav(nav,actual,frozen.transform_nav(original,baseline))
                transform={"input":record["nav"],"output":pin(actual),"baseline_median_m":baseline,
                    "lever_frd_m":[.03,.03-baseline/2,-.30],"changed_columns_zero_based":[2,3,4],
                    "std_transformed":False,"fit_used":False,"uncertainty_status":"UNTRANSPORTED_STD_DIAGNOSTIC_ONLY"}
                reservation=reserve(stage,"evaluator",rid);calls+=1
                emit(out/"INVOCATION.json",{"reservation":reservation,"native_seal_sha256":sha(stage/"ALL_NATIVE_SEALED.json"),
                     "trace_identity_from_lock_only":spec["reference"],"reference_parent_reads":0,"transform":transform})
                ev=evaluator(evaluator=Path(plan["evaluator"]["path"]),trace=Path(spec["reference"]["path"]),nav=actual,std=std,
                    outdir=out/"FROZEN_EVALUATOR",base_time=spec["base_time_unix_s"],window=window,
                    trace_sha256=spec["reference"]["sha256"],code_root=ROOT,raw_root=Path(plan["aliases"]["<RAW_ROOT>"]),
                    clean_root=Path(plan["aliases"]["<CLEAN_ROOT>"]),instrument=True,consistency_policy="canonical_v2_wgs84_full_support")
                audit,capture=frozen._capture(ev,SimpleNamespace(trace_sha256=spec["reference"]["sha256"]))
                require(capture["consistency"]["passed"],"frozen evaluator consistency")
                errors=frozen.canonical._read_error_series(out/"FROZEN_EVALUATOR")
                ts=np.asarray(errors["time"],float)
                require(len(ts)>0 and np.isfinite(ts).all() and np.all(np.diff(ts)>0) and np.all((ts>=window[0])&(ts<=window[1])),"matched support")
                row=frozen.window_metrics(errors,original,identity,window,capture.get("reference_epoch_count"))
                row.update(status="COMPLETED",metrics_admitted=True,evaluation_invoked=True,
                           source_nav_sha256=record["nav"]["sha256"],uncertainty_status="UNTRANSPORTED_STD_DIAGNOSTIC_ONLY")
                result={"row":row,"audit":audit,"capture":capture,"transform":transform,
                    "error_series":pin(out/"FROZEN_EVALUATOR/error_series.csv"),
                    "output_support":{k:record[k] for k in ("output_rows","first_time","last_time","time_keys_sha256","nav","std")},
                    "matched_time_keys_sha256":hashlib.sha256(np.asarray(ts,dtype="<f8").tobytes()).hexdigest()}
            except BaseException as exc:
                emit(out/"FAILED.json",{"error":repr(exc),"traceback":traceback.format_exc(),"no_retry":True});raise
        emit(out/"EVALUATION_RESULT.json",result)
        records.append({k:record[k] for k in ("run_id","sequence_id","arm")}|
                       {"result":pin(out/"EVALUATION_RESULT.json"),"error_series":result["error_series"]})
        print("EVALUATED",rid,result["row"]["status"],flush=True)
    emit(stage/"EVALUATION_COMPLETE.json",{"status":"COMPLETE","evaluator_calls":calls,"registered_run_count":3,
        "plan_sha256":sha(stage/"PLAN.json"),"native_seal_sha256":sha(stage/"ALL_NATIVE_SEALED.json"),
        "records":records,"files":seal_files(stage/"EVALUATION",stage),
        "reference_parent_reads":0,"reference":"shared GNSS commercial reference, not independent truth"})


def compare(a):
    """Only sealed evaluator rows/error series; no new reference resolution."""
    import numpy as np
    import compare_full_window_navigation as base
    import compare_clone_window_navigation as derived
    stage,plan=checked_plan(a)
    n=read(stage/"ALL_NATIVE_SEALED.json");e=read(stage/"EVALUATION_COMPLETE.json")
    require(n["status"]=="SEALED" and e["status"]=="COMPLETE" and
            n["plan_sha256"]==e["plan_sha256"]==sha(stage/"PLAN.json") and
            e["native_seal_sha256"]==sha(stage/"ALL_NATIVE_SEALED.json"),"new comparison seal chain")
    nr={x["run_id"]:x for x in n["records"]};er={x["run_id"]:x for x in e["records"]}
    require(tuple(nr)==tuple(er)==IDS and len(n["records"])==len(e["records"])==3,"three output identities")
    previous,pn,pe,pnr,per=derived.stage_metadata(plan["reused_stage"],base.ARMS)
    lp=ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
    fp=ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_METRICS.csv"
    require(sha(lp)==base.V3_LOCK_SHA256 and sha(fp)==base.V3_FACTS_SHA256,"V3 facts/lock")
    lock=read(lp);facts={x["sequence_id"]:x for x in base.read_csv(fp)}
    cache={};rows=[];coverage=[];effects=[];events=[]
    for sid in SEQUENCES:
        spec=next(x for x in lock["sequences"] if x["sequence_id"]==sid);fact=facts[sid]
        require(fact["source_result_sha256"]==spec["evaluation"]["result"]["sha256"],"V3 metric provenance")
        op=spec["evaluation"]["retained_error_series"]
        oldpath=Path(op["path"].replace("<V3_ROOT>",plan["aliases"]["<V3_ROOT>"]))
        require("<" not in str(oldpath) and sha(oldpath)==op["sha256"],"retained V3 error-series pin")
        old=base.errors_from_rows(base.read_csv(oldpath))
        require(len(old["time"])==int(fact["matched_epoch_count"]),"V3 actual support")
        cur=derived.load_run(stage,n,e,nr[sid+"__"+ARM],er[sid+"__"+ARM],spec,lock,cache)
        ctrl=derived.load_run(previous,pn,pe,pnr[sid+"__PVT_CONTROL"],per[sid+"__PVT_CONTROL"],spec,lock,cache)
        for label,item in ((ARM,cur),("REUSED_EULER_PVT_CONTROL",ctrl)):
            cov=derived.coverage_row(sid,label,item,old,fact,spec["full_window_s"])
            cov["source_run_id"]=item["native"]["run_id"];coverage.append(cov)
            rows.append(base.comparison_row(sid,label,"FULL_AVAILABLE_FROZEN",item["row"],fact,len(item["errors"]["time"])))
            oo,nn=base.common_errors(old,item["errors"])
            rows.append(base.comparison_row(sid,label,"COMMON_V3_MATCHED_EXACT_KEYS",
                                           base.metrics(nn),base.metrics(oo),len(oo["time"])))
            events.append({"sequence_id":sid,"arm":label,"source_run_id":item["native"]["run_id"],
                "channels":[base.event_summary(np.union1d(old["time"],item["native_times"]),item["errors"],c,spec["full_window_s"])
                            for c in base.CHANNELS]})
        events.append({"sequence_id":sid,"arm":"ORIGINAL_V3","source_run_id":spec["run_id"],
            "channels":[base.event_summary(old["time"],old,c,spec["full_window_s"]) for c in base.CHANNELS]})
        effects.extend(derived.paired_effects(sid,cur,ctrl,"DIRECTION_MODEL_ONLY",ARM,
            "REUSED_EULER_PVT_CONTROL","COMMON_PROJECTION_EULER_EXACT_KEYS"))
    current={x["sequence_id"]:x for x in rows if x["arm"]==ARM and x["support"]=="FULL_AVAILABLE_FROZEN"}
    cov={x["sequence_id"]:x["coverage_nondegraded"] for x in coverage if x["arm"]==ARM}
    values=[current[s]["all_metric_nondegraded"] for s in SEQUENCES]+[cov[s] for s in SEQUENCES]
    nd=False if False in values else None if None in values else True
    qualifying=[s for s in SEQUENCES if current[s].get("yaw_rmse_relative_reduction") is not None and
                current[s]["yaw_rmse_relative_reduction"]>=.05]
    A=None if nd is None else bool(nd and len(qualifying)>=2)
    full={x["sequence_id"]:x for x in effects if x["support"]=="FULL_AVAILABLE_FROZEN"}
    common={x["sequence_id"]:x for x in effects if x["support"]=="COMMON_PROJECTION_EULER_EXACT_KEYS"}
    attributable=[s for s in qualifying if full[s]["strict_improved_yaw_rmse_deg"] is True and
        common[s]["strict_improved_yaw_rmse_deg"] is True and common[s]["same_complete_error_keys"] is True]
    gate={"all_sequence_nondegradation_vs_original_V3":nd,"A_original_V3_contract":A,
        "A_sequences_at_least_5_percent":qualifying,"A_sequences_with_positive_model_effect":attributable,
        "recommend_model_change_for_review":bool(A and len(attributable)>=2),
        "B":None,"B_reason":"NO_CARRIER_RECOVERY_COMPARISON_IN_THIS_MODEL_ONLY_TRIAL",
        "AR_gain_claim":False,"independent_HV_claim":False,"integer_correctness":None,
        "false_fix_probability":None,"velocity_truth_metrics":None,"reference_is_independent_truth":False,
        "main_replacement_authorized":False}
    out=Path(a.out).resolve();require(out==stage/"COMPARISON","single registered comparison output")
    out.mkdir(parents=True,exist_ok=False)
    base.write_csv(out/"V3_COMPARISONS.csv",rows);base.write_csv(out/"MODEL_DIFFERENCES.csv",effects)
    base.write_csv(out/"COVERAGE.csv",coverage)
    emit(out/"COMPARISON.json",{"schema":"trusted_heading.direction_model_comparison.v1",
        "gate":gate,"events":events,"native_calls":0,"evaluator_calls":0,"reference_reads":0,
        "new_plan_sha256":sha(stage/"PLAN.json"),"new_native_seal_sha256":sha(stage/"ALL_NATIVE_SEALED.json"),
        "new_evaluation_complete_sha256":sha(stage/"EVALUATION_COMPLETE.json"),
        "reused_evaluation_complete_sha256":sha(previous/"EVALUATION_COMPLETE.json"),
        "source_sha256":sha(Path(__file__)),"v3_facts_sha256":sha(fp),"missing_metrics_are_NA":True})

def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=("prepare","native","evaluate","compare"))
    p.add_argument("--stage",type=Path,required=True);p.add_argument("--registration-commit",required=True)
    p.add_argument("--baseline-stage",type=Path);p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.command=="prepare":require(a.baseline_stage is not None,"prepare requires baseline stage")
    if a.command=="compare":require(a.out is not None,"compare requires new output directory")
    try:globals()[a.command](a)
    except BaseException as exc:
        if a.stage.exists():
            name=a.command.upper()+"_FAILED.json"
            if not (a.stage/name).exists():
                emit(a.stage/name,{"error":repr(exc),"traceback":traceback.format_exc(),"retry":0})
        raise
if __name__=="__main__":main()
