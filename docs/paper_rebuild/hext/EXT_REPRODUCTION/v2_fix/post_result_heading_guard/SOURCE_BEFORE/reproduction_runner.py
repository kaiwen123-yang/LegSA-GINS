"""One explicit EXT method/sequence run. No controller, reference, or resume path."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
from dataclasses import fields, is_dataclass
import gzip
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import subprocess
import time
import csv

import numpy as np
from . import shared_raw_backend as raw
from . import reproduction_backend as backend
from . import ext01_clambda as cl
from . import ext02_cwls as cw
from .phase2_runner import CompactCacheReader, validate_compact_cache
from .phase3_runner import _ecef_vector_to_ned
from .reproduction_prepare import aliases, expand, write_json, digest, LIBRARY_PINS

def jsonable(value):
    if is_dataclass(value): return {f.name:jsonable(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value, dict): return {(raw.identity_text(k) if isinstance(k,raw.SignalIdentity) else str(k)):jsonable(v) for k,v in value.items()}
    if isinstance(value,(set,frozenset)): return sorted((jsonable(x) for x in value),key=str)
    if isinstance(value,(list,tuple)): return [jsonable(x) for x in value]
    if isinstance(value,np.ndarray): return jsonable(value.tolist())
    if isinstance(value,np.generic): return jsonable(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value

class CountedProvider(raw.RtklibBroadcastProvider):
    def __init__(self,*args):
        self.state_calls=0;self.spp_calls=0
        super().__init__(*args)
    def state(self,*args,**kwargs):
        self.state_calls+=1
        return super().state(*args,**kwargs)
    def pntpos_rawx_epoch(self,*args,**kwargs):
        self.spp_calls+=1
        return super().pntpos_rawx_epoch(*args,**kwargs)

_reader=None
_provider=None
_positions=None
_config=None
_method=None
_lambda=None

def initialize(cache, bridge, nav, positions, config, method, library):
    global _reader,_provider,_positions,_config,_method,_lambda
    _reader=CompactCacheReader(Path(cache));_provider=CountedProvider(Path(bridge),[Path(x) for x in nav])
    _positions=positions;_config=config;_method=method;_lambda=library

def solve_independent(index):
    first,second=_reader.pair(index)
    started=time.monotonic();before=_provider.state_calls
    result={"epoch_index":index,"gps_week":first.gps_week,"gps_tow_seconds":first.gps_tow_seconds,
            "time_unix_s":315964800.+first.gps_week*604800.+first.gps_tow_seconds-first.leap_seconds,
            "method":_method,"valid":False,"solution_state":"INVALID","failure_code":None,
            "body_yaw_deg":None,"baseline_ned_m":None,"baseline_ecef_m":None,
            "float_solved":None if _method=="EXT02" else False,"search_attempted":False,"search_complete":False,
            "candidate_returned":False,"acceptance_test_defined":False,"ratio_fixed":None,
            "ambiguity_correctness_known":False,"accounting":raw.gps_l1_epoch_accounting(first,second).as_counts()}
    try:
        spp=_positions[index]
        if spp["position"] is None:
            raise raw.DoubleDifferenceStageError("SPP_POSITION_UNAVAILABLE",spp["failure"],None)
        position=np.asarray(spp["position"])
        model,geometry=backend.build_gps_l1_model(first,second,_provider,position)
        result.update(accounting=model.accounting.as_counts(),geometry=geometry,model=jsonable(model),spp=spp)
        count=len(model.satellites)
        if _method=="EXT01":
            result["search_attempted"]=True
            settings=_config["EXT01"]
            solved=cl.solve_clambda(model.observation_m,model.ambiguity_design_m,model.baseline_design,
                model.covariance_m2,length_m=_config["baseline_length_m"],lambda_bridge_path=_lambda,
                strict=True,initial_candidate_count=settings["lambda_seed_count"],
                strict_node_limit=settings["node_limit"],timeout_seconds=settings["wall_budget_seconds"])
            result.update(float_solved=True,search_complete=bool(solved.global_optimum_certified),
                          candidate_returned=solved.best is not None,solver=jsonable(solved))
            if not solved.global_optimum_certified or solved.best is None:
                result["failure_code"]=solved.failure_code or solved.termination_reason
            else:
                baseline=solved.best.baseline
                result.update(valid=True,solution_state="CERTIFIED_INTEGER_CANDIDATE",
                              ambiguity=solved.best.ambiguity.tolist(),objective=solved.best.objective)
        else:
            from .reproduction_ext02 import solve_cwls
            cm=cw.adapt_metric_double_differences(code_m=model.observation_m[:count],
                phase_m=model.observation_m[count:],design_m_per_m=model.baseline_design,
                covariance_code_phase_m2=model.covariance_m2,
                wavelength_m=raw.wavelength_m(model.pivot),baseline_length_m=_config["baseline_length_m"])
            result["search_attempted"]=True
            solved=solve_cwls(cm)
            # Retain every candidate's terminal objective/status; dense iteration
            # histories are not duplicated in the public heading table.
            solver=jsonable(solved)
            solver["diagnostics"]=[{k:v for k,v in d.items() if k!="iterations"}
                                   for d in solver["diagnostics"]]
            result.update(valid=True,solution_state="WRAPPED_CANDIDATE",search_complete=True,
                          candidate_returned=True,solver=solver,ambiguity=list(solved.integer_ambiguities),
                          objective=solved.objective)
            baseline=solved.baseline_vector_m
        if result["valid"]:
            ned=_ecef_vector_to_ned(baseline,position)
            result.update(baseline_ecef_m=baseline,baseline_ned_m=ned,baseline_length_m=np.linalg.norm(ned),
                          body_yaw_deg=cl.body_yaw_from_ned_baseline(ned))
    except (raw.RawBackendError,ValueError,np.linalg.LinAlgError) as exc:
        result["failure_code"]=getattr(exc,"code",type(exc).__name__)
        result["failure_detail"]=str(exc)
        for attribute in ("candidate_pool","candidate_diagnostics"):
            if hasattr(exc,attribute):result[attribute]=jsonable(getattr(exc,attribute))
        if getattr(exc,"accounting",None) is not None: result["accounting"]=exc.accounting.as_counts()
    result.update(elapsed_s=time.monotonic()-started,satellite_state_calls=_provider.state_calls-before)
    return jsonable(result)

def source_pins(repo):
    files=["shared_raw_backend.py","ext01_clambda.py","ext02_cwls.py","ext03_yang2024.py",
           "phase2_runner.py","phase3_runner.py","phase3_signal_inventory.py","sequence_override.py",
           "reproduction_backend.py","reproduction_ext02.py","reproduction_ext03.py",
           "reproduction_prepare.py","reproduction_runner.py"]
    prefix=Path("src/legsa_gins/paper_rebuild/horizontal_literature")
    return {str(prefix/name):digest((repo/prefix/name).read_bytes()) for name in files}

def reproduction_contract(config):
    """Choose an explicit version; old V1 never silently takes the SPP repair."""
    schema = config.get("schema")
    if schema == "ext_reproduction.config.v1":
        if "gps_l1_spp_earth_rotation_delay" in config:
            raise ValueError("V1 cannot redefine the frozen SPP Earth-rotation contract")
        return "V1", "legacy_raw_code"
    if schema == "ext_reproduction.config.v2":
        if config.get("gps_l1_spp_earth_rotation_delay") != "iterated_geometric":
            raise ValueError("V2 requires the physical SPP Earth-rotation delay")
        return "V2", "iterated_geometric"
    raise ValueError("unknown EXT reproduction configuration schema")


def prepare_spp_positions(reader, provider, earth_rotation_delay):
    """Keep every input index; a failed SPP is never a previous-position hold."""
    positions, previous = [], None
    for i in range(len(reader)):
        try:
            solved = raw.gps_l1_code_spp(reader.pair(i)[0], provider, previous,
                                        earth_rotation_delay=earth_rotation_delay)
            previous = solved.position_ecef_m
            positions.append({"position": previous.tolist(), "failure": None})
        except (raw.RawBackendError, ValueError, np.linalg.LinAlgError) as exc:
            positions.append({"position": None, "failure": str(exc)})
    return positions


def run(roots_path,config_path,sequence,method,attempt,*,allow_source_overlay=False):
    roots=aliases(roots_path);repo=Path(roots["<CODE_ROOT>"])
    config=json.loads(Path(config_path).read_text())
    version, spp_delay = reproduction_contract(config)
    if allow_source_overlay and version != "V2":
        raise ValueError("source overlay requires the explicit V2 reproduction contract")
    info=json.loads((Path(roots["<EXT_REPRO_ROOT>"])/f"inputs/{sequence}/INPUT.json").read_text())
    cache=expand(info["cache_root"],roots);nav=[expand(x,roots) for x in info["navigation"]]
    libroot=Path(roots["<EXT_REPRO_BUILD>"])/"lib"
    library=libroot/"librtklib_legsa.so";bridge=libroot/"liblegsa_rtklib_bridge.so"
    run_id=f"{sequence}__{method}__RAW_REPRO_{version}"+("" if attempt==1 else f"__TECH_RETRY_{attempt}")
    out=Path(roots["<EXT_REPRO_ROOT>"])/"runs"/run_id;out.mkdir(parents=True,exist_ok=False)
    reader=CompactCacheReader(cache);assert len(reader)==info["pair_count"]
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    pins=source_pins(repo)
    config_relative=str(Path(config_path).resolve().relative_to(repo))
    config_hash=digest(Path(config_path).read_bytes())
    if not allow_source_overlay:
        # Frozen V1 behaviour remains HEAD-pinned. V2 also defaults to this gate.
        for relative,value in pins.items():
            assert digest(subprocess.check_output(["git","show",f"{head}:{relative}"],cwd=repo))==value,relative
        assert digest(subprocess.check_output(["git","show",f"{head}:{config_relative}"],cwd=repo))==config_hash
    source_state=subprocess.check_output(
        ["git","status","--short","--untracked-files=all","--",*sorted(pins),config_relative],
        cwd=repo,text=True).splitlines()
    snapshot_hashes={}
    if version == "V2":
        # A reviewed worktree overlay is concrete immutable run evidence; HEAD
        # is recorded only as its base, never as the complete runtime identity.
        for relative,expected in {**pins,config_relative:config_hash}.items():
            payload=(repo/relative).read_bytes()
            assert digest(payload)==expected,relative
            snapshot=out/"SOURCE_SNAPSHOT"/relative
            snapshot.parent.mkdir(parents=True,exist_ok=True)
            snapshot.write_bytes(payload)
            snapshot_hashes[relative]=expected
    cache_receipt=validate_compact_cache(cache,source_fingerprint=info["cache"]["source_fingerprint"],expected_pair_count=info["pair_count"])
    for i,path in enumerate(nav,1):assert digest(path.read_bytes())==info["source_files"][f"gnss{i}.nav"]["sha256"]
    for name,expected in LIBRARY_PINS.items():assert digest((libroot/name).read_bytes())==expected
    assert config["baseline_length_m"]==.350
    if method=="EXT02":
        assert config["EXT02"]=={"delta_Delta":.05,"K":"all unique candidates","refinement_max_iterations":20,
          "direction_tolerance":1e-10,"any_candidate_failure":"whole epoch invalid",
          "round_boundary":"original half-down implementation and literal Eq75; edge caveat documented"}
    if method=="EXT03":
        from .reproduction_ext03 import CONFIG,SYSTEM_MODE
        assert config["EXT03"]["system_mode"]==SYSTEM_MODE
        assert config["EXT03"]["constraint_mode"]==CONFIG.constraint_mode
        assert config["EXT03"]["baseline_sigma_m"]==CONFIG.baseline_sigma_m
        assert config["EXT03"]["ratio_threshold"]==CONFIG.ratio_threshold
        from .ext03_yang2024 import INITIAL_BASELINE_VARIANCE_M2,INITIAL_AMBIGUITY_VARIANCE_CYCLES2
        assert config["EXT03"]["initial_baseline_variance_m2"]==INITIAL_BASELINE_VARIANCE_M2
        assert config["EXT03"]["initial_ambiguity_variance_cycles2"]==INITIAL_AMBIGUITY_VARIANCE_CYCLES2
    receipt={"run_id":run_id,"sequence":sequence,"method":method,"status":"RUNNING",
        "attempt":attempt,"start_unix":time.time(),"code_commit":head,"source_hashes":pins,
        "code_commit_role":"BASE_HEAD_ONLY" if allow_source_overlay else "HEAD_PINNED_RUNTIME_SOURCE",
        "source_overlay_explicitly_enabled":allow_source_overlay,"runtime_source_git_state":source_state,
        "source_snapshot_hashes":snapshot_hashes,"reproduction_version":version,
        "gps_l1_spp_earth_rotation_delay":spp_delay,
        "config_hash":digest(Path(config_path).read_bytes()),"config":config,
        "input_manifest":f"<EXT_REPRO_ROOT>/inputs/{sequence}/INPUT.json",
        "input_manifest_sha256":digest((Path(roots["<EXT_REPRO_ROOT>"])/f"inputs/{sequence}/INPUT.json").read_bytes()),
        "cache_manifest_sha256":digest((cache/"CACHE_MANIFEST.json").read_bytes()),
        "cache_files_verified":cache_receipt["files"],"library_hashes_verified":LIBRARY_PINS,
        "data_mode":"real_raw","synthetic_data_used":False,"semisynthetic_data_used":False,
        "trace_used_online":False,"receiver_imu_as_body_imu":False,"final_v23_output_solver_input":False,
        "LegSA_output_solver_input":False,"per_case_tuning":False,"output_only_correction":False,
        "epoch_deleted_for_metric":False,"old_runtime_input_count":0,
        "input_reuse_role":"verified raw-derived UBX/NAV; no prior estimate reused",
        "planned_paired_epochs":len(reader),"new_method_sequence_calls":1,"evaluator_calls":0}
    write_json(out/"RUN.json",receipt)
    rows=[];start=time.monotonic();spp_state_calls=0;spp_attempts=0
    output_fields=["epoch_index","gps_week","gps_tow_seconds","time_unix_s","valid","body_yaw_deg",
                   "solution_state","failure_code","float_solved","search_attempted","search_complete",
                   "candidate_returned","acceptance_test_defined","ratio_fixed","baseline_n_m","baseline_e_m",
                   "baseline_d_m","baseline_length_m","elapsed_s","satellite_state_calls"]
    def save_record(record,stream,writer):
        stream.write(json.dumps(jsonable(record),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
        item={k:record.get(k) for k in output_fields}
        for key in ("valid","float_solved","search_attempted","search_complete","candidate_returned","acceptance_test_defined"):
            item[key]=None if item[key] is None else int(bool(item[key]))
        if item["ratio_fixed"] is not None:item["ratio_fixed"]=int(item["ratio_fixed"])
        for i,key in enumerate(("baseline_n_m","baseline_e_m","baseline_d_m")):
            item[key]=None if record.get("baseline_ned_m") is None else record["baseline_ned_m"][i]
        writer.writerow(item);rows.append(item)
        if len(rows)%25==0 or len(rows)==len(reader):
            write_json(out/"PROGRESS.json",{"run_id":run_id,"completed_epochs":len(rows),"planned":len(reader),
                                          "valid":sum(x["valid"] for x in rows),"elapsed_s":time.monotonic()-start})
            print(json.dumps({"run":run_id,"done":len(rows),"valid":sum(x["valid"] for x in rows)}),flush=True)
    try:
        with gzip.open(out/"EPOCH_EVIDENCE.jsonl.gz","wt",encoding="utf-8",compresslevel=3) as stream, (out/"HEADING.csv").open('w',newline='') as table:
            writer=csv.DictWriter(table,output_fields,lineterminator='\n');writer.writeheader()
            if method in ("EXT01","EXT02"):
                with CountedProvider(bridge,nav) as provider:
                    positions=prepare_spp_positions(reader,provider,spp_delay)
                    spp_attempts=len(reader)
                    spp_state_calls=provider.state_calls
                write_json(out/"SPP.json",positions)
                with concurrent.futures.ProcessPoolExecutor(max_workers=config["workers_independent_epochs"],
                        mp_context=multiprocessing.get_context("spawn"),initializer=initialize,
                        initargs=(str(cache),str(bridge),[str(x) for x in nav],positions,config,method,str(library))) as executor:
                    for record in executor.map(solve_independent,range(len(reader)),chunksize=1):save_record(record,stream,writer)
            else:
                from .reproduction_ext03 import ReproductionEXT03Engine
                with CountedProvider(bridge,nav) as provider:
                    engine=ReproductionEXT03Engine(provider,library)
                    for i in range(len(reader)):
                        first,second=reader.pair(i);before=time.monotonic();before_calls=provider.state_calls;record=engine.step(first,second)
                        valid=bool(record["state_updated"])
                        stage=record["stage_evidence"]
                        record.update(time_unix_s=315964800.+first.gps_week*604800.+first.gps_tow_seconds-first.leap_seconds,
                            valid=valid,satellite_state_calls=provider.state_calls-before_calls,float_solved=stage["float_solution_returned"],
                            search_attempted=stage["mlambda_attempted"],search_complete=stage["mlambda_completed"],
                            candidate_returned=stage["two_candidates_returned"],acceptance_test_defined=True,ratio_fixed=record.get("paper_ratio_fixed",False),
                            elapsed_s=time.monotonic()-before)
                        save_record(record,stream,writer)
                    spp_attempts=provider.spp_calls;spp_state_calls=0
        receipt.update(status="COMPLETED",completed_epochs=len(rows),valid_epochs=sum(x["valid"] for x in rows),
            failure_counts=dict(collections.Counter(x["failure_code"] or x["solution_state"] for x in rows if not x["valid"])),
            state_counts=dict(collections.Counter(x["solution_state"] for x in rows)),
            float_solved_epochs=None if method=="EXT02" else sum(x["float_solved"]==1 for x in rows),
            float_stage_applicability="NOT_APPLICABLE_CWLS" if method=="EXT02" else "DEFINED",
            search_attempted_epochs=sum(x["search_attempted"]==1 for x in rows),
            search_complete_epochs=sum(x["search_complete"]==1 for x in rows),
            candidate_returned_epochs=sum(x["candidate_returned"]==1 for x in rows),
            unknown_stage_counts={k:(0 if k=="float_solved" and method=="EXT02" else sum(x[k] is None for x in rows)) for k in
                                  ("float_solved","search_attempted","search_complete","candidate_returned")},
            ratio_fixed_epochs=sum(bool(x["ratio_fixed"]) for x in rows),
            spp_attempts=spp_attempts,total_satellite_state_calls=spp_state_calls+sum(x["satellite_state_calls"] or 0 for x in rows),
            elapsed_s=time.monotonic()-start,end_unix=time.time())
        receipt["outputs"]={name:{"path":f"<EXT_REPRO_ROOT>/runs/{run_id}/{name}",
                                 "sha256":digest((out/name).read_bytes()),"bytes":(out/name).stat().st_size}
                            for name in ("HEADING.csv","EPOCH_EVIDENCE.jsonl.gz")}
        assert len(rows)==len(reader)
        assert source_pins(repo)==pins,"runtime scientific source changed during run"
        assert digest(Path(config_path).read_bytes())==config_hash,"configuration changed during run"
        for relative,expected in snapshot_hashes.items():
            assert digest((out/"SOURCE_SNAPSHOT"/relative).read_bytes())==expected,relative
        receipt["runtime_source_revalidated_after_run"]=True
    except Exception as exc:
        receipt.update(status="TECHNICAL_FAILURE",exception=repr(exc),completed_epochs=len(rows),end_unix=time.time())
        write_json(out/"RUN.json",receipt)
        raise
    write_json(out/"RUN.json",receipt)
    print(json.dumps({"run_id":run_id,"status":receipt["status"],"valid":receipt["valid_epochs"]}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--roots",required=True);p.add_argument("--config",required=True)
    p.add_argument("--sequence",choices=("BY2","BY2H","BY2O"),required=True)
    p.add_argument("--method",choices=("EXT01","EXT02","EXT03"),required=True);p.add_argument("--attempt",type=int,default=1)
    p.add_argument("--allow-source-overlay",action="store_true",help="V2 only: record reviewed worktree sources and immutable per-run snapshots")
    a=p.parse_args();run(a.roots,a.config,a.sequence,a.method,a.attempt,allow_source_overlay=a.allow_source_overlay)
