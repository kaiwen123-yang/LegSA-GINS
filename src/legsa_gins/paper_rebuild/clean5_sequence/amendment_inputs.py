"""C-04b B/C orchestration after the published 10/10 A.4 revalidation gate.

Only frozen observation providers and explicitly admitted raw Go2/status inputs
are read. This module never runs providers, solvers, evaluators, or plotters.
Three independent strace sessions isolate pre-hashing, events, and post-hashing.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .. import providers
from ..manifest import sha256_file, verify_raw_sources
from ..paths import guard_path, load_yaml_mapping
from ..subprocess_guard import run_process_group
from . import alignment_diagnostics as diagnostics
from . import event_window
from .generation_audit import (audit_records, selected_lock, validate_checkpoint,
                               write_json_exclusive)
from .io_audit import audited_open_records, write_scope_audit
from .probes import forbidden_path_guard, open_probe_file
from .registry import load_registry
from .revalidation import _published_source
from .runtime_config import METHODS
from .solver_runner import (C02_COMMIT, EXECUTABLE_RELATIVE, _record_hashes,
                             verify_executable, verify_provider_files)

ORDER = ("BY2", "BY2H", "BY2O")
CONTROL_STAGE = "CLEAN5_BY2_CONTROL_PROVIDER_PARITY"
BASE_TIMES = {"BY2": 1772784000.0, "BY2H": 1772784000.0, "BY2O": 1772780400.0}
COMMON_COVERAGE = {"BY2": (55.20679450035095,349.20453906059265),
                   "BY2H": (400.20381903648376,692.2076218128204),
                   "BY2O": (3143.211548805237,3572.2081441879272)}
COMMON_REPORT_SHA256 = {"BY2": "5684d32255b99e015b9e959ce7344e85c4ca49bd81eecbe1e861c59ece209965",
                        "BY2H": "6f29f668481f7e1ac31453b0a6a94f12adedda9f6c96c661453a70e892b089d5",
                        "BY2O": "7e1850fc9a9de867634e43ceab342eead0772b77e430ad31ce619bb02ddd5672"}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_text(path, text):
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(text)


def stage_root(registry, dataset):
    name = CONTROL_STAGE if dataset == "BY2" else registry.sequences[dataset].stage_id
    return guard_path(registry.clean_root / "stages" / name, role="C-04b event stage",
                       allowed_root=registry.clean_root, must_exist=True)


def require_revalidation_gate(registry, code_freeze_commit):
    root = registry.clean_root / "stages" / CONTROL_STAGE / "00_C04B_REVALIDATION_V2"
    gate_path, result_path = root / "REVALIDATION_GATE.json", root / "REVALIDATION_RESULT.json"
    gate, result = _read(gate_path), _read(result_path)
    expected_ids = {f"{dataset}_{method}_{profile}" for dataset in ("BY2H","BY2O") for method,profile in METHODS.items()}
    rows = result.get("runs", [])
    valid = (gate.get("status") == "PASS" and gate.get("passed") is True
             and gate.get("passed_run_count") == 10 and gate.get("worker_exit_code") == 0
             and gate.get("strace_audit",{}).get("pass") is True
             and gate.get("code_freeze_commit") == code_freeze_commit
             and result.get("code_freeze_commit") == code_freeze_commit
             and gate.get("result_sha256") == sha256_file(result_path)
             and result.get("passed") is True and result.get("expected_run_count") == 10
             and result.get("passed_run_count") == 10 and len(rows) == 10
             and {row.get("run_id") for row in rows} == expected_ids
             and all(row.get("passed") is True and row.get("terminal_status") == "COMPLETED" for row in rows))
    if not valid:
        raise RuntimeError("A.4 must pass all ten immutable v1 runs under the published code freeze before event computation")
    return {"path": str(gate_path), "sha256": sha256_file(gate_path),
            "result_path": str(result_path), "result_sha256": sha256_file(result_path),
            "passed_run_count": 10, "code_freeze_commit": code_freeze_commit}


def require_prior_sequence_gates(registry,dataset,code_freeze_commit):
    for prior in ORDER[:ORDER.index(dataset)]:
        prior_stage = stage_root(registry,prior)
        path = prior_stage / "06_ALIGNMENT_DIAGNOSTICS/00_AUDIT/EVENT_PHASE_GATE.json"
        gate = _read(path)
        expected_event = prior_stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json"
        if gate.get("event_path") != str(expected_event):
            raise RuntimeError("Prior event path differs from its exact stage-owned file")
        expected_event = guard_path(expected_event,role="prior event",allowed_root=prior_stage,
                                    must_exist=True,regular_file=True)
        if (gate.get("passed") is not True or gate.get("code_freeze_commit") != code_freeze_commit
                or gate.get("event_sha256") != sha256_file(expected_event)
                or gate["pre_checkpoint"]["verified_hashes"] != gate["post_checkpoint"]["verified_hashes"]):
            raise RuntimeError(f"{prior} event/checkpoint gate must pass unchanged before {dataset}")


def _checked_json(path, expected, *, root, role):
    path = guard_path(path, role=role, allowed_root=root, must_exist=True, regular_file=True)
    if sha256_file(path) != expected:
        raise RuntimeError(f"{role} SHA-256 differs from frozen provenance")
    return _read(path), {"path": str(path), "sha256": expected}


def metadata_inputs(registry, dataset):
    """Validate frozen metadata and provider hashes without opening raw bytes."""
    seq, stage = registry.sequences[dataset], stage_root(registry,dataset)
    hashes, _, record_sha = _record_hashes(registry.code_root)
    manifest_path = stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"
    alias = "<CLEAN_ROOT>/" + manifest_path.relative_to(registry.clean_root).as_posix()
    manifest, manifest_ref = _checked_json(manifest_path,hashes[alias],root=stage,role="C-03 provider manifest")
    if manifest.get("dataset_id") != dataset or manifest.get("status") != "PASS_PROVIDER_FREEZE":
        raise RuntimeError("Frozen provider manifest identity/status mismatch")
    provider_checks = verify_provider_files(stage / "02_PROVIDER_FREEZE",manifest)
    lock = selected_lock(registry,seq)
    locked = {name:row["sha256"] for name,row in lock["rows"].items()}
    if manifest["raw_source_hashes"] != locked:
        raise RuntimeError("Provider and 22-file raw-lock lineage disagree")
    if dataset == "BY2":
        report_path = registry.clean_root / "stages/CLEAN5_BY2_CONTROL_PROBES/PROBE_REPORT.json"
        contract = {"identity": {"dataset_id":"BY2","data_mode":"real_by2_raw"},
                    "window_contract": {"t_start":66.0,"t_end":340.0},
                    "time_contract": {"base_time":BASE_TIMES[dataset]}}
        contract_ref = {"source":"C-03 BY2 control provider manifest window/base_time", "sha256":manifest_ref["sha256"]}
    else:
        report_path = stage / "00_RAW_INVENTORY_AND_PROBES/PROBE_REPORT.json"
        relative = f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
        contract_path = registry.code_root / relative
        expected_bytes = subprocess.check_output(["git","show",f"{C02_COMMIT}:{relative}"],cwd=registry.code_root,
                            env={**os.environ,"GIT_OPTIONAL_LOCKS":"0"})
        if contract_path.read_bytes() != expected_bytes:
            raise RuntimeError("B/C must read unchanged C-02 v1 contract before D amendment")
        contract = load_yaml_mapping(contract_path)
        contract_ref = {"path":str(contract_path),"sha256":sha256(expected_bytes).hexdigest(),"commit":C02_COMMIT}
        if manifest["contract_paths_sha256"][relative] != contract_ref["sha256"] or contract["identity"]["raw_files_sha256"] != locked:
            raise RuntimeError("C-02 contract and C-03 provider/raw lineage disagree")
    report, report_ref = _checked_json(report_path,COMMON_REPORT_SHA256[dataset],root=registry.clean_root,role="C-01 common-coverage metadata")
    common = report["d_window_candidates"]["common_coverage"]
    if (common["first"],common["last"]) != COMMON_COVERAGE[dataset]:
        raise RuntimeError("Frozen three-stream common coverage mismatch")
    base = float(contract["time_contract"]["base_time"])
    if base != BASE_TIMES[dataset] or manifest["base_time"] != base:
        raise RuntimeError("Frozen R1 base time mismatch")
    occlusion = occlusion_ref = None
    if dataset == "BY2O":
        entry = manifest["occlusion_window"]
        occlusion, occlusion_ref = _checked_json(stage / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json",entry["sha256"],root=stage,role="C-02 occlusion metadata")
        if entry["sha256"] != contract["occlusion_window"]["report_sha256"]:
            raise RuntimeError("C-02 occlusion hash lineage mismatch")
    return {"stage":stage,"sequence":seq,"contract":contract,"base_time":base,
            "common_coverage":common,"occlusion_window":occlusion,"provider_manifest":manifest,
            "provider_checks":provider_checks,"lock":lock,
            "provenance":{"provider_manifest":manifest_ref,"provider_files":provider_checks,
                          "common_coverage_source":report_ref,"contract":contract_ref,
                          "occlusion_window":occlusion_ref,"c03_record_sha256":record_sha,
                          "raw_lock_path":str(lock["path"]),"raw_lock_sha256":lock["sha256"],
                          "raw_source_hashes":locked}}


def select_initialization(position_rows, a1_rows, *, base_time, t_start):
    """Apply C-02's unchanged first-valid-position/physical-A1 rules."""
    position = next((row for row in position_rows if str(row.get("pos_valid","")).strip().lower() in {"1","true"}
                     and float(providers.status_time_sys(row))-base_time>=t_start),None)
    yaw = next((row for row in a1_rows if float(row["aligned_time"])>=t_start),None)
    if position is None or yaw is None:
        raise RuntimeError("No valid first GNSS1 position or physical A1 yaw at/after event start")
    initpos = [float(position[key]) for key in ("pos_lat","pos_lon","pos_height")]
    body_candidate = float(yaw["yaw_baseline_deg"])
    yaw360 = (90.0-body_candidate)%360.0
    result = {"initpos":initpos,"initvel":[0,0,0],"initatt":[0,0,yaw360],
              "position_epoch_R1":float(providers.status_time_sys(position))-base_time,
              "yaw_epoch_R1":float(yaw["aligned_time"]),"yaw_ned_deg_0_360":yaw360,
              "yaw_wrap180_equivalent_deg":(yaw360+180.0)%360.0-180.0,
              "position_rule":"first GNSS1 status pos_valid epoch with sys_stamp - base_time >= t_start",
              "yaw_rule":"first constructed A1 aligned_time >= t_start; wrap360(90 - body_candidate)",
              "body_candidate_deg":body_candidate,"candidate_t_start":t_start,
              "rule_source":"configs/paper_rebuild/clean1_by2_clean_protocol.yaml#initialization",
              "trace_initialization":False,"method_specific_initialization":False,
              "zero_initial_velocity_roll_pitch_preserved":True}
    if not all(math.isfinite(value) for value in [*initpos,yaw360,result["position_epoch_R1"],result["yaw_epoch_R1"]]):
        raise RuntimeError("Nonfinite initialization input")
    return result


def prepare_initialization(sequence, *, contract, base_time, t_start):
    first,second = sequence.fix_root / "gnss1-status.csv",sequence.fix_root / "gnss2-status.csv"
    with open_probe_file(first,encoding="utf-8-sig",newline="") as handle:
        positions = list(csv.DictReader(handle))
    # C-03 retained no full physical A1 CSV. This is the same pure status helper
    # used by C-02 initialization; no provider files are written or regenerated.
    rows,audit = providers.build_a1_dual_diff_yaw_rows(first,second,base_time=base_time)
    result = select_initialization(positions,rows,base_time=base_time,t_start=t_start)
    if contract["initialization_contract"]["initvel"] != [0,0,0] or contract["initialization_contract"]["initatt"][:2] != [0,0]:
        raise RuntimeError("C-02 static velocity/roll/pitch initialization drifted")
    source = Path(registry_module_root()) / "src/legsa_gins/input_generation/status_yaw_builder.py"
    result.update(physical_a1_source="maintained pure status_yaw_builder.build_a1_dual_diff_yaw_rows",
                  physical_a1_source_sha256=sha256_file(source),physical_a1_audit=audit,
                  physical_a1_row_count=len(rows),provider_files_written=0)
    fields = ("initpos","initatt","position_epoch_R1","yaw_epoch_R1",
              "yaw_ned_deg_0_360","yaw_wrap180_equivalent_deg")
    return {**{key:result[key] for key in fields},
            "source_provenance":{key:value for key,value in result.items() if key not in fields}}


def registry_module_root():
    return Path(__file__).resolve().parents[4]


def requested_gap_relation(report, event, dataset):
    if dataset != "BY2H":
        return None
    start = (event.get("candidate_v2_window") or {}).get("t_start")
    sources = {}
    for key in ("imu_increment_holes","raw_go2_holes"):
        matches = []
        for gap in report[key]["holes"]:
            overlap = max(0.0,min(gap["t_end"],413.0)-max(gap["t_start"],411.0))
            if overlap>0:
                matches.append({"full_observed_gap":dict(gap),"overlap_with_requested_411_413_seconds":overlap,
                                "candidate_v2_start":start,
                                "v2_start_at_or_after_gap_end":None if start is None else start>=gap["t_end"]})
        sources[key] = matches
    return {"diagnostic_only":True,"requested_interval_R1":[411.0,413.0],
            "interval_is_not_a_redefined_gap":True,"source_gaps":sources,
            "used_to_adjust_window":False}


def event_worker(args, registry, dataset, state, a4):
    prepared = metadata_inputs(registry,dataset)
    stage,seq = prepared["stage"],prepared["sequence"]
    diag_root = stage / "06_ALIGNMENT_DIAGNOSTICS"
    validate_checkpoint(_read(diag_root / "00_AUDIT/pre_event_CHECKPOINT.json"),phase="pre_event",lock=prepared["lock"])
    if _read(diag_root / "00_AUDIT/pre_event_STRACE_AUDIT.json").get("pass") is not True:
        raise RuntimeError("Event worker requires a passing independent pre-event strace checkpoint")
    provenance = {"first_code_freeze_commit":args.code_freeze_commit,**state,
                  "human_protocol_statement":event_window.HUMAN_STATEMENT,
                  "input_provenance":prepared["provenance"],"A4_revalidation_gate":a4,
                  "data_mode":seq.data_mode,"synthetic_data_used":False,"semisynthetic_data_used":False,
                  "trace_used_online":False,"old_runtime_input_count":0,
                  "provider_generation_count":0,"solver_execution_count":0,"evaluator_execution_count":0,
                  "config_hash":sha256(json.dumps(event_window.constants(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()}
    event = None
    try:
        entries = prepared["provider_manifest"]["artifacts"]
        speeds = event_window.load_speed_inputs(entries["gnss_runtime_input"]["path"],entries["go2_horizontal_velocity_prior"]["path"])
        speed_arguments = {key:speeds[key] for key in ("gnss_times","gnss_speeds","body_times","body_speeds")}
        imu_times = diagnostics.read_imu_increment_times(entries["imu_runtime_input"]["path"])
        kick = event_window.detect_kick_report(seq.body_path,base_time=prepared["base_time"],diagnostic_dir=diag_root)
        raw_times = diagnostics.read_raw_go2_times(seq.body_path,base_time=prepared["base_time"])
        holes = diagnostics.summarize_time_holes(imu_times)
        event = event_window.compute_event_window(dataset_id=dataset,**speed_arguments,
                    common_coverage=prepared["common_coverage"],kick_report=kick,
                    v1_window={key:prepared["contract"]["window_contract"][key] for key in ("t_start","t_end")},
                    first_imu_hole_end=holes["first_hole_end"],occlusion_window=prepared["occlusion_window"])
        report = diagnostics.diagnose(dataset_id=dataset,imu_times=imu_times,raw_body_times=raw_times,
                    **speed_arguments,common_coverage=prepared["common_coverage"],v2_window=event["v2_window"])
        relation = requested_gap_relation(report,event,dataset)
        if relation is not None:
            report["by2h_411_413_gap_diagnostic"] = relation
        event["initialization_v2"] = None
        if event["ready_for_v2_contract"] and dataset != "BY2":
            try:
                event["initialization_v2"] = prepare_initialization(seq,contract=prepared["contract"],
                                                base_time=prepared["base_time"],t_start=event["v2_window"]["t_start"])
            except Exception as exc:
                event.update(status="INITIALIZATION_V2_FAILED",ready_for_v2_contract=False,v2_window=None)
                event["failures"].append(f"{type(exc).__name__}: {exc}")
        event.update(provenance)
        report.update(provenance)
        text = diagnostics.markdown_report(report)
        if relation is not None:
            text += "\nBY2H requested 411–413 s interval is compared with each full observed gap, without replacing its endpoints.\n"
            for source,matches in relation["source_gaps"].items():
                for item in matches:
                    gap=item["full_observed_gap"]
                    text += (f"{source}: full gap {gap['t_start']:.12g} .. {gap['t_end']:.12g} s; "
                             f"overlap with [411,413] {item['overlap_with_requested_411_413_seconds']:.12g} s; "
                             f"v2 start >= gap end: {item['v2_start_at_or_after_gap_end']}.\n")
    except Exception as exc:
        event = {**(event or {}),"dataset_id":dataset,"status":"TECHNICAL_FAILURE","ready_for_v2_contract":False,
                 "v2_window":None,"initialization_v2":None,"failures":[f"{type(exc).__name__}: {exc}"],**provenance}
        report = {"dataset_id":dataset,"first_line":diagnostics.REPORT_FIRST_LINE,"diagnostic_only":True,
                  "status":"UNAVAILABLE","error":f"{type(exc).__name__}: {exc}",**provenance}
        text = diagnostics.REPORT_FIRST_LINE+"\n\nUnavailable: "+report["error"]+"\n"
    write_json_exclusive(stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json",event)
    write_json_exclusive(diag_root / "ALIGNMENT_DIAGNOSTICS.json",report)
    _write_text(diag_root / "ALIGNMENT_DIAGNOSTICS.md",text)
    print(json.dumps({"dataset_id":dataset,"event_status":event["status"],"ready_for_v2_contract":event["ready_for_v2_contract"]}),flush=True)
    return event


def checkpoint_worker(registry,dataset,phase):
    prepared = metadata_inputs(registry,dataset)
    lock,seq = prepared["lock"],prepared["sequence"]
    hashes = verify_raw_sources(registry.raw_root,sorted(lock["rows"]),lock["rows"])
    payload = {"schema_version":"paper_rebuild.final_v23_external_raw_checkpoint.v1","audit_phase":phase,
               "dataset_id":dataset,"raw_hash_lock_sha256":lock["sha256"],"expected":22,"verified":len(hashes),
               "missing":0,"mismatch":0,"symlink_escape":0,"raw_mutation":0,"passed":True,
               "trace_read_role":"outer_raw_integrity_hash_audit_only","trace_provider_or_solver_input":False,
               "verified_hashes":hashes,"synthetic_data_used":False,"semisynthetic_data_used":False}
    validate_checkpoint(payload,phase=phase,lock=lock)
    write_json_exclusive(prepared["stage"] / "06_ALIGNMENT_DIAGNOSTICS/00_AUDIT" / f"{phase}_CHECKPOINT.json",payload)


def phase_audit(log, *, registry, dataset, phase, prepared):
    records = audited_open_records(log,registry.code_root)
    raw_paths = {registry.raw_root / name for name in prepared["lock"]["rows"]}
    seq,stage = prepared["sequence"],prepared["stage"]
    checkpoint = phase != "events"
    admitted = raw_paths if checkpoint else {seq.body_path,seq.fix_root/"gnss1-status.csv",seq.fix_root/"gnss2-status.csv"}
    raw = audit_records(records,registry.raw_root,admitted,checkpoint_phase=checkpoint)
    roots = [stage / "06_ALIGNMENT_DIAGNOSTICS"]
    if not checkpoint:
        roots.append(stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json")
    writes = write_scope_audit(records,raw_root=registry.raw_root,clean_root=registry.clean_root,allowed_write_roots=roots)
    forbidden = {"trace":sum(Path(row["path"]).name.lower().startswith("trace_") for row in records),
                 "bag":sum(Path(row["path"]).suffix.lower()==".bag" for row in records),
                 "fpl":sum(Path(row["path"]).suffix.lower()==".fpl" for row in records)}
    passed = bool(records) and raw["pass"] and writes["pass"] and (checkpoint or not any(forbidden.values()))
    return {"pass":passed,"phase":phase,"raw_audit":raw,"write_audit":writes,
            "raw_open_count":raw["raw_open_count"],"raw_write_open_count":writes["raw_write_open_count"],
            "forbidden_open_counts":forbidden,"strace_sha256":sha256_file(log),"session_count":1,
            "trace_role":"outer_raw_integrity_hash_audit_only" if checkpoint else "not_opened"}


def run_phase(args,registry,dataset,phase,prepared):
    audit_root = prepared["stage"] / "06_ALIGNMENT_DIAGNOSTICS/00_AUDIT"
    log = audit_root / f"{phase}_OPENAT.strace"
    command = [shutil.which("strace") or "strace","-f","-qq","-yy","-s","4096","-e","trace=openat","-o",str(log),
               sys.executable,"-B",str(registry.code_root/"scripts/paper_rebuild/clean5_prepare_event_window_v2.py"),
               "--code-root",str(registry.code_root),"--code-freeze-commit",args.code_freeze_commit,
               "--paths-config",str(args.paths_config),"--_worker",phase,"--_sequence",dataset]
    if args.executable:
        command += ["--executable",str(args.executable)]
    completed = run_process_group(command,cwd=registry.code_root,timeout_seconds=1800,
                                  timeout_message=f"C-04b {phase} timed out",launch_failure_message=f"Cannot launch C-04b {phase}")
    _write_text(audit_root / f"{phase}_stdout.log",completed.stdout)
    _write_text(audit_root / f"{phase}_stderr.log",completed.stderr)
    try:
        audit = phase_audit(log,registry=registry,dataset=dataset,phase=phase,prepared=prepared)
    except Exception as exc:
        audit = {"pass":False,"phase":phase,"error":str(exc),"raw_open_count":None,
                 "forbidden_open_counts":{"trace":None,"bag":None,"fpl":None},"raw_write_open_count":None}
    audit.update(worker_exit_code=completed.returncode,stderr_tail="\n".join(completed.stderr.splitlines()[-30:]))
    audit["pass"] = audit["pass"] and completed.returncode==0
    write_json_exclusive(audit_root / f"{phase}_STRACE_AUDIT.json",audit)
    return audit


def prepare_sequence(args,registry,dataset,state,a4):
    prepared = metadata_inputs(registry,dataset)
    stage = prepared["stage"]
    diag_root = stage / "06_ALIGNMENT_DIAGNOSTICS"
    if diag_root.exists() or (stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json").exists():
        raise FileExistsError("C-04b event/diagnostic attempt already exists; no overwrite or automatic retry")
    diag_root.mkdir(exist_ok=False)
    audit_root = diag_root / "00_AUDIT"
    audit_root.mkdir(exist_ok=False)
    (stage / "01_SEQUENCE_CONTRACT").mkdir(exist_ok=True)
    write_json_exclusive(audit_root / "PREFLIGHT.json",{**state,"A4_revalidation_gate":a4,"input_provenance":prepared["provenance"]})
    pre_audit = run_phase(args,registry,dataset,"pre_event",prepared)
    if not pre_audit["pass"]:
        raise RuntimeError("Pre-event independent 22-file raw checkpoint/strace failed; event worker not launched")
    pre = _read(audit_root / "pre_event_CHECKPOINT.json")
    validate_checkpoint(pre,phase="pre_event",lock=prepared["lock"])
    event_audit = None
    try:
        event_audit = run_phase(args,registry,dataset,"events",prepared)
    finally:
        post_audit = run_phase(args,registry,dataset,"post_event",prepared)
    failures = []
    event_path = stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json"
    event = _read(event_path) if event_path.is_file() else {"status":"UNAVAILABLE","ready_for_v2_contract":False}
    post = None
    try:
        post = _read(audit_root / "post_event_CHECKPOINT.json")
        validate_checkpoint(post,phase="post_event",lock=prepared["lock"])
        if post["verified_hashes"] != pre["verified_hashes"]:
            raise RuntimeError("Raw identity changed between event checkpoints")
        after = metadata_inputs(registry,dataset)
        if after["provider_checks"] != prepared["provider_checks"] or after["provenance"] != prepared["provenance"]:
            raise RuntimeError("Frozen provider/metadata identity changed")
        if _published_source(args,registry) != {key:value for key,value in state.items() if key!="frozen_executable"}:
            raise RuntimeError("Published code state changed during event computation")
        verify_executable(state["frozen_executable"]["path"],registry.code_root)
    except Exception as exc:
        failures.append(str(exc))
    passed = (event.get("ready_for_v2_contract") is True and event_audit is not None and event_audit["pass"]
              and post_audit["pass"] and not failures)
    gate = {"status":"PASS" if passed else "FAIL_EVENT_PREPARATION","passed":passed,"dataset_id":dataset,
            "event_status":event["status"],"event_path":str(event_path),
            "event_sha256":sha256_file(event_path) if event_path.is_file() else None,
            "pre_checkpoint":pre,"post_checkpoint":post,"pre_event_strace":pre_audit,
            "event_strace":event_audit,"post_event_strace":post_audit,"failures":failures,
            "provider_post_checked":not failures,"A4_revalidation_gate":a4,**state}
    write_json_exclusive(audit_root / "EVENT_PHASE_GATE.json",gate)
    print(json.dumps({"dataset_id":dataset,"event_status":event["status"],"event_phase_gate":gate["status"]}),flush=True)
    return gate


def prepare_all(args,registry,state,a4):
    records = []
    for dataset in ORDER:
        try:
            record = prepare_sequence(args,registry,dataset,state,a4)
        except Exception as exc:
            record = {"dataset_id":dataset,"passed":False,"status":"TECHNICAL_FAILURE",
                      "error":f"{type(exc).__name__}: {exc}"}
        records.append(record)
        if not records[-1]["passed"]:
            break
    passed = len(records)==3 and all(row["passed"] for row in records)
    gate = {"status":"PASS" if passed else "STOPPED_BEFORE_CONTRACT_V2","passed":passed,
            "sequence_order":list(ORDER),"sequences_completed":[row["dataset_id"] for row in records],
            "not_executed_sequences":list(ORDER[len(records):]),"sequence_gates":records,
            "ready_for_contract_amendment":passed,"contracts_written":0,
            "human_protocol_statement":event_window.HUMAN_STATEMENT,"A4_revalidation_gate":a4,**state}
    root = stage_root(registry,"BY2") / "06_ALIGNMENT_DIAGNOSTICS"
    if root.is_dir():
        write_json_exclusive(root / "B_C_PREPARATION_GATE.json",gate)
    print(json.dumps({"preparation_gate":gate["status"],"sequences_completed":gate["sequences_completed"],
                      "not_executed_sequences":gate["not_executed_sequences"]}),flush=True)
    return 0 if passed else 3


def main(argv=None,*,execution_script=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root",type=Path,required=True)
    parser.add_argument("--code-freeze-commit",required=True)
    parser.add_argument("--paths-config",type=Path,required=True)
    parser.add_argument("--executable",type=Path)
    parser.add_argument("--_worker",choices=("pre_event","events","post_event"),help=argparse.SUPPRESS)
    parser.add_argument("--_sequence",choices=ORDER,help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    os.environ.update(PYTHONDONTWRITEBYTECODE="1",GIT_OPTIONAL_LOCKS="0")
    try:
        root = args.code_root.resolve(strict=True)
        if execution_script is not None and Path(execution_script).resolve()!=root / "scripts/paper_rebuild/clean5_prepare_event_window_v2.py":
            raise RuntimeError("Event preparation CLI must come from the published code root")
        registry = load_registry(root / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml",args.paths_config)
        state = _published_source(args,registry)
        a4 = require_revalidation_gate(registry,args.code_freeze_commit)
        state["frozen_executable"] = verify_executable(args.executable or root / EXECUTABLE_RELATIVE,root)
        if not shutil.which("strace"):
            raise RuntimeError("strace is required before any raw input operation")
        if args._worker:
            if args._sequence is None:
                raise RuntimeError("Internal event/checkpoint worker requires sequence")
            require_prior_sequence_gates(registry,args._sequence,args.code_freeze_commit)
            if args._worker == "events":
                seq = registry.sequences[args._sequence]
                admitted = {seq.body_path,seq.fix_root/"gnss1-status.csv",seq.fix_root/"gnss2-status.csv"}
                with forbidden_path_guard(registry.raw_root,admitted):
                    event_worker(args,registry,args._sequence,state,a4)
            else:
                checkpoint_worker(registry,args._sequence,args._worker)
            return 0
        if args._sequence is not None:
            raise RuntimeError("Sequence selection is internal; public execution always uses BY2, BY2H, BY2O")
        return prepare_all(args,registry,state,a4)
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        return 2
