#!/usr/bin/env python3
"""Six original-window NULL_CLONE/PAIR_YOUNG trials; explicit commands only.

Reuses immutable fallback configuration/input lineage and pure transport helpers.
No legacy module globals are changed. Evaluation is disabled until all six native
outputs are sealed. Importing this module performs no data access or algorithm call.
"""
from __future__ import annotations
import argparse
from collections import Counter
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
import full_window_navigation as legacy

require,sha,read,emit,pin,check,clone,launch,seal_files = (
    legacy.require,legacy.sha,legacy.read,legacy.emit,legacy.pin,legacy.check,
    legacy.clone,legacy.launch,legacy.seal_files)
PLAN_REL="docs/paper_rebuild/TRUSTED_HEADING_20261006/CLONE_WINDOW_NAVIGATION_R2_PLAN.json"
SOURCE_REL="scripts/paper_rebuild/carrier_phase/clone_window_navigation.py"
SEQUENCES=("BY2","BY2H","BY2O")
ARMS=("NULL_CLONE","PAIR_YOUNG")
IDS=tuple(s+"__"+arm for s in SEQUENCES for arm in ARMS)
WINDOWS={"BY2":[66.,340.],"BY2H":[413.,683.],"BY2O":[3186.,3563.]}
FOOT_COLUMNS=("event_time_s available_time_s event_type clone_id source_time_s endpoint_id "
              "foot_i foot_j episode_i episode_j d_body_frd_x_m d_body_frd_y_m d_body_frd_z_m reason").split()
FOOT_COLUMNS += ["sigma_"+str(i)+str(j) for i in range(6) for j in range(6)]

def registered(commit):
    p=read(ROOT/PLAN_REL)
    require(p["status"]=="REGISTERED_READY","clone navigation registration is DRAFT")
    require(tuple(p["run_ids"])==IDS and p["window_s"]==WINDOWS,"fixed clone trial identities/windows")
    require(p["budgets"]["new_native"]==p["budgets"]["new_evaluator_max"]==6,"six-call budget")
    require(p["binary"]["sha256"] and p["static_library"]["sha256"] and p["native_local_qualification"],
            "new binary/local qualification not yet registered")
    for rel in (PLAN_REL,SOURCE_REL):
        saved=subprocess.run(["git","show",commit+":"+rel],cwd=ROOT,check=True,capture_output=True).stdout
        require(saved==(ROOT/rel).read_bytes(),"registration payload changed: "+rel)
    for rel,h in p["source_pins"].items():check({"path":str(ROOT/rel),"sha256":h})
    return p

def reserve(stage,kind,run_id):
    require(kind in ("native","evaluator") and run_id in IDS,"unregistered clone invocation")
    with (stage/(kind.upper()+"_LEDGER.jsonl")).open("a+") as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX);f.seek(0)
        rows=[json.loads(x) for x in f if x.strip()]
        require(len(rows)<6 and all(x["run_id"]!=run_id for x in rows),"budget/duplicate: no retry")
        row={"kind":kind,"run_id":run_id,"ordinal":len(rows)+1,"budget":6,"reserved_unix":time.time(),"retry":0}
        f.write(json.dumps(row)+"\n");f.flush();os.fsync(f.fileno())
    return row

def untouched(payload,fields):
    return b"".join(line for line in payload.splitlines(keepends=True)
        if not any(re.match(rb"^[ \t]*"+re.escape(k.encode())+rb"[ \t]*:",line) for k in fields))

def foot_audit(path,window,summary):
    """Input/schema/ledger audit only; no state or contact inference."""
    with Path(path).open(newline="") as f:
        rd=csv.DictReader(f);require(rd.fieldnames==FOOT_COLUMNS,"foot50 header");rows=list(rd)
    last=-math.inf;active=None;ids=set();endpoints=set();counts=Counter()
    for row in rows:
        require(None not in row and None not in row.values(),"foot column mismatch")
        t=float(row["event_time_s"]);a=float(row["available_time_s"]);kind=row["event_type"]
        require(math.isfinite(t) and t==a and last<t and window[0]<=t<=window[1],"foot time/window")
        last=t;counts[kind]+=1
        require(kind in ("START","END","RETIRE") and row["clone_id"] and row["reason"],"foot event identity")
        if kind=="RETIRE":
            require(active is not None and row["clone_id"]==active["clone_id"],"retire lifecycle")
            require(all(row[k]=="" for k in FOOT_COLUMNS[4:13]+FOOT_COLUMNS[14:]),"retire measurement fields")
            active=None;continue
        require(float(row["source_time_s"])==t and row["endpoint_id"] not in endpoints,"source time/duplicate endpoint")
        endpoints.add(row["endpoint_id"])
        require(row["endpoint_id"] and row["episode_i"] and row["episode_j"] and
                row["foot_i"] in ("FR","FL","RR","RL") and row["foot_j"] in ("FR","FL","RR","RL") and
                row["foot_i"]!=row["foot_j"],"foot endpoint/source identity")
        d=[float(row[k]) for k in FOOT_COLUMNS[10:13]]
        require(all(math.isfinite(x) for x in d) and sum(x*x for x in d)>1e-20,"foot vector domain")
        if kind=="START":
            require(active is None and row["clone_id"] not in ids,"overlap/revival")
            require(all(row[k]=="" for k in FOOT_COLUMNS[14:]),"START cannot carry future covariance")
            ids.add(row["clone_id"]);active=row.copy()
        else:
            require(active is not None and row["clone_id"]==active["clone_id"],"END missing START")
            require(.1-1e-9<=t-float(active["event_time_s"])<=.15+1e-9,"END registered interval")
            require(all(row[k]==active[k] for k in ("foot_i","foot_j","episode_i","episode_j")),"END pair/arc changed")
            for i in range(6):
                for j in range(6):
                    v=float(row["sigma_"+str(i)+str(j)]);expected=.0008 if i==j else 0.
                    require(math.isfinite(v) and abs(v-expected)<1e-15,"registered Sigma6 bound changed")
            active=None
    require(active is None,"provider did not finish lifecycle")
    require(dict(counts)==summary["events"],"foot provider sealed counts mismatch")
    return {"rows":len(rows),"counts":dict(counts),"all_opportunities_retained":summary["all_opportunities_retained"],
            "first_time":None if not rows else float(rows[0]["event_time_s"]),
            "last_time":None if not rows else float(rows[-1]["event_time_s"]),
            "source_time_replay_assumption":True,"working_sigma_m":.01,
            "Sigma6_bound_diagonal_m2":.0008,"physical_covariance_calibrated":False}

def prepare(a):
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    reg=registered(a.registration_commit)
    baseline=Path(a.baseline_stage).resolve();foot=Path(a.foot_provider).resolve()
    oldpins={n:pin(check({"path":str(baseline/n),"sha256":h})) for n,h in reg["reused_stage_pins"].items()}
    previous=read(baseline/"PLAN.json");oldseal=read(baseline/"ALL_NATIVE_SEALED.json")
    oldeval=read(baseline/"EVALUATION_COMPLETE.json")
    require(previous["schema"]=="trusted_heading.full_window_navigation.v1","original prepared schema")
    require(read(baseline/"PREPARED.json")["plan_sha256"]==sha(baseline/"PLAN.json"),"original prepared chain")
    require(oldseal["status"]=="SEALED" and oldseal["solver_calls"]==6 and
            oldseal["plan_sha256"]==sha(baseline/"PLAN.json") and
            oldeval["status"]=="COMPLETE" and oldeval["registered_run_count"]==6 and
            oldeval["native_seal_sha256"]==sha(baseline/"ALL_NATIVE_SEALED.json") and
            oldeval["plan_sha256"]==sha(baseline/"PLAN.json"),"reused six-result metadata chain")
    require(tuple(x["run_id"] for x in previous["runs"])==legacy.IDS and
            tuple(x["run_id"] for x in oldseal["records"])==legacy.IDS and
            tuple(x["run_id"] for x in oldeval["records"])==legacy.IDS,"all original six identities retained")
    aliases=previous["aliases"];require(Path(aliases["<CODE_ROOT>"])==ROOT,"code root alias")
    require(previous["v3_lock"]["sha256"]==reg["v3_lock_sha256"],"V3 lock identity")
    lock=read(check(previous["v3_lock"]))
    require(sha(check(previous["evaluator"]))==reg["evaluator_sha256"],"unchanged frozen evaluator")
    terminal=read(check({"path":str(foot/"COMPLETE.json"),"sha256":reg["foot_complete_sha256"]}))
    require(terminal["status"]=="COMPLETE" and not (foot/"FAILED.json").exists(),"provider terminal")
    fsummary=read(check({"path":str(foot/"SUMMARY.json"),"sha256":terminal["files"]["SUMMARY.json"]}))
    require(fsummary["status"]=="COMPLETE" and fsummary["native_calls"]==fsummary["reference_reads"]==0,"foot input-only role")
    require(tuple(x["sequence_id"] for x in fsummary["sequences"])==SEQUENCES,"three sealed foot sequences")
    foot_plan=read(check({"path":str(foot/"PLAN.json"),"sha256":terminal["files"]["PLAN.json"]}))
    require(foot_plan["v3_lock_sha256"]==reg["v3_lock_sha256"],"foot sequence lineage")
    stage=Path(a.stage).resolve()
    require(stage.is_relative_to(Path(aliases["<SCRATCH_ROOT>"]).resolve()),"scratch output required")
    stage.mkdir(parents=True,exist_ok=False);emit(stage/"REGISTERED_PLAN.json",reg)
    binary=check({**reg["binary"],"path":str(legacy.expand(reg["binary"]["path"],aliases))})
    library=check({**reg["static_library"],"path":str(legacy.expand(reg["static_library"]["path"],aliases))})
    qualification=check({**reg["native_local_qualification"],"path":str(legacy.expand(reg["native_local_qualification"]["path"],aliases))})
    build=stage/"CONFIG_CHECKER";build.mkdir();source=build/"config_check.cpp";source.write_text(legacy.CHECKER)
    argv=["c++","-std=c++17","-O2","-I",str(ROOT/"cpp/legsa_v23_port_core/include"),str(source),str(library),"-o",str(build/"config_check")]
    emit(build/"COMPILE_INVOCATION.json",{"argv":argv,"static_library":pin(library),"algorithm_calls":0})
    result=launch(argv,build,120);emit(build/"COMPILE_RESULT.json",result)
    require(result["returncode"]==0 and not result["timed_out"],"config checker compilation failed")
    checker=pin(build/"config_check");runs=[];inputs={}
    for sid in SEQUENCES:
        old=next(x for x in previous["runs"] if x["run_id"]==sid+"__CARRIER_FALLBACK")
        seq=next(x for x in previous["sequences"] if x["sequence_id"]==sid)
        v3=next(x for x in lock["sequences"] if x["sequence_id"]==sid)
        require(old["window"]==seq["full_window_s"]==v3["full_window_s"]==WINDOWS[sid],"original full window")
        require(old["original_config"]["sha256"]==v3["configuration"]["sha256"],"original config identity")
        require(seq["initialization"]==v3["initialization"] and
                seq["base_time_unix_s"]==v3["base_time_unix_s"] and
                seq["evaluation"]["baseline_median_m"]==v3["evaluation"]["baseline_median_m"] and
                seq["reference"]["sha256"]==v3["evaluation"]["reference"]["sha256"] and
                seq["reference"]["path"]==str(legacy.expand(v3["evaluation"]["reference"]["path"],aliases)),
                "V3 initialization/time/physical evaluation/reference identity")
        require(len(old["providers"])==5 and set(old["providers"])==set(v3["runtime_provider_pins"]),"five V3 providers")
        for key,p in old["providers"].items():
            require(p["sha256"]==v3["runtime_provider_pins"][key]["sha256"],"V3 provider hash lineage")
            check(p);inputs[p["path"]]=p
        check(old["carrier"]);inputs[old["carrier"]["path"]]=old["carrier"]
        payload=check(old["config"]).read_bytes();cfg=frozen._runtime_mapping(payload)
        require(cfg["heading_source_policy"]=="pvt_priority_fallback" and cfg["dual_yaw_prediction_model"]=="euler_yaw" and
                cfg["imudatalen"]==7 and cfg["imudatarate"]==500 and
                [cfg["starttime"],cfg["endtime"]]==WINDOWS[sid],"unchanged prior fallback model/time")
        for key,p in old["providers"].items():require(cfg[key]==p["path"],"inherited provider path")
        require(cfg["external_carrier_baseline_path"]==old["carrier"]["path"],"same sealed carrier")
        for key,value in seq["initialization"].items():require(cfg[key]==value,"unchanged V3 initialization: "+key)
        fs=next(x for x in fsummary["sequences"] if x["sequence_id"]==sid)
        require(fs["full_window_s"]==WINDOWS[sid] and fs["working_point_sigma_m"]==.01 and
                fs["source_time_replay_assumption"] and not fs["point_covariance_is_calibrated"] and
                not fs["imu_independence_proven"],"foot working source contract")
        event=pin(check({"path":str(foot/(sid+"_EVENTS.csv")),"sha256":terminal["files"][sid+"_EVENTS.csv"]}))
        audit=foot_audit(event["path"],WINDOWS[sid],fs);inputs[event["path"]]=event
        pair=[]
        for arm in ARMS:
            rid=sid+"__"+arm;out=stage/"NATIVE"/rid
            fields={"stage_id":reg["stage_id"],"protocol_id":reg["protocol_id"],"case_id":rid,"run_id":rid,
                "run_label":rid,"outputpath":str(out),"attitude_clone_mode":arm,"foot_pair_events_path":event["path"],
                "foot_pair_position_source_id":"SDK_FOOT_BODY_PROXY_NOT_ENCODER_FK:"+sid,
                "foot_pair_position_gnss_input_status":"unknown",
                "foot_pair_covariance_source_id":"ENGINEERING_POINT_SIGMA_0_01M_ARBITRARY_FOUR_POINT_CROSS_BOUND",
                "foot_pair_covariance_assumption":"Sigma6 upper bound 8 sigma squared I6; sigma 0.01m; uncalibrated zero mean working model",
                "foot_pair_frame_source_id":"SDK_FLU_TO_FRD_THEN_ENGINE_BODY_IDENTITY_UNCALIBRATED",
                "foot_pair_body_frd_to_engine_body":[1,0,0,0,1,0,0,0,1],
                "foot_pair_availability_policy":"source_time_replay_assumption"}
            modified,changes=clone(payload,fields);parsed=frozen._runtime_mapping(modified)
            require(untouched(payload,fields)==untouched(modified,fields),"untouched config line bytes changed")
            require({k:v for k,v in parsed.items() if k not in fields}=={k:v for k,v in cfg.items() if k not in fields},"unapproved config change")
            cp=stage/"CONFIGS"/(rid+".yaml");cp.parent.mkdir(exist_ok=True);cp.write_bytes(modified)
            cd=stage/"CHECKS"/rid;cd.mkdir(parents=True)
            call=[checker["path"],str(cp),str(cd/"ECHO")]
            emit(cd/"INVOCATION.json",{"argv":call,"solver_calls":0,"loader_only":True})
            cr=launch(call,cd,60);emit(cd/"RESULT.json",cr)
            require(cr["returncode"]==0 and not cr["timed_out"],"config checker failure: "+rid)
            echo=read(cd/"ECHO/RUN_MANIFEST.json")
            require(echo["attitude_clone_mode"]==arm and echo["attitude_clone_max_joint_dimension"]==24 and
                    echo["heading_source_policy"]=="pvt_priority_fallback","checker clone mode")
            runs.append({"run_id":rid,"sequence_id":sid,"arm":arm,"policy":"pvt_priority_fallback","config":pin(cp),
                "original_config":old["original_config"],"reused_fallback_config":old["config"],"changes":changes,
                "providers":old["providers"],"carrier":old["carrier"],"foot_events":event,"foot_audit":audit,
                "window":WINDOWS[sid],"checker_echo":pin(cd/"ECHO/RUN_MANIFEST.json")})
            pair.append(parsed);print("PREPARED",rid,flush=True)
        ignore={"run_id","run_label","case_id","outputpath","attitude_clone_mode"}
        require({k:v for k,v in pair[0].items() if k not in ignore}=={k:v for k,v in pair[1].items() if k not in ignore},"NULL/PAIR config mismatch")
    plan={"schema":"trusted_heading.clone_window_navigation.v1","registration_commit":a.registration_commit,
        "registered_plan_sha256":sha(ROOT/PLAN_REL),"source_pins":reg["source_pins"],"aliases":aliases,
        "binary":pin(binary),"static_library":pin(library),"checker":checker,"native_local_qualification":pin(qualification),
        "v3_lock":previous["v3_lock"],"evaluator":previous["evaluator"],"sequences":previous["sequences"],
        "reused_stage":str(baseline),"reused_stage_pins":oldpins,"foot_complete":pin(foot/"COMPLETE.json"),
        "foot_summary":pin(foot/"SUMMARY.json"),"foot_plan":pin(foot/"PLAN.json"),"runs":runs,"inputs":list(inputs.values()),
        "native_budget":6,"evaluator_budget":6,"historical_native_reused":6,"total_native_after_completion":12,
        "reference_parent_reads":0,"config_checker_calls":6}
    emit(stage/"PLAN.json",plan);emit(stage/"PREPARED.json",{"status":"PREPARED","plan_sha256":sha(stage/"PLAN.json")})

def checked_plan(a):
    registered(a.registration_commit);stage=Path(a.stage).resolve();plan=read(stage/"PLAN.json")
    require(plan["registration_commit"]==a.registration_commit and plan["registered_plan_sha256"]==sha(ROOT/PLAN_REL),"registration chain")
    require(read(stage/"PREPARED.json")["plan_sha256"]==sha(stage/"PLAN.json"),"prepared plan hash")
    require(tuple(x["run_id"] for x in plan["runs"])==IDS,"six clone identities")
    for rel,h in plan["source_pins"].items():check({"path":str(ROOT/rel),"sha256":h})
    for p in [plan["binary"],plan["evaluator"],plan["v3_lock"],plan["native_local_qualification"],
              plan["foot_complete"],plan["foot_summary"],plan["foot_plan"],*plan["reused_stage_pins"].values(),
              *plan["inputs"],*(x["config"] for x in plan["runs"])]:check(p)
    return stage,plan

def clone_diagnostics(out,run,manifest):
    with (out/"ATTITUDE_CLONE_EVENTS.csv").open(newline="") as f:rows=list(csv.DictReader(f))
    expected=run["foot_audit"]["rows"]
    require(len(rows)==expected==manifest["attitude_clone_source_rows"],"all source event rows must be accounted for")
    actions=Counter(x["action"] for x in rows);updates=sum(x["updated"]=="1" for x in rows)
    require(updates==manifest["attitude_clone_pair_updates"],"pair update count mismatch")
    for row in rows:
        t=float(row["event_time_s"]);state=float(row["state_time_s"])
        require(math.isfinite(t) and math.isfinite(state),"event diagnostic time")
        if not row["action"].startswith("UNCONSUMED_"):require(t==state,"consumed foot not bound to actual state time")
        if row["event_type"]=="RETIRE":require(row["source_time_s"]=="","RETIRE invented source")
        else:require(float(row["source_time_s"])==t,"foot source changed")
    with (out/"ATTITUDE_CLONE_FIXED_WEIGHTS.csv").open(newline="") as f:weights=list(csv.DictReader(f))
    require(len(weights)==21 and [int(x["current_error_coordinate"]) for x in weights]==list(range(21)),"fixed W coverage")
    require(all(math.isfinite(float(x["initial_block_inverse_mean_variance_weight"])) and
                float(x["initial_block_inverse_mean_variance_weight"])>=0 for x in weights),"fixed W finite")
    if run["arm"]=="NULL_CLONE":require(updates==0,"NULL performed pair update")
    return {"rows":len(rows),"actions":dict(actions),"pair_updates":updates,
            "events":pin(out/"ATTITUDE_CLONE_EVENTS.csv"),"fixed_weights":pin(out/"ATTITUDE_CLONE_FIXED_WEIGHTS.csv"),
            "working_model_only":True,"unconsumed_preserved":True}

def native(a):
    import numpy as np
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    stage,plan=checked_plan(a);records=[]
    require(not (stage/"NATIVE").exists(),"native already started: no retry")
    for run in plan["runs"]:
        rid=run["run_id"];out=stage/"NATIVE"/rid;out.mkdir(parents=True)
        reservation=reserve(stage,"native",rid)
        argv=["strace","-f","-yy","-s","4096","-e","trace=openat,execve","-o",str(out/"OPENAT.strace"),
              plan["binary"]["path"],"--config",run["config"]["path"],"--output-dir",str(out)]
        emit(out/"INVOCATION.json",{"argv":argv,"reservation":reservation,"plan_sha256":sha(stage/"PLAN.json")})
        rec={k:run[k] for k in ("run_id","sequence_id","arm")}
        try:
            rec.update(launch(argv,out,1200))
            # Pure legacy access checker: add the explicit optional input role locally only.
            audit_run={**run,"providers":{**run["providers"],"foot_pair_events_path":run["foot_events"]}}
            rec["access_audit"]=legacy.native_access(out/"OPENAT.strace",plan,audit_run,out)
            require(rec["access_audit"]["passed"],"native passive I/O audit")
            require(rec["returncode"]==0 and not rec["timed_out"],"native technical failure: no retry")
            manifest=read(out/"RUN_MANIFEST.json");echo=read(check(run["checker_echo"]))
            keys=("run_id","stage_id","protocol_id","case_id","algorithm_id","data_mode","runtime_contract",
                  "heading_source_policy","dual_yaw_prediction_model","actual_solver_input_paths","actual_solver_input_roles",
                  "heading_pvt_freshness_s","heading_accepted_cross_source_exclusion_s",
                  "attitude_clone_mode","attitude_clone_max_joint_dimension","attitude_clone_output_current_dimension",
                  "attitude_clone_reset","foot_pair_Young_epsilon_candidates","foot_pair_Young_selection",
                  "foot_pair_body_frd_to_engine_body","foot_pair_safe_innovation_threshold",
                  "foot_pair_position_source_id","foot_pair_position_gnss_input_status",
                  "foot_pair_covariance_source_id","foot_pair_covariance_assumption","foot_pair_availability_policy")
            for key in keys:require(key in manifest and manifest[key]==echo[key],"runtime static echo mismatch: "+key)
            foot=clone_diagnostics(out,run,manifest)
            nav=pin(out/"KF_GINS_Navresult.nav");std=pin(out/"KF_GINS_STD.txt")
            numeric,_=frozen.read_native_numeric(nav["path"],columns=11);st,_=frozen.read_native_numeric(std["path"])
            frozen._support(numeric,run["window"])
            require(st.ndim==2 and st.shape[1]>=10 and len(st)==len(numeric) and np.isfinite(st).all(),"STD shape/finite/coverage")
            require(np.array_equal(st[:,0],numeric[:,1]),"NAV/STD exact time keys")
            bound=frozen.bounded_lla_native(nav["path"],expected_sha256=nav["sha256"])
            rec.update(status="COMPLETED" if bound["passed"] else "ALGORITHM_FAILURE_DIVERGED",
                nav=nav,std=std,bound=bound,output_rows=len(numeric),first_time=float(numeric[0,1]),last_time=float(numeric[-1,1]),
                time_keys_sha256=hashlib.sha256(np.asarray(numeric[:,1],dtype="<f8").tobytes()).hexdigest(),
                time_key_encoding="little-endian float64 C-order bytes",foot_diagnostics=foot,
                clone_counts={k:v for k,v in manifest.items() if k.startswith("attitude_clone_") and isinstance(v,int)},
                heading_counts={k:v for k,v in manifest.items() if k.startswith("heading_") and k.endswith("_count")},
                manifest=pin(out/"RUN_MANIFEST.json"),heading_events=pin(out/"HEADING_SOURCE_EVENTS.csv"))
            emit(out/"RESULT.json",rec);records.append(rec)
        except BaseException as exc:
            rec.update(status="FAILED_TECHNICAL",error=repr(exc),traceback=traceback.format_exc())
            emit(out/"FAILED.json",rec);raise
        print("NATIVE",rid,rec["status"],flush=True)
    support={}
    for sid in SEQUENCES:
        null,pair=[x for x in records if x["sequence_id"]==sid]
        require(null["arm"]=="NULL_CLONE" and pair["arm"]=="PAIR_YOUNG","paired identity order")
        require(null["time_keys_sha256"]==pair["time_keys_sha256"],"paired output support differs")
        same_nav=null["nav"]["sha256"]==pair["nav"]["sha256"];same_std=null["std"]["sha256"]==pair["std"]["sha256"]
        zero=pair["foot_diagnostics"]["pair_updates"]==0
        require(null["foot_diagnostics"]["fixed_weights"]["sha256"]==pair["foot_diagnostics"]["fixed_weights"]["sha256"],"paired fixed W differs")
        support[sid]={"same_time_keys":True,"nav_byte_equal":same_nav,"std_byte_equal":same_std,
                      "pair_updates":pair["foot_diagnostics"]["pair_updates"],"zero_update_identity_required":zero,
                      "zero_update_identity_passed":(same_nav and same_std) if zero else None}
        if zero:require(same_nav and same_std,"PAIR had no updates yet differs from NULL")
    emit(stage/"ALL_NATIVE_SEALED.json",{"status":"SEALED","plan_sha256":sha(stage/"PLAN.json"),"solver_calls":6,
        "historical_native_reused":6,"total_native":12,"records":records,"paired_support":support,
        "reference_reads":0,"files":seal_files(stage/"NATIVE",stage)})

def evaluate(a):
    import numpy as np
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    from legsa_gins.paper_rebuild.protocol_v3.evaluation_process import evaluate as evaluator
    stage,plan=checked_plan(a);seal=read(stage/"ALL_NATIVE_SEALED.json")
    require(seal["status"]=="SEALED" and seal["plan_sha256"]==sha(stage/"PLAN.json") and
            tuple(r["run_id"] for r in seal["records"])==IDS,"all six native outputs must be sealed")
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
    emit(stage/"EVALUATION_COMPLETE.json",{"status":"COMPLETE","evaluator_calls":calls,"registered_run_count":6,
        "plan_sha256":sha(stage/"PLAN.json"),"native_seal_sha256":sha(stage/"ALL_NATIVE_SEALED.json"),
        "records":records,"files":seal_files(stage/"EVALUATION",stage),
        "reference_parent_reads":0,"reference":"shared GNSS commercial reference, not independent truth"})

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","native","evaluate"))
    p.add_argument("--stage",type=Path,required=True);p.add_argument("--registration-commit",required=True)
    p.add_argument("--baseline-stage",type=Path);p.add_argument("--foot-provider",type=Path)
    a=p.parse_args()
    if a.command=="prepare":require(a.baseline_stage and a.foot_provider,"prepare requires sealed baseline/foot provider")
    try:globals()[a.command](a)
    except BaseException as exc:
        if a.stage.exists() and not (a.stage/(a.command.upper()+"_FAILED.json")).exists():
            emit(a.stage/(a.command.upper()+"_FAILED.json"),{"error":repr(exc),"traceback":traceback.format_exc(),"retry":0})
        raise
if __name__=="__main__":main()
