#!/usr/bin/env python3
"""Bounded loader completion: reuse stored BY2; parse only BY2H and BY2O.

No compile, prepare, GIEngine, navigation or evaluator command exists here.
The imported runner supplies pinned I/O, trace-audit and subprocess helpers only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import traceback
import arc_native_real as h

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007"
PLAN = D / "ARC_NATIVE_LOADER_FINISH_PLAN.json"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_native_loader_finish.py"
STAGE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_TELEMETRY_REPAIR01"
PREPARE_COMMIT = "82e56f07dfc3358e437450014ca0849ce08ec195"
BUDGET = dict(checker_compiles=0, prepare_calls=0, reused_by2_validations=1,
              loader_calls=2, arc_event_csv_parses=2, native_calls=0, evaluator_calls=0,
              provider_payload_reads=0, raw_reads=0, reference_reads=0,
              loader_timeout_s=60)
OWN_ATTEMPT = None
COUNTS = dict(checker_compiles=0, prepare_calls=0, reused_by2_validations=0,
              loader_calls=0, arc_event_csv_parses=0, native_calls=0, evaluator_calls=0)


def register(commit):
    reg = h.read(PLAN)
    h.require(reg["schema"] == "arc_native_loader.finish/v1" and
              reg["status"] == "REGISTERED_READY_SINGLE_EXECUTION", "draft not executable")
    h.require(reg["budgets"] == BUDGET and reg["prepare_registration_commit"] == PREPARE_COMMIT,
              "fixed unused-call budget and prepared identity")
    h.require(SCRIPT in reg["source_pins"], "finish script must be pinned")
    h.require(PLAN.read_bytes() == subprocess.check_output(
        ["git", "show", commit+":"+PLAN.relative_to(ROOT).as_posix()], cwd=ROOT), "unfrozen plan")
    h.source_check(reg, commit)
    aliases = reg["aliases"]
    scratch = ROOT.parent.parent/"LegSA-GINS-SCRATCH"
    h.require(h.expand("<CODE_ROOT>", aliases) == ROOT and
              h.expand("<SCRATCH_ROOT>", aliases) == scratch.resolve(), "fixed workspace")
    h.require(reg["stage"] == "<SCRATCH_ROOT>/"+STAGE_REL, "fixed prepared stage")
    stage = h.expand(reg["stage"], aliases)
    h.require(stage == scratch/STAGE_REL, "fixed stage alias")
    h.require(reg["output_substage"] == "LOADER_COMPLETION01", "single completion substage")
    return reg, aliases, stage


def check_echo(run, echo, parsed_counts, aliases):
    sid = run["sequence_id"]
    blocks = {"BY2": 274, "BY2H": 270, "BY2O": 377}[sid]
    h.require(run["block_count"] == blocks and parsed_counts ==
              {"source_rows": 2*blocks, "source_blocks": blocks}, "parsed full denominator")
    expected = {"run_id": sid+"__ARC_EMPTY_MODEL", "arc_clone_mode": "NULL_ARC_DIAGNOSTIC",
                "arc_source_events_path": str(h.expand(run["events"]["path"], aliases)),
                "arc_source_events_sha256": run["events"]["sha256"],
                "arc_schedule_manifest_sha256": run["manifest"]["sha256"],
                "arc_source_time_scale_id": "UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS",
                "arc_source_time_mapping_id": sid+":SEALED_RAWX_UTC_AND_CALIBRATED_IMU_BASE_V1",
                "arc_availability_policy": "source_time_replay_assumption",
                "arc_actual_available_time": None, "arc_phase_state_cross": "UNKNOWN",
                "heading_source_policy": "pvt_priority_control", "dual_yaw_prediction_model": "euler_yaw"}
    expected.update({k: run["metadata_fields"][k] for k in
                     ("stage_id", "protocol_id", "case_id", "run_id", "run_label")})
    for key, value in expected.items():
        h.require(key in echo and echo[key] == value, "static ARC/metadata echo mismatch: "+key)
    original = h.read(h.expand(run["original_checker_echo"]["path"], aliases))
    # Production loadYamlLike assigns options.phase = options.stage_id (line 462).
    # Both are checked, but stage-derived metadata is not an invariant science field.
    h.require(original.get("phase") == original.get("stage_id") and
              echo.get("phase") == echo.get("stage_id") and "phase" in original and "phase" in echo,
              "phase must equal its own stage_id in original and new echoes")
    keys = sorted((set(h.SCIENCE_FIELDS) - {"phase"}) |
                  {key for key in original if key.startswith("init_")})
    for key in keys:
        h.require(key in original and key in echo and original[key] == echo[key],
                  "original scientific field changed: "+key)
    actual_inputs = dict(echo["actual_solver_input_paths"])
    h.require(actual_inputs.pop("arc_source_time_metadata_only") == expected["arc_source_events_path"],
              "ARC metadata path role")
    paths = {str(h.expand(p["path"], aliases)) for p in run["providers"].values()}
    paths.add(str(h.expand(run["carrier"]["path"], aliases)))
    h.require(set(actual_inputs.values()) == paths, "inherited scientific provider path identity")
    return dict(sequence_id=sid, config=run["config"], arc_and_metadata_echo=expected,
                original_scientific_echo={k: echo[k] for k in keys},
                derived_phase_check=dict(original_stage=original["stage_id"],original_phase=original["phase"],
                                         new_stage=echo["stage_id"],new_phase=echo["phase"]),
                production_csv_parse_counts=parsed_counts, event_execution_qualified=False)


def finish(commit):
    global OWN_ATTEMPT
    reg, aliases, stage = register(commit)
    prepared = h.read(stage/"PREPARED.json")
    h.require(prepared["status"] == "PREPARED_METADATA_ONLY_NO_NATIVE" and
              prepared["plan_sha256"] == h.digest(stage/"PLAN.json"), "prepared seal")
    plan = h.read(stage/"PLAN.json")
    h.require(plan["schema"] == "arc_native_telemetry.prepared/v1" and
              plan["registration_commit"] == PREPARE_COMMIT and plan["aliases"] == aliases,
              "reuse already successful preparation")
    h.require(tuple(r["sequence_id"] for r in plan["runs"]) == ("BY2","BY2H","BY2O") and
              plan["total_blocks"] == 921 and plan["total_endpoints"] == 1842, "fixed full denominator")
    metadata = [stage/"PREPARED.json", stage/"PLAN.json"]
    for run in plan["runs"]:
        for key in ("config","events","manifest","original_checker_echo"):
            metadata.append(h.check(run[key], aliases))
    for role in ("library","binary"):
        h.require(h.expand(plan[role]["path"], aliases) == h.expand(reg[role]["path"], aliases) and
                  plan[role]["sha256"] == reg[role]["sha256"], "unchanged "+role)
        metadata.append(h.check(reg[role], aliases))
    metadata.extend(h.check(item, aliases) for item in reg["preserved_artifact_pins"])
    pinned_paths = {h.expand(item["path"], aliases) for item in reg["preserved_artifact_pins"]}
    checker = h.check(reg["checker"], aliases)
    previous = stage/"LOADER_CHECK_REPAIR01"
    h.require(checker == previous/"config_check" and checker in pinned_paths, "reuse exact sealed checker")
    compile_result = h.read(previous/"COMPILE/RESULT.json")
    h.require(previous/"COMPILE/RESULT.json" in pinned_paths and
              compile_result["returncode"] == 0 and not compile_result["timed_out"] and
              compile_result["audit_passed"], "existing successful compile receipt")
    metadata.append(h.check(reg["strace"], aliases))
    h.require(h.expand(reg["strace"]["path"], aliases) == Path("/usr/bin/strace"), "fixed tracer")
    stored = previous/"BY2"
    stored_paths = [stored/name for name in
                    ("RESULT.json","INVOCATION.json","stdout.log","ECHO/RUN_MANIFEST.json",
                     "ACCESS_AUDIT.json","OPENAT.strace")]
    h.require(set(stored_paths).issubset(pinned_paths), "all successful BY2 artifacts frozen")
    before = {str(p): h.digest(p) for p in metadata}
    out = stage/"LOADER_COMPLETION01"
    h.require(not out.exists(), "completion attempt exists; no retry")
    out.mkdir(); OWN_ATTEMPT = out
    h.emit(out/"REGISTERED_PLAN.json", reg)
    h.emit(out/"INPUT_PINS.json", dict(files=before,provider_payload_status="INHERITED_NOT_REHASHED"))
    COUNTS["reused_by2_validations"] += 1
    old_result = h.read(stored/"RESULT.json")
    old_audit = h.read(stored/"ACCESS_AUDIT.json")
    h.require(old_result["returncode"] == 0 and not old_result["timed_out"] and
              old_result["audit_passed"] and old_audit["passed"], "stored BY2 process must have succeeded")
    old_command = h.read(stored/"INVOCATION.json")["argv"]
    old_inputs = [str(checker),str(h.expand(plan["runs"][0]["config"]["path"],aliases)),str(stored/"ECHO")]
    h.require(old_command[-3:] == old_inputs, "stored BY2 command/config identity")
    first = check_echo(plan["runs"][0], h.read(stored/"ECHO/RUN_MANIFEST.json"),
                       h.read(stored/"stdout.log"), aliases)
    first.update(source="REUSED_SUCCESSFUL_BY2_PROCESS_NO_RERUN", echo=h.pin(stored/"ECHO/RUN_MANIFEST.json"))
    records = [first]
    h.emit(out/"BY2_STORED_VALIDATION.json", first)
    for ordinal,run in enumerate(plan["runs"][1:], 1):
        sid = run["sequence_id"]
        config = h.expand(run["config"]["path"],aliases)
        dest = out/sid
        COUNTS["loader_calls"] += 1; COUNTS["arc_event_csv_parses"] += 1
        result = h.launch([checker,config,dest/"ECHO"],dest,60,aliases,
                          [checker,config,h.expand(run["events"]["path"],aliases)],"LOADER_"+sid,ordinal)
        record = check_echo(run,h.read(dest/"ECHO/RUN_MANIFEST.json"),h.read(dest/"stdout.log"),aliases)
        record.update(source="NEW_REMAINING_LOADER_PROCESS",echo=h.pin(dest/"ECHO/RUN_MANIFEST.json"),result=result)
        records.append(record)
    h.source_check(reg,commit)
    h.require(all(h.digest(Path(path)) == digest for path,digest in before.items()),
              "metadata/binary/preserved artifact changed")
    h.emit(out/"COMPLETE.json", dict(status="COMPLETE_THREE_LOADER_QUALIFICATIONS_ONE_REUSED_TWO_NEW",
           registration_commit=commit,prepare_registration_commit=PREPARE_COMMIT,
           prepared_plan_sha256=before[str(stage/"PLAN.json")],checker=reg["checker"],
           registered_budget=BUDGET,actual_calls=COUNTS,records=records,source_pins=reg["source_pins"],
           preserved_and_metadata_pins=before,provider_payload_pins="INHERITED_NOT_REHASHED_THIS_STAGE",
           native_calls=0,next_gate="Separate registered six-call matched native plan and provider hash budget"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--registration-commit",required=True)
    args=parser.parse_args()
    try:
        finish(args.registration_commit)
    except BaseException as exc:
        if OWN_ATTEMPT is not None and not (OWN_ATTEMPT/"FAILED.json").exists():
            h.emit(OWN_ATTEMPT/"FAILED.json",dict(error=repr(exc),traceback=traceback.format_exc(),
                   actual_calls=COUNTS,first_failure_preserved=True,retry_allowed=False))
        raise


if __name__ == "__main__":
    main()
