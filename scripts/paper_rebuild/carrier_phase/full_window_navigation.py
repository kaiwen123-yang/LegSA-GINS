#!/usr/bin/env python3
"""Original V3 full-window PVT control/fallback transport, no automatic execution.

prepare: identity/CSV checks and six loader-only checks; native: six guarded,
passively audited solver slots; evaluate: only after all six native outputs
are sealed. No raw/reference payload is read by this controller.
"""
from __future__ import annotations
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"src"))
PLAN_REL="docs/paper_rebuild/TRUSTED_HEADING_20261006/FULL_WINDOW_NAVIGATION_PLAN.json"
MAP_REL="docs/paper_rebuild/TRUSTED_HEADING_20261006/FULL_WINDOW_NAV_INPUT_MAP.json"
LOCK_REL="docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
SEQUENCES=("BY2","BY2H","BY2O")
ARMS={"PVT_CONTROL":"pvt_priority_control","CARRIER_FALLBACK":"pvt_priority_fallback"}
IDS=tuple(s+"__"+arm for s in SEQUENCES for arm in ARMS)
COLUMNS=("measurement_time,decision_available_time,b_ecef_x,b_ecef_y,b_ecef_z,"
         "cov_xx,cov_xy,cov_xz,cov_yx,cov_yy,cov_yz,cov_zx,cov_zy,cov_zz,valid").split(",")
CHECKER=r"""
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include <iostream>
int main(int argc,char**argv) {
 if(argc!=3)return 2;
 try {
  auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);
  legsa_v23_port_core::FileSaver::writeRunManifest(argv[2],o);
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
"""

def require(ok,msg):
    if not ok:raise RuntimeError(msg)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda:f.read(1024*1024),b""):h.update(data)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if hasattr(v,"item"):return clean(v.item())
    return v

def emit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:
        json.dump(clean(value),f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
        f.flush();os.fsync(f.fileno())

def pin(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink(),"regular nonsymlink file required: "+str(path))
    return {"path":str(path),"sha256":sha(path),"size_bytes":path.stat().st_size}

def check(item):
    p=Path(item["path"])
    require(p.is_file() and not p.is_symlink(),"missing/symlink pin: "+str(p))
    require("size_bytes" not in item or p.stat().st_size==item["size_bytes"],"size mismatch: "+str(p))
    require(sha(p)==item["sha256"],"hash mismatch: "+str(p))
    return p

def expand(s,aliases):
    for k,v in aliases.items():s=s.replace(k,v)
    require("<" not in s and ">" not in s,"unresolved path alias")
    return Path(s)

def registered(commit):
    p=read(ROOT/PLAN_REL)
    require(p["status"]=="REGISTERED_READY","navigation plan is still a draft")
    for rel in [PLAN_REL,"scripts/paper_rebuild/carrier_phase/full_window_navigation.py"]:
        saved=subprocess.run(["git","show",commit+":"+rel],cwd=ROOT,check=True,capture_output=True).stdout
        require(saved==(ROOT/rel).read_bytes(),"registration payload differs: "+rel)
    for rel,h in p["source_pins"].items():check({"path":str(ROOT/rel),"sha256":h})
    return p

def clone(payload,fields):
    result=payload;changes=[]
    for key,value in fields.items():
        rx=re.compile(rb"(?m)^([ \t]*"+re.escape(key.encode())+rb"[ \t]*:[ \t]*)([^\r\n]*)(\r?\n|$)")
        found=list(rx.finditer(result));require(len(found)<=1,"duplicate config key: "+key)
        token=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        if found:
            m=found[0];before=m.group(2).decode()
            result=result[:m.start(2)]+token+result[m.end(2):]
        else:
            before=None;result+=(b"" if result.endswith(b"\n") else b"\n")+key.encode()+b": "+token+b"\n"
        changes.append({"key":key,"before":before,"after":value})
    return result,changes

def carrier_audit(path,window,expected_rows,expected_valid):
    import numpy as np
    with Path(path).open(newline="") as f:
        rd=csv.DictReader(f);require(rd.fieldnames==COLUMNS,"carrier15 columns");rows=list(rd)
    times=[];valid=0
    for row in rows:
        require(None not in row,"extra carrier column")
        t=float(row[COLUMNS[0]]);a=float(row[COLUMNS[1]])
        require(np.isfinite([t,a]).all() and t==a and window[0]<=t<=window[1],"carrier availability/window")
        times.append(t);require(row["valid"] in ("0","1"),"carrier validity")
        if row["valid"]=="1":
            v=np.array([float(row[k]) for k in COLUMNS[2:5]])
            q=np.array([float(row[k]) for k in COLUMNS[5:14]]).reshape(3,3)
            require(np.isfinite(v).all() and np.linalg.norm(v)>0 and np.isfinite(q).all(),"finite carrier vector/Q")
            require(np.allclose(q,q.T,rtol=0,atol=1e-12) and np.linalg.eigvalsh(q).min()>0,"carrier SPD")
            valid+=1
    require(len(rows)==expected_rows and valid==expected_valid,"sealed carrier summary counts")
    require(len(times)>0 and np.all(np.diff(times)>0),"carrier strictly ordered complete rows")
    return {"rows":len(rows),"valid":valid,"invalid":len(rows)-valid,
            "first_time":times[0],"last_time":times[-1],"all_invalid_retained":True}

def launch(argv,output,timeout,cwd=ROOT):
    output=Path(output);start=time.monotonic()
    with (output/"stdout.log").open("xb") as out,(output/"stderr.log").open("xb") as err:
        p=subprocess.Popen(argv,cwd=cwd,stdout=out,stderr=err,start_new_session=True)
        try:rc=p.wait(timeout=timeout);timed_out=False
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);rc=p.wait();timed_out=True
    return {"returncode":rc,"timed_out":timed_out,"wall_s":time.monotonic()-start}

def reserve(stage,kind,run_id):
    require(kind in ("native","evaluator") and run_id in IDS,"unregistered invocation")
    p=stage/(kind.upper()+"_LEDGER.jsonl")
    with p.open("a+") as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX);f.seek(0)
        rows=[json.loads(x) for x in f if x.strip()]
        require(len(rows)<6 and all(x["run_id"]!=run_id for x in rows),"budget/duplicate reservation; no retry")
        row={"kind":kind,"run_id":run_id,"ordinal":len(rows)+1,"budget":6,"reserved_unix":time.time(),"retry":0}
        f.write(json.dumps(row)+"\n");f.flush();os.fsync(f.fileno())
    return row

def seal_files(directory,relative_to):
    return {str(p.relative_to(relative_to)):sha(p) for p in sorted(directory.rglob("*")) if p.is_file()}

def prepare(a):
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    plan=registered(a.registration_commit)
    aliases=read(a.local_paths)["aliases"];require(Path(aliases["<CODE_ROOT>"])==ROOT,"code root alias")
    mapping=read(check({"path":str(ROOT/MAP_REL),"sha256":plan["input_map_sha256"]}))
    lock=read(check({"path":str(ROOT/LOCK_REL),"sha256":plan["v3_lock_sha256"]}))
    require({s["sequence_id"] for s in mapping["sequences"]}==set(SEQUENCES),"three original sequences")
    require(plan["frontend_complete_sha256"],"frontend terminal pin must be registered")
    frontend=Path(a.frontend).resolve();require(not (frontend/"FAILED.json").exists(),"frontend failure retained")
    terminal=read(check({"path":str(frontend/"COMPLETE.json"),"sha256":plan["frontend_complete_sha256"]}))
    require(terminal["status"]=="TERMINAL_ALL_FULL_WINDOW_ROWS","all frontend slots required")
    summary=read(check({"path":str(frontend/"SUMMARY.json"),"sha256":terminal["summary_sha256"]}))
    require(summary["status"] in ("COMPLETE","PARTIAL_PROCESSING_LIMIT"),"frontend terminal classification")
    require(summary["reference_reads"]==summary["navigation_calls"]==0,"frontend input role")
    require(set(terminal["sequence_seals"])==set(SEQUENCES),"frontend sequence coverage")
    stage=Path(a.stage).resolve();stage.mkdir(parents=True,exist_ok=False)
    emit(stage/"REGISTERED_PLAN.json",plan)
    binary=check({"path":str(expand(plan["binary"]["path"],aliases)),"sha256":plan["binary"]["sha256"]})
    library=check({"path":str(expand(plan["static_library"]["path"],aliases)),"sha256":plan["static_library"]["sha256"]})
    # This checker loads configuration only: no GIEngine propagation or input provider loading.
    build=stage/"CONFIG_CHECKER";build.mkdir()
    source=build/"config_check.cpp";source.write_text(CHECKER)
    argv=["c++","-std=c++17","-O2","-I",str(ROOT/"cpp/legsa_v23_port_core/include"),str(source),str(library),"-o",str(build/"config_check")]
    emit(build/"COMPILE_INVOCATION.json",{"argv":argv,"static_library":pin(library),"algorithm_calls":0})
    result=launch(argv,build,120);emit(build/"COMPILE_RESULT.json",result)
    require(result["returncode"]==0 and not result["timed_out"],"config checker compilation failed")
    checker=pin(build/"config_check");runs=[];inputs={};sequences=[]
    for sid in SEQUENCES:
        seq=next(s for s in mapping["sequences"] if s["sequence_id"]==sid)
        locked=next(s for s in lock["sequences"] if s["sequence_id"]==sid)
        require(seq["configuration"]["sha256"]==locked["configuration"]["sha256"] and
                seq["full_window_s"]==locked["full_window_s"] and
                set(seq["runtime_provider_pins"])==set(locked["runtime_provider_pins"]),
                "map/lock source identity")
        for key,item in locked["runtime_provider_pins"].items():
            require(all(seq["runtime_provider_pins"][key][k]==item[k] for k in ("path","sha256","size_bytes")),
                    "map/lock provider identity: "+key)
        require(seq["evaluation"]["baseline_median_m"]==locked["evaluation"]["baseline_median_m"] and
                seq["base_time_unix_s"]==locked["base_time_unix_s"],"map/lock evaluation physical/time contract")
        original=check({**seq["configuration"],"path":str(expand(seq["configuration"]["path"],aliases))})
        original_bytes=original.read_bytes();cfg=frozen._runtime_mapping(original_bytes)
        require(cfg["imudatalen"]==7 and cfg["imudatarate"]==500,"original seven-column 500Hz IMU")
        require([cfg["starttime"],cfg["endtime"]]==seq["full_window_s"],"original full window")
        resolved_model=cfg.get("dual_yaw_prediction_model","legacy")
        if resolved_model=="legacy":
            resolved_model="lateral_projection" if cfg["stage_id"]=="IMU_V3_TIME_CONTRACT_FIX_20261004" else "euler_yaw"
        require(resolved_model==plan["scalar_model_by_sequence"][sid],"original scalar route mismatch")
        providers={}
        for key,item in seq["runtime_provider_pins"].items():
            path=check({**item,"path":str(expand(item["path"],aliases))})
            require(cfg[key]==str(path),"original provider path changed: "+key)
            providers[key]=pin(path);inputs[str(path)]=providers[key]
        seal_path=frontend/sid/"OUTPUT_SEAL.json"
        seqseal=read(check({"path":str(seal_path),"sha256":terminal["sequence_seals"][sid]}))
        sidecar=check({"path":str(frontend/sid/"CARRIER.csv"),"sha256":seqseal["CARRIER.csv"]})
        seqsummary=read(check({"path":str(frontend/sid/"SUMMARY.json"),"sha256":seqseal["SUMMARY.json"]}))
        require(seqsummary["sequence"]==sid and seqsummary["window_s"]==seq["full_window_s"],"carrier sequence window")
        audit=carrier_audit(sidecar,seq["full_window_s"],seqsummary["rows"],seqsummary["valid_research_points"])
        inputs[str(sidecar)]=pin(sidecar)
        two=[]
        for arm,policy in ARMS.items():
            rid=sid+"__"+arm;out=stage/"NATIVE"/rid
            fields={"runtime_contract":"research_experiment","stage_id":plan["stage_id"],"protocol_id":plan["protocol_id"],
                    "case_id":rid,"run_id":rid,"run_label":rid,"outputpath":str(out),
                    "heading_source_policy":policy,"dual_antenna_measurement_model":"baseline3d",
                    "baseline3d_source":"external_carrier","external_carrier_baseline_path":str(sidecar),
                    "baseline3d_body_vector_m":[0,-.35,0],"dual_yaw_prediction_model":resolved_model}
            cloned,changes=clone(original_bytes,fields);new=frozen._runtime_mapping(cloned)
            require({k:v for k,v in new.items() if k not in fields}=={k:v for k,v in cfg.items() if k not in fields},"unapproved nonheading config edit")
            # Removing edited complete lines leaves every other original byte unchanged.
            def untouched(payload):
                return b"".join(line for line in payload.splitlines(keepends=True)
                    if not any(re.match(rb"^[ \t]*"+k.encode()+rb"[ \t]*:",line) for k in fields))
            require(untouched(cloned)==untouched(original_bytes),"unmodified config line bytes changed")
            cpath=stage/"CONFIGS"/(rid+".yaml");cpath.parent.mkdir(exist_ok=True);cpath.write_bytes(cloned)
            cdir=stage/"CHECKS"/rid;cdir.mkdir(parents=True)
            call=[checker["path"],str(cpath),str(cdir/"ECHO")]
            emit(cdir/"INVOCATION.json",{"argv":call,"solver_calls":0,"loader_only":True})
            result=launch(call,cdir,60);emit(cdir/"RESULT.json",result)
            require(result["returncode"]==0 and not result["timed_out"],"configuration checker failed: "+rid)
            record={"run_id":rid,"sequence_id":sid,"arm":arm,"policy":policy,"config":pin(cpath),
                    "original_config":pin(original),"changes":changes,"providers":providers,
                    "carrier":pin(sidecar),"carrier_audit":audit,"window":seq["full_window_s"],
                    "checker_echo":pin(cdir/"ECHO/RUN_MANIFEST.json")}
            runs.append(record);two.append(new)
            print("PREPARED",rid,flush=True)
        ignore={"run_id","run_label","case_id","outputpath","heading_source_policy"}
        require({k:v for k,v in two[0].items() if k not in ignore}=={k:v for k,v in two[1].items() if k not in ignore},"paired arm config inequality")
        seq["evaluation"]["reference_identity_from_lock_only"]=locked["evaluation"]["reference"]
        seq["reference"]= {**locked["evaluation"]["reference"],"path":str(expand(locked["evaluation"]["reference"]["path"],aliases))}
        sequences.append(seq)
    evaluator=pin(check({**mapping["frozen_evaluator"],"path":str(expand(mapping["frozen_evaluator"]["path"],aliases))}))
    emitted={"schema":"trusted_heading.full_window_navigation.v1","registration_commit":a.registration_commit,
        "registered_plan_sha256":sha(ROOT/PLAN_REL),"source_pins":plan["source_pins"],
        "input_map":pin(ROOT/MAP_REL),"v3_lock":pin(ROOT/LOCK_REL),"local_paths":pin(a.local_paths),
        "aliases":aliases,"binary":pin(binary),"checker":checker,"evaluator":evaluator,
        "frontend_complete":pin(frontend/"COMPLETE.json"),"frontend_summary":pin(frontend/"SUMMARY.json"),
        "frontend_seals":{s:pin(frontend/s/"OUTPUT_SEAL.json") for s in SEQUENCES},
        "runs":runs,"sequences":sequences,"inputs":list(inputs.values()),"native_budget":6,"evaluator_budget":6,
        "reference_parent_reads":0,"config_checker_calls":6,"static_library":pin(library)}
    emit(stage/"PLAN.json",emitted);emit(stage/"PREPARED.json",{"status":"PREPARED","plan_sha256":sha(stage/"PLAN.json")})

def checked_plan(a):
    registered(a.registration_commit)
    stage=Path(a.stage).resolve();plan=read(stage/"PLAN.json")
    require(plan["registration_commit"]==a.registration_commit and plan["registered_plan_sha256"]==sha(ROOT/PLAN_REL),"registered plan chain")
    require(read(stage/"PREPARED.json")["plan_sha256"]==sha(stage/"PLAN.json"),"prepared plan hash")
    require(tuple(r["run_id"] for r in plan["runs"])==IDS,"six fixed identities")
    for rel,h in plan["source_pins"].items():check({"path":str(ROOT/rel),"sha256":h})
    for p in [plan["binary"],plan["evaluator"],plan["input_map"],plan["v3_lock"],plan["local_paths"],
              plan["frontend_complete"],plan["frontend_summary"],*plan["frontend_seals"].values(),
              *plan["inputs"],*(r["config"] for r in plan["runs"])]:check(p)
    return stage,plan

def native_access(log,plan,run,out):
    from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records,write_scope_audit
    records=audited_open_records(log,ROOT);raw=Path(plan["aliases"]["<RAW_ROOT>"])
    protected=[Path(plan["aliases"]["<CLEAN_ROOT>"]),Path(plan["aliases"]["<SCRATCH_ROOT>"])]
    expected={p["path"] for p in run["providers"].values()}|{run["carrier"]["path"]}
    allowed=expected|{run["config"]["path"],plan["binary"]["path"]}
    badraw=[r for r in records if raw in Path(r["path"]).parents or Path(r["path"])==raw]
    unexpected=[r for r in records if any(x in Path(r["path"]).parents for x in protected)
                and r["path"] not in allowed and out not in Path(r["path"]).parents and Path(r["path"])!=out]
    opened={r["path"] for r in records if r["return_code"]>=0 and "O_RDONLY" in r["flags"]}
    writes=write_scope_audit(records,raw_root=raw,clean_root=Path(plan["aliases"]["<CLEAN_ROOT>"]),allowed_write_roots=[out])
    executions=[x for x in Path(log).read_text().splitlines() if "execve(" in x]
    native=sum(plan["binary"]["path"] in x for x in executions)
    trace_paths={s["reference"]["path"] for s in plan["sequences"]}
    result={"passed":not badraw and not unexpected and expected<=opened and writes["pass"] and native==1,
        "raw_open_records":badraw,"online_reference_opens":sum(r["path"] in trace_paths for r in records),
        "unexpected_protected_opens":unexpected,"missing_inputs":sorted(expected-opened),
        "write_scope":writes,"native_exec_count":native,"strace_sha256":sha(log)}
    require(result["online_reference_opens"]==0,"native reference access violation")
    return result

def native(a):
    import numpy as np
    from legsa_gins.paper_rebuild.protocol_v3.runtime import frozen
    stage,plan=checked_plan(a);records=[]
    require(not (stage/"NATIVE").exists(),"native directory already exists: no retry")
    for run in plan["runs"]:
        rid=run["run_id"];out=stage/"NATIVE"/rid;out.mkdir(parents=True)
        reservation=reserve(stage,"native",rid)
        argv=["strace","-f","-yy","-s","4096","-e","trace=openat,execve","-o",str(out/"OPENAT.strace"),
              plan["binary"]["path"],"--config",run["config"]["path"],"--output-dir",str(out)]
        emit(out/"INVOCATION.json",{"argv":argv,"reservation":reservation,"plan_sha256":sha(stage/"PLAN.json")})
        rec={k:run[k] for k in ("run_id","sequence_id","arm")}
        try:
            rec.update(launch(argv,out,1200));rec["access_audit"]=native_access(out/"OPENAT.strace",plan,run,out)
            require(rec["access_audit"]["passed"],"native passive I/O audit")
            require(rec["returncode"]==0 and not rec["timed_out"],"native failure: retained without retry")
            manifest=read(out/"RUN_MANIFEST.json");echo=read(check(run["checker_echo"]))
            # Static identity/input/initialization fields are those emitted by same loader.
            for key in ("run_id","stage_id","protocol_id","case_id","algorithm_id","data_mode","runtime_contract",
                        "heading_source_policy","dual_yaw_prediction_model","actual_solver_input_paths","actual_solver_input_roles"):
                require(manifest.get(key)==echo.get(key),"runtime static echo mismatch: "+key)
            for key in ("heading_pvt_freshness_s","heading_accepted_cross_source_exclusion_s"):
                require(manifest[key]==echo[key],"heading engineering time contract changed")
            nav=pin(out/"KF_GINS_Navresult.nav");std=pin(out/"KF_GINS_STD.txt")
            numeric,_=frozen.read_native_numeric(nav["path"],columns=11)
            st,_=frozen.read_native_numeric(std["path"])
            frozen._support(numeric,run["window"])
            require(st.ndim==2 and st.shape[1]>=10,"STD must have at least 10 columns")
            require(len(numeric)==len(st) and np.isfinite(st).all(),"NAV/STD coverage or finite mismatch")
            require(np.array_equal(st[:,0],numeric[:,1]),"NAV/STD exact time-key mismatch")
            bound=frozen.bounded_lla_native(nav["path"],expected_sha256=nav["sha256"])
            rec.update(status="COMPLETED" if bound["passed"] else "ALGORITHM_FAILURE_DIVERGED",
                nav=nav,std=std,bound=bound,output_rows=len(numeric),first_time=float(numeric[0,1]),
                last_time=float(numeric[-1,1]),time_keys_sha256=hashlib.sha256(np.asarray(numeric[:,1],dtype="<f8").tobytes()).hexdigest(),
                time_key_encoding="little-endian float64 C-order bytes",
                heading_counts={k:v for k,v in manifest.items() if k.startswith("heading_") and k.endswith("_count")},
                manifest=pin(out/"RUN_MANIFEST.json"),heading_events=pin(out/"HEADING_SOURCE_EVENTS.csv"))
            if run["arm"]=="PVT_CONTROL":require(manifest["heading_carrier_attempt_count"]==0,"control attempted carrier")
            emit(out/"RESULT.json",rec);records.append(rec)
        except BaseException as exc:
            rec.update(status="FAILED_TECHNICAL",error=repr(exc),traceback=traceback.format_exc())
            emit(out/"FAILED.json",rec);raise
        print("NATIVE",rid,rec["status"],flush=True)
    support={}
    for sid in SEQUENCES:
        pair=[r for r in records if r["sequence_id"]==sid]
        require(len({x["time_keys_sha256"] for x in pair})==1,"paired NAV time support differs: "+sid)
        support[sid]={"same_time_keys":True,"nav_byte_equal":pair[0]["nav"]["sha256"]==pair[1]["nav"]["sha256"],
                      "std_byte_equal":pair[0]["std"]["sha256"]==pair[1]["std"]["sha256"]}
        if sid in ("BY2","BY2H"):
            require(support[sid]["nav_byte_equal"] and support[sid]["std_byte_equal"],"all-PVT-valid control/fallback inequality: "+sid)
    emit(stage/"ALL_NATIVE_SEALED.json",{"status":"SEALED","plan_sha256":sha(stage/"PLAN.json"),"solver_calls":6,
         "records":records,"paired_support":support,"reference_reads":0,"files":seal_files(stage/"NATIVE",stage)})

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
    p.add_argument("--local-paths",type=Path);p.add_argument("--frontend",type=Path)
    a=p.parse_args()
    if a.command=="prepare":require(a.local_paths and a.frontend,"prepare requires --local-paths and --frontend")
    try:globals()[a.command](a)
    except BaseException as exc:
        if a.stage.exists():
            name=a.command.upper()+"_FAILED.json"
            if not (a.stage/name).exists():
                emit(a.stage/name,{"error":repr(exc),"traceback":traceback.format_exc(),"retry":0})
        raise
if __name__=="__main__":main()
