#!/usr/bin/env python3
"""One registered six-call empty-phase ARC replay; no information/evaluation math.

This is a new matched-timeline control, not historical PVT trajectory reproduction.
Only telemetry serialization and CLI output destination differ within each pair.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import time
import traceback
import arc_native_real as h

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007"
PLAN = D / "ARC_NATIVE_REPLAY_PLAN.json"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_native_replay.py"
STAGE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_REPLAY_ATTEMPT01"
PREPARED_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_TELEMETRY_REPAIR01"
SIDS = ("BY2", "BY2H", "BY2O")
ARMS = (("ARC_NULL", "0"), ("ARC_TELEMETRY", "1"))
BASE_BUDGET = dict(native_calls=6, evaluator_calls=0, prepare_calls=0, compile_calls=0,
                   loader_only_calls=0, raw_reads=0, reference_reads=0, phase_math_calls=0,
                   information_readout_calls=0, provider_hash_passes=2,
                   provider_unique_files=18, provider_bytes_per_hash_pass=120200614,
                   provider_hash_bytes_max=240401228, native_timeout_s=1200,
                   structural_summary_passes=1, automatic_retries=0)
ENV = {"PATH":"/usr/bin:/bin", "LANG":"C.UTF-8", "LC_ALL":"C.UTF-8",
       "OMP_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1", "MKL_NUM_THREADS":"1",
       "NUMEXPR_NUM_THREADS":"1"}
NUMERIC_FILES = {"KF_GINS_Navresult.nav": (11,1), "KF_GINS_STD.txt": (22,0),
                 "KF_GINS_IMU_ERR.txt": (13,0)}
REQUIRED = set(NUMERIC_FILES) | {"LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv",
            "RUN_MANIFEST.json", "HEADING_SOURCE_EVENTS.csv",
            "ARC_LIFECYCLE.csv", "ARC_CONDITIONING_EVENTS.jsonl", "ARC_IMU_SEGMENTS.csv"}
MAX_OUTPUT_BYTES = 4*1024**3
MAX_PRIOR_LINE = 2*1024**2
OWN_STAGE = None
CALLS = []
HASH_PASSES = []


def emit(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n"); f.flush(); os.fsync(f.fileno())


def bits(value):
    return struct.pack(">d", float(value)).hex()


def finite_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def normalized(pin, aliases):
    return (str(h.expand(pin["path"],aliases)), pin["sha256"], pin["size_bytes"])


def check_metadata(pin, aliases):
    path = h.expand(pin["path"],aliases)
    h.require(path.stat().st_size == pin["size_bytes"], "metadata size changed: "+str(path))
    h.require(h.digest(path) == pin["sha256"], "metadata hash changed: "+str(path))
    return path


def register(commit):
    reg = h.read(PLAN)
    h.require(reg["schema"] == "arc_native_replay.registration/v1" and
              reg["status"] == "REGISTERED_READY_SINGLE_EXECUTION", "draft is not executable")
    h.require(reg["budgets"] == BASE_BUDGET and reg["environment_common"] == ENV,
              "fixed budget/environment")
    h.require(reg["stage"] == "<SCRATCH_ROOT>/"+STAGE_REL and
              reg["prepared_stage"] == "<SCRATCH_ROOT>/"+PREPARED_REL,
              "fixed new replay and existing preparation stages")
    h.require(reg["ordered_calls"] == [dict(sequence_id=s,arm=a,telemetry_flag=f)
              for s in SIDS for a,f in ARMS], "six fixed calls")
    h.require(reg["manifest_difference_keys"] == ["arc_native_telemetry_enabled"] and
              reg["telemetry_only_files"] == ["ARC_JOINT_PRIORS.jsonl"], "fixed identity exceptions")
    h.require(SCRIPT in reg["source_pins"], "replay source must be frozen")
    h.require(PLAN.read_bytes() == subprocess.check_output(
        ["git","show",commit+":"+PLAN.relative_to(ROOT).as_posix()],cwd=ROOT), "plan not registered")
    h.source_check(reg,commit)
    aliases=reg["aliases"]; scratch=ROOT.parent.parent/"LegSA-GINS-SCRATCH"
    h.require(h.expand("<CODE_ROOT>",aliases)==ROOT and
              h.expand("<SCRATCH_ROOT>",aliases)==scratch.resolve(), "fixed workspace aliases")
    stage=h.expand(reg["stage"],aliases); prepared=h.expand(reg["prepared_stage"],aliases)
    h.require(not stage.exists(), "replay stage already exists; no retry or alternate output")
    metadata={k:check_metadata(p,aliases) for k,p in reg["metadata_pins"].items()}
    h.require(metadata["prepared_plan"]==prepared/"PLAN.json" and
              metadata["prepared_receipt"]==prepared/"PREPARED.json" and
              metadata["loader_complete"]==prepared/"LOADER_COMPLETION01/COMPLETE.json", "sealed metadata paths")
    plan=h.read(metadata["prepared_plan"]); receipt=h.read(metadata["prepared_receipt"])
    loader=h.read(metadata["loader_complete"])
    h.require(receipt["status"]=="PREPARED_METADATA_ONLY_NO_NATIVE" and
              receipt["plan_sha256"]==reg["metadata_pins"]["prepared_plan"]["sha256"], "prepared seal")
    h.require(plan["registration_commit"]==reg["prepare_registration_commit"] and
              loader["registration_commit"]==reg["loader_registration_commit"] and
              loader["status"]=="COMPLETE_THREE_LOADER_QUALIFICATIONS_ONE_REUSED_TWO_NEW" and
              loader["prepared_plan_sha256"]==receipt["plan_sha256"], "loader/preparation seal chain")
    h.require(h.read(metadata["loader_audit"])["status"]=="PASS_WITH_STATED_TRACE_SCOPE", "independent loader gate")
    h.require(plan["aliases"]==aliases and tuple(x["sequence_id"] for x in plan["runs"])==SIDS and
              plan["total_blocks"]==921 and plan["total_endpoints"]==1842, "full prepared denominator")
    h.require(h.expand(plan["binary"]["path"],aliases)==h.expand(reg["binary"]["path"],aliases) and
              plan["binary"]["sha256"]==reg["binary"]["sha256"]==
              "3010a85d27d0571f27640f68814b522c7094e32455c9cc7b8bdf43d11331013e", "same qualified binary")
    binary=check_metadata(reg["binary"],aliases)
    check_metadata(reg["strace"],aliases)
    h.require(h.expand(reg["strace"]["path"],aliases)==Path("/usr/bin/strace"), "fixed tracer")
    closure={}
    for run,entry in zip(plan["runs"],loader["records"]):
        sid=run["sequence_id"]
        h.require(entry["sequence_id"]==sid and len(entry["original_scientific_echo"])==53,
                  "same qualified sequence/static fields")
        for role in ("config","events","manifest"):
            h.require(normalized(run[role],aliases)==normalized(reg["metadata_pins"][sid+"_"+role],aliases),
                      "prepared input changed: "+sid+"/"+role)
        h.require(normalized(entry["echo"],aliases)==normalized(reg["metadata_pins"][sid+"_loader_echo"],aliases),
                  "qualified loader echo pin")
        for item in [*run["providers"].values(),run["carrier"]]:
            identity=normalized(item,aliases)
            h.require(identity[0] not in closure or closure[identity[0]]==identity, "conflicting inherited pins")
            closure[identity[0]]=identity
    declared={normalized(p,aliases)[0]:normalized(p,aliases) for p in reg["provider_inputs"]}
    h.require(len(declared)==len(reg["provider_inputs"])==18 and closure==declared,
              "provider hash closure must equal exact three-run providers plus carrier")
    h.require(sum(x[2] for x in declared.values())==BASE_BUDGET["provider_bytes_per_hash_pass"], "input byte budget")
    for path,_,size in declared.values():
        h.require(Path(path).stat().st_size==size,"provider size before registered read")
    return reg,aliases,stage,plan,loader,binary


def provider_hash_pass(reg,aliases,stage,label):
    h.require(label in ("PRE","POST") and label not in HASH_PASSES,"one pre/post hash pass only")
    HASH_PASSES.append(label); rows=[]; total=0
    try:
        for item in reg["provider_inputs"]:
            path=h.expand(item["path"],aliases)
            h.require(path.stat().st_size==item["size_bytes"],"provider size drift")
            actual=h.digest(path);total+=item["size_bytes"]
            rows.append(dict(path=str(path),size_bytes=item["size_bytes"],expected_sha256=item["sha256"],sha256=actual))
            h.require(actual==item["sha256"],"inherited provider hash mismatch: "+str(path))
        h.require(len(rows)==18 and total==120200614,"one complete unique-input hash pass")
    finally:
        emit(stage/(label+"_PROVIDER_HASHES.json"),dict(pass_name=label,files=rows,bytes_hashed=total,
             complete=len(rows)==18 and all(x["sha256"]==x["expected_sha256"] for x in rows)))


def launch(reg,aliases,stage,run,arm,flag,binary,ordinal):
    dest=stage/(run["sequence_id"]+"__"+arm);dest.mkdir();out=dest/"OUT";out.mkdir()
    config=h.expand(run["config"]["path"],aliases)
    command=[str(binary),"--config",str(config),"--output-dir",str(out)]
    argv=["/usr/bin/strace","-f","-yy","-s","4096","-e","trace=openat,execve",
          "-o",str(dest/"OPENAT.strace"),*command]
    env={**ENV,"LEGSA_ARC_NATIVE_TELEMETRY":flag}
    invocation=dict(ordinal=ordinal,sequence_id=run["sequence_id"],arm=arm,argv=argv,environment=env,
                    timeout_s=1200,retry=0,config=run["config"],binary=reg["binary"],
                    events=run["events"],schedule_manifest=run["manifest"],
                    scientific_providers=[*run["providers"].values(),run["carrier"]])
    emit(dest/"INVOCATION.json",invocation); CALLS.append(dict(ordinal=ordinal,sequence_id=run["sequence_id"],arm=arm))
    started=time.monotonic();timed_out=False;code=None
    with (dest/"stdout.log").open("x") as stdout,(dest/"stderr.log").open("x") as stderr:
        process=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=process.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGKILL);code=process.wait()
    result=dict(returncode=code,timed_out=timed_out,elapsed_s=time.monotonic()-started,retry=0)
    emit(dest/"PROCESS_RESULT.json",result)
    allowed=[binary,config,h.expand(run["events"]["path"],aliases)]
    allowed += [h.expand(x["path"],aliases) for x in [*run["providers"].values(),run["carrier"]]]
    audit=h.audit_openat(dest/"OPENAT.strace",aliases,allowed,out)
    text=(dest/"OPENAT.strace").read_text(errors="replace")
    execs=[m.group(1) for line in text.splitlines() if re.search(r"= 0\s*$",line)
           for m in [re.search(r'execve\("([^"]+)"',line)] if m]
    audit["successful_execs"]=execs
    audit["exact_native_exec_passed"]=execs==[str(binary)]
    reads={x["path"] for x in audit["protected_opens"] if not x["writing"]}
    audit["all_declared_run_inputs_opened"]=set(map(str,allowed[1:])).issubset(reads)
    emit(dest/"ACCESS_AUDIT.json",audit)
    h.require(code==0 and not timed_out and audit["passed"] and audit["exact_native_exec_passed"] and
              audit["all_declared_run_inputs_opened"],"native/process/access first failure; preserve, no retry")
    return dest,out


def seal_outputs(out,window):
    files=sorted(p for p in out.rglob("*") if p.is_file())
    h.require(files and all(not p.is_symlink() for p in out.rglob("*")),"no output symlinks")
    h.require(sum(p.stat().st_size for p in files)<=MAX_OUTPUT_BYTES,"per-run output byte ceiling")
    pins={}; health={}
    for path in files:
        name=path.relative_to(out).as_posix();sha=hashlib.sha256()
        if name in NUMERIC_FILES:
            columns,time_column=NUMERIC_FILES[name];count=0;first=None;last=None;times=hashlib.sha256()
            with path.open("rb") as f:
                for line in f:
                    sha.update(line);values=[float(x) for x in line.split()]
                    h.require(len(values)==columns and all(math.isfinite(v) for v in values),"finite native columns")
                    t=values[time_column]
                    h.require(last is None or t>last,"strict native sample time")
                    h.require(window[0]-1e-7<=t<=window[1]+1e-7,"native output within registered window")
                    if first is None:first=t
                    last=t;count+=1;times.update(struct.pack("<d",t))
            h.require(count>1,"native output sample coverage")
            health[name]=dict(rows=count,first_time_s=first,last_time_s=last,time_keys_sha256=times.hexdigest())
        else:
            with path.open("rb") as f:
                for block in iter(lambda:f.read(1024*1024),b""):sha.update(block)
        pins[name]=dict(sha256=sha.hexdigest(),size_bytes=path.stat().st_size)
    h.require(REQUIRED.issubset(pins),"missing required native/common output")
    h.require(len({(v["rows"],v["time_keys_sha256"]) for v in health.values()})==1,"NAV/STD/IMUERR sample identity")
    return dict(files=pins,numeric_serialization_health=health)


def manifest_gate(manifest,run,loader_record,flag,aliases):
    h.require(manifest["cov_health_fail_count"]==0 and manifest["cov_health_status"]=="PASS" and
              manifest["propagation_count"]>0,"runtime finite covariance health")
    for key,value in loader_record["original_scientific_echo"].items():
        h.require(manifest.get(key)==value,"runtime static scientific echo: "+key)
    for key,value in loader_record["arc_and_metadata_echo"].items():
        h.require(manifest.get(key)==value,"runtime ARC identity: "+key)
    h.require(manifest["phase"]==manifest["stage_id"] and
              manifest["arc_native_telemetry_enabled"]==(flag=="1"),"phase metadata / actual telemetry arm")
    h.require(manifest["arc_phase_updates"]==manifest["arc_foot_pair_updates"]==0 and
              manifest["heading_carrier_attempt_count"]==0,"empty phase/PVT-control updates only")
    h.require(manifest["arc_source_blocks"]==run["block_count"] and
              manifest["arc_source_rows"]==2*run["block_count"],"all scheduled source endpoints")
    expected=h.read(h.expand(loader_record["echo"]["path"],aliases))["actual_solver_input_paths"]
    h.require(manifest["actual_solver_input_paths"]==expected,"runtime provider path declaration")


def pair_gate(null,telem,run):
    a=null["seal"]["files"];b=telem["seal"]["files"]
    h.require(set(b)-set(a)=={"ARC_JOINT_PRIORS.jsonl"} and not set(a)-set(b),"only intentional telemetry file")
    equal=[]
    for name in sorted(set(a)&set(b)):
        if name=="RUN_MANIFEST.json":continue
        h.require(a[name]==b[name],"matched-timeline byte identity failed: "+name);equal.append(name)
    ma=dict(null["manifest"]);mb=dict(telem["manifest"])
    h.require(ma.pop("arc_native_telemetry_enabled") is False and mb.pop("arc_native_telemetry_enabled") is True,
              "manifest flags must actually differ")
    h.require(ma==mb,"manifest differs beyond serialization flag")
    return dict(sequence_id=run["sequence_id"],status="PASS_COMMON_BYTE_IDENTITY",byte_equal_files=equal,
                manifest_difference_keys=["arc_native_telemetry_enabled"],telemetry_only_files=["ARC_JOINT_PRIORS.jsonl"],
                historical_PVT_trajectory_identity_claim=False)


def exact_event(prior,event):
    for key in ("sequence_id","block_id","endpoint_id","role","source_time_bits_hex","endpoint_model_fingerprint"):
        h.require(prior[key]==event[key],"prior/source identity: "+key)
    h.require(prior["epoch_index"]==int(event["epoch_index"]) and
              bits(prior["source_time_s"])==event["source_time_bits_hex"] and
              bits(prior["replay_execution_time_s"])==event["source_time_bits_hex"] and
              prior["actual_available_time_s"] is None and
              prior["availability_mode"]=="SOURCE_TIME_REPLAY_ASSUMPTION","prior exact time / unknown arrival")


def structure_summary(run,null,telem,aliases):
    """One post-six-seal schema/identity pass; no covariance algebra or phase values."""
    sid=run["sequence_id"]; n=run["block_count"]
    with h.expand(run["events"]["path"],aliases).open() as f: events=list(csv.DictReader(f))
    h.require(len(events)==2*n,"source denominator in field-only pass")
    source={events[i]["block_id"]:(events[i],events[i+1]) for i in range(0,len(events),2)}
    h.require(len(source)==n,"source unique block identity")
    with (null["out"]/"ARC_LIFECYCLE.csv").open() as f: life=list(csv.DictReader(f))
    h.require(len(life)==n and len({x["block_id"] for x in life})==n,"full lifecycle denominator")
    statuses=Counter(); covered={}; legal_covered=0; missing_covered=0
    for row in life:
        pair=source[row["block_id"]];statuses[row["status"]]+=1
        h.require(row["sequence_id"]==sid and row["actual_available_time_s"]=="" and
                  row["availability_mode"]=="SOURCE_TIME_REPLAY_ASSUMPTION" and row["planned_clone_owner"]=="ARC",
                  "lifecycle identity/availability")
        h.require(row["status"] in ("COVERED_END_PRIOR","UNCOVERED_INITIAL_STATE","UNCOVERED_TERMINAL"),"explicit final block status")
        for prefix,event in zip(("start","end"),pair):
            h.require(row[prefix+"_endpoint_id"]==event["endpoint_id"] and
                      row[prefix+"_epoch_index"]==event["epoch_index"] and
                      row[prefix+"_model_fingerprint"]==event["endpoint_model_fingerprint"] and
                      row[prefix+"_source_time_bits_hex"]==event["source_time_bits_hex"] and
                      bits(row[prefix+"_source_time_s"])==event["source_time_bits_hex"] and
                      bits(row[prefix+"_replay_execution_time_s"])==event["source_time_bits_hex"],"lifecycle exact endpoint")
            if row[prefix+"_state_time_s"]:
                h.require(bits(row[prefix+"_state_time_s"])==event["source_time_bits_hex"],"no snapped state endpoint")
        if row["status"]=="COVERED_END_PRIOR":
            h.require(row["clone_created"]=="1" and row["clone_owner_at_creation"]=="ARC" and
                      all(row[k]=="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP" for k in
                          ("dispatch_phase","start_dispatch_phase","end_dispatch_phase")),"covered dispatch identity")
            h.require(row["start_state_time_s"] and row["end_state_time_s"],"covered state times present")
            covered[row["block_id"]]=row
            if all(e["endpoint_model_fingerprint"] for e in pair):legal_covered+=1
            else:missing_covered+=1
        elif row["status"]=="UNCOVERED_INITIAL_STATE":
            h.require(row["clone_created"]=="0" and row["clone_owner_at_creation"]=="NONE" and
                      row["start_dispatch_phase"]=="NOT_DISPATCHED" and not row["start_state_time_s"],
                      "initial uncovered has no invented start clone")
            if row["end_state_time_s"]:
                h.require(row["end_dispatch_phase"]=="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP" and
                          row["dispatch_phase"]=="END_DISPATCHED_START_UNCOVERED", "actual END on initial uncovered")
            else:
                h.require(row["end_dispatch_phase"]==row["dispatch_phase"]=="NOT_DISPATCHED",
                          "wholly initial uncovered has no dispatch")
        else:
            h.require(row["end_dispatch_phase"]=="NOT_DISPATCHED" and not row["end_state_time_s"],
                      "terminal uncovered has no invented END")
            if row["clone_created"]=="1":
                h.require(row["clone_owner_at_creation"]=="ARC" and row["start_state_time_s"] and
                          row["start_dispatch_phase"]=="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",
                          "active terminal block retains actual START")
                h.require(row["dispatch_phase"]=="START_DISPATCHED_END_UNCOVERED", "active terminal phase")
            else:
                h.require(row["clone_created"]=="0" and row["clone_owner_at_creation"]=="NONE" and
                          row["start_dispatch_phase"]=="NOT_DISPATCHED" and not row["start_state_time_s"],
                          "future terminal block was never cloned")
                h.require(row["dispatch_phase"]=="NOT_DISPATCHED", "future terminal phase")
    manifest=null["manifest"]
    starts=sum(row["clone_created"]=="1" for row in life)
    h.require(manifest["arc_starts"]==manifest["arc_retires"]==starts and
              manifest["arc_ends"]==len(covered),"clone creation/end/retirement counters")
    for status,key in (("COVERED_END_PRIOR","arc_covered_blocks"),("UNCOVERED_INITIAL_STATE","arc_uncovered_initial"),
                       ("UNCOVERED_TERMINAL","arc_uncovered_terminal")):
        h.require(statuses[status]==manifest[key],"lifecycle/manifest count identity")
    ledger=[];kinds=Counter(); source_audit={}; source_seen={}; update_ordinal=0; reset_ordinal=0; last_ledger_time=None
    # Reporting only: the inherited real NED-HV scheduler may use a future
    # reported source timestamp or reuse a provider row. Arrival stays unknown.
    source_tags=("GO2_VELOCITY_DIAGNOSTIC","GO2_ATTITUDE_RP","RAW_DOPPLER")
    with (null["out"]/"ARC_CONDITIONING_EVENTS.jsonl").open() as f:
        for line in f:
            entry=json.loads(line);ledger.append(entry);kinds[entry["kind"]]+=1
            h.require(entry["kind"] in ("ORDINARY_UPDATE","FULL_RESET","UNCOVERED_INITIAL_STATE",
                      "ARC_START","ARC_END","ARC_END_UNCOVERED_INITIAL","ARC_TERMINAL_RETIRE"),"known conditioning kind")
            update_ordinal+=int(entry["kind"]=="ORDINARY_UPDATE")
            reset_ordinal+=int(entry["kind"]=="FULL_RESET")
            h.require(entry["update_ordinal"]==update_ordinal and entry["reset_ordinal"]==reset_ordinal and
                      (last_ledger_time is None or entry["state_time_s"]>=last_ledger_time),"conditioning prefix counts/time")
            last_ledger_time=entry["state_time_s"]
            h.require(entry["ordinal"]==len(ledger) and finite_number(entry["state_time_s"]) and
                      bits(entry["state_time_s"])==entry["state_time_bits_hex"] and
                      entry["actual_available_time_s"] is None and entry["phase_state_cross"]=="UNKNOWN", "conditioning ledger fields")
            if entry["kind"]=="ORDINARY_UPDATE" and entry["source_tag"] in source_tags:
                tag=entry["source_tag"]
                counts=source_audit.setdefault(tag,dict(update_rows=0,identity_unavailable=0,
                       source_time_after_state_rows=0,repeated_vector_index_rows=0,
                       inconsistent_source_time_for_vector_index_rows=0))
                counts["update_rows"]+=1
                match=re.fullmatch(r"SOURCE_TIME_BITS:([0-9a-f]{16}):VECTOR_INDEX:([0-9]+)",
                                   entry["provider_measurement_identity"])
                if match is None:counts["identity_unavailable"]+=1
                else:
                    source_time=struct.unpack(">d",bytes.fromhex(match[1]))[0];index=int(match[2])
                    h.require(math.isfinite(source_time),"finite logged provider source time")
                    counts["source_time_after_state_rows"]+=int(source_time>entry["state_time_s"])
                    seen_tag=source_seen.setdefault(tag,{})
                    if index in seen_tag:
                        counts["repeated_vector_index_rows"]+=1
                        counts["inconsistent_source_time_for_vector_index_rows"]+=int(seen_tag[index]!=match[1])
                    seen_tag[index]=match[1]
    consumed=sum(kinds[k] for k in ("UNCOVERED_INITIAL_STATE","ARC_START","ARC_END","ARC_END_UNCOVERED_INITIAL"))
    h.require(consumed==manifest["arc_consumed_event_rows"]<=2*n and
              kinds["ORDINARY_UPDATE"]==manifest["arc_ordinary_updates"] and
              kinds["FULL_RESET"]==manifest["arc_full_resets"],"source consumption and conditioning counters")
    dimensions={"start_P21":(21,21),"J0":(3,21),"start_C0":(3,3),"P24":(24,24),
                "clone_C0_given_end":(3,3),"current_cbn":(3,3),"current_C1":(3,3),
                "J1":(3,21),"B6":(6,24),"P6":(6,6)}
    seen=set()
    with (telem["out"]/"ARC_JOINT_PRIORS.jsonl").open() as f:
        while True:
            line=f.readline(MAX_PRIOR_LINE+1)
            if not line:break
            h.require(len(line)<=MAX_PRIOR_LINE and len(seen)<n,"bounded prior field read")
            p=json.loads(line);bid=p["start"]["block_id"]
            h.require(bid in covered and bid not in seen,"one prior per covered block")
            seen.add(bid);row=covered[bid]
            for key,event in zip(("start","end"),source[bid]):exact_event(p[key],event)
            for prefix in ("start","end"):
                h.require(bits(p[prefix+"_state_time_s"])==source[bid][0 if prefix=="start" else 1]["source_time_bits_hex"],"prior exact state time")
                for field in ("update_ordinal","reset_ordinal"):
                    h.require(p[prefix+"_"+field]==int(row[prefix+"_"+field]),"prior conditioning ordinals")
            h.require(p["schema_version"]==1 and p["run_id"]==run["run_id"] and
                      p["arc_source_events_sha256"]==run["events"]["sha256"] and
                      p["arc_schedule_manifest_sha256"]==run["manifest"]["sha256"] and
                      p["actual_available_time_s"] is None and p["phase_state_cross"]=="UNKNOWN" and
                      p["dispatch_phase"]=="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP", "prior provenance/availability")
            expected_strings=dict(
                source_time_scale_id="UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS",
                source_time_mapping_id=sid+":SEALED_RAWX_UTC_AND_CALIBRATED_IMU_BASE_V1",
                pin_validation="DECLARED_PINS_EXTERNAL_RUNNER_VERIFICATION_REQUIRED",
                config_binary_provider_hash_binding="EXTERNAL_SEALED_RUN_RECEIPT_REQUIRED",
                error_order="current21_P_V_PHI_BG_BA_SG_SA_then_ECEF_clone3",
                error_units="m_mps_rad_radps_mps2_dimensionless_dimensionless_rad",
                error_convention="position_velocity_estimate_minus_true_attitude_and_clone_positive_left_truth_from_nominal_bias_scale_true_minus_nominal",
                prior_scope="INHERITED_WORKING_MODEL_CONDITIONAL_ON_EXECUTED_PREFIX_NOT_CALIBRATED_TRUTH")
            h.require(all(p.get(k)==v for k,v in expected_strings.items()),"prior error/source contract fields")
            ordinal=p["conditioning_ordinal"]
            h.require(isinstance(ordinal,int) and 0<=ordinal<len(ledger) and ledger[ordinal]["kind"]=="ARC_END" and
                      ledger[ordinal]["block_id"]==bid,"prior binds completed ordinary prefix before its ARC_END")
            end_event=ledger[ordinal]
            h.require(end_event["state_time_bits_hex"]==p["end"]["source_time_bits_hex"] and
                      end_event["update_ordinal"]==p["end_update_ordinal"] and
                      end_event["reset_ordinal"]==p["end_reset_ordinal"] and end_event["clone_owner"]=="ARC",
                      "END ledger/current joint prior same prefix")
            identity=(run["run_id"]+":"+run["events"]["sha256"]+":"+run["manifest"]["sha256"]+
                      ":U"+str(p["end_update_ordinal"])+":R"+str(p["end_reset_ordinal"])+
                      ":L"+str(ordinal)+":T"+p["end"]["source_time_bits_hex"])
            h.require(p["conditioning_information_id"]==identity,"same conditioning-information identity")
            for key,(rows,cols) in dimensions.items():
                a=p[key];h.require(isinstance(a,list) and len(a)==rows and all(isinstance(v,list) and len(v)==cols and
                      all(finite_number(x) for x in v) for v in a),"finite matrix dimensions only: "+key)
            for key,size in (("dx24",24),("start_blh",3),("current_blh",3)):
                h.require(len(p[key])==size and all(finite_number(x) for x in p[key]),"finite vector dimensions: "+key)
            h.require(all(x==0 for x in p["dx24"]),"complete END feedback zero error")
    h.require(seen==set(covered),"all covered priors present, no uncovered prior fabricated")
    return dict(sequence_id=sid,source_blocks=n,source_endpoints=2*n,consumed_endpoints=consumed,
                unconsumed_endpoints=2*n-consumed,lifecycle_status_counts=dict(statuses),prior_rows=len(seen),
                legal_model_blocks=run["legal_model_blocks"],legal_model_covered=legal_covered,
                missing_model_blocks=n-run["legal_model_blocks"],missing_model_covered=missing_covered,
                phase_state_cross="UNKNOWN",actual_available_time_s=None,matrix_algebra_calls=0,
                real_hv_source="INHERITED_STATUS_A1_ROTATED_NED_WEAK_PRIOR",
                reported_provider_source_time_audit=source_audit,
                source_time_audit_is_report_only_no_zero_gate=True,
                all_source_online_causality_qualified=False,
                prior_scope="OFFLINE_EXECUTED_PREFIX_WORKING_PRIOR")


def main():
    global OWN_STAGE
    parser=argparse.ArgumentParser();parser.add_argument("--registration-commit",required=True);args=parser.parse_args()
    reg,aliases,stage,plan,loader,binary=register(args.registration_commit)
    stage.mkdir();OWN_STAGE=stage
    emit(stage/"REGISTERED_PLAN.json",reg)
    emit(stage/"RESERVATION.json",dict(registration_commit=args.registration_commit,budget=BASE_BUDGET,
         started_unix_s=time.time(),automatic_retry=False))
    pre_complete=False;records=[];pairs=[]
    try:
        provider_hash_pass(reg,aliases,stage,"PRE");pre_complete=True
        for run,lrec in zip(plan["runs"],loader["records"]):
            pair=[]
            for arm,flag in ARMS:
                dest,out=launch(reg,aliases,stage,run,arm,flag,binary,len(CALLS)+1)
                seal=seal_outputs(out,run["window"]);manifest=h.read(out/"RUN_MANIFEST.json")
                manifest_gate(manifest,run,lrec,flag,aliases)
                emit(dest/"OUTPUT_SEAL.json",seal)
                record=dict(sequence_id=run["sequence_id"],arm=arm,out=out,seal=seal,manifest=manifest)
                records.append(record);pair.append(record)
            checked=pair_gate(pair[0],pair[1],run);pairs.append(checked)
            emit(stage/(run["sequence_id"]+"_PAIR_IDENTITY.json"),checked)
            print(run["sequence_id"],"PAIR_BYTE_IDENTITY_PASS",flush=True)
        provider_hash_pass(reg,aliases,stage,"POST")
        h.source_check(reg,args.registration_commit)
        for spec in reg["metadata_pins"].values():check_metadata(spec,aliases)
        check_metadata(reg["binary"],aliases);check_metadata(reg["strace"],aliases)
        # Bind the complete execution evidence without re-hashing large OUT payloads.
        # OUT pins come from each already completed serialization/health seal.
        evidence_paths=[stage/"REGISTERED_PLAN.json",stage/"RESERVATION.json",
                        stage/"PRE_PROVIDER_HASHES.json",stage/"POST_PROVIDER_HASHES.json"]
        evidence_paths += [stage/(sid+"_PAIR_IDENTITY.json") for sid in SIDS]
        for record in records:
            dest=record["out"].parent
            evidence_paths += [dest/name for name in ("INVOCATION.json","PROCESS_RESULT.json",
                              "ACCESS_AUDIT.json","OPENAT.strace","stdout.log","stderr.log","OUTPUT_SEAL.json")]
        execution_evidence={p.relative_to(stage).as_posix():dict(sha256=h.digest(p),size_bytes=p.stat().st_size)
                            for p in evidence_paths}
        emit(stage/"ALL_NATIVE_SEALED.json",dict(status="ALL_SIX_NATIVE_SEALED_AND_THREE_PAIRS_IDENTICAL",
             registration_commit=args.registration_commit,calls=CALLS,pairs=pairs,
             outputs=[dict(sequence_id=x["sequence_id"],arm=x["arm"],path=str(x["out"]),seal=x["seal"]) for x in records],
             provider_hash_passes=HASH_PASSES,metadata_pins=reg["metadata_pins"],binary=reg["binary"],
             execution_evidence=execution_evidence))
        summary=[structure_summary(run,records[2*i],records[2*i+1],aliases) for i,run in enumerate(plan["runs"])]
        h.require(sum(x["source_blocks"] for x in summary)==921 and
                  sum(x["source_endpoints"] for x in summary)==1842,"full final denominator")
        emit(stage/"COMPLETE.json",dict(status="COMPLETE_MATCHED_EMPTY_PHASE_NATIVE_TELEMETRY_NOT_INFORMATION_GAIN",
             registration_commit=args.registration_commit,native_calls=len(CALLS),evaluator_calls=0,
             phase_math_calls=0,information_readout_calls=0,structural_summary_passes=1,sequences=summary,
             seal_sha256=h.digest(stage/"ALL_NATIVE_SEALED.json"),historical_PVT_exact_identity_claim=False,
             actual_arrival_qualified=False,phase_fusion=False,provider_hash_status="PRE_AND_POST_REHASHED_MATCH"))
    except BaseException as exc:
        post_error=None
        if pre_complete and "POST" not in HASH_PASSES:
            try:provider_hash_pass(reg,aliases,stage,"POST")
            except BaseException as post:post_error=repr(post)
        emit(stage/"FAILED.json",dict(error=repr(exc),traceback=traceback.format_exc(),calls_started=CALLS,
             provider_hash_passes=HASH_PASSES,post_hash_error=post_error,retry_allowed=False,
             first_failure_preserved=True,native_budget_remaining_not_auto_used=6-len(CALLS)))
        raise


if __name__=="__main__":main()
