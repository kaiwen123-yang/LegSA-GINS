#!/usr/bin/env python3
"""Registered ARC loader-only gate; no scientific provider payload or native replay.

This file deliberately has no native/evaluate command. A later separately
registered runner must re-hash the inherited provider payloads before/after the
six real calls. Here pins for those payloads remain inherited declarations.
The checker loads configuration and parses the generated metadata event CSV.
It does not construct GIEngine, replay navigation or read scientific providers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007"
PLAN = D / "ARC_NATIVE_LOADER_PLAN.json"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_native_real.py"
STAGE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_TELEMETRY_ATTEMPT01"
SEQUENCES = ("BY2", "BY2H", "BY2O")
BUDGET = {"checker_compiles": 1, "loader_calls": 3, "arc_event_csv_parses": 3, "native_calls": 0,
          "evaluator_calls": 0, "provider_payload_reads": 0,
          "raw_reads": 0, "reference_reads": 0, "compile_timeout_s": 60,
          "loader_timeout_s": 60}
SCIENCE_FIELDS = (
    "clean1_formal_mode", "clean_final_v23_parity_mode", "data_mode", "phase",
    "algorithm_id", "runtime_contract", "ablation_variant", "starttime", "endtime",
    "imudatalen", "imudatarate", "antlever_m", "common_initialization_source",
    "propagation_imu_source", "measurement_update_order", "correlation_time_h",
    "angle_random_walk_deg_sqrt_h", "velocity_random_walk_mps_sqrt_h",
    "gyro_bias_std_deg_h", "accel_bias_std_mgal", "gyro_scale_std_ppm", "accel_scale_std_ppm",
    "enable_dual_yaw_update", "enable_receiver_velocity_update", "raw_doppler_mode",
    "go2_attitude_weak_prior_enabled", "go2_velocity_prior_diagnostic_enabled",
    "go2_horizontal_velocity_prior_enabled", "go2_horizontal_velocity_prior_mode",
    "go2_horizontal_velocity_prior_source_aware_enabled", "formal_go2_velocity_prior",
    "dual_antenna_measurement_model", "baseline3d_source", "external_carrier_body_vector_frd_m",
    "heading_source_policy", "dual_yaw_prediction_model", "source_aware_source_configs",
    "source_caps", "source_aware_policy_version", "source_aware_mode")
CHECKER = r"""
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/factors/arc_source_events.hpp"
#include <iostream>
int main(int argc,char** argv) {
  if(argc!=3) return 2;
  try {
    const auto options=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);
    const auto events=legsa_v23_port_core::readArcSourceEvents(options.arc_clone_config);
    std::size_t blocks=0;
    for(const auto& event:events) if(event.role=="START") ++blocks;
    legsa_v23_port_core::FileSaver::writeRunManifest(argv[2],options);
    std::cout << "{\"source_rows\":" << events.size()
              << ",\"source_blocks\":" << blocks << "}\n";
    return 0;
  } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
"""
OWN_ATTEMPT = None


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def emit(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def expand(text, aliases):
    value = str(text)
    for alias, root in aliases.items():
        value = value.replace(alias, root)
    require("<" not in value and ">" not in value, "unresolved alias")
    path = Path(value)
    require(path.is_absolute(), "absolute resolved path required")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink input forbidden")
    return path.resolve()


def check(pin, aliases):
    path = expand(pin["path"], aliases)
    require(path.is_file() and digest(path) == pin["sha256"], "metadata/binary pin changed: "+str(path))
    return path


def pin(path):
    return {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}


def source_check(reg, commit):
    require(SCRIPT in reg["source_pins"], "runner must be source-pinned")
    for relative, expected in reg["source_pins"].items():
        path = (ROOT/relative).resolve()
        require(path.is_relative_to(ROOT), "source pin outside checkout")
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == expected, "source pin changed: "+relative)
        frozen = subprocess.check_output(["git", "show", commit+":"+relative], cwd=ROOT)
        require(payload == frozen, "source not frozen at registration: "+relative)


def registration(args):
    require(args.plan.resolve() == PLAN.resolve(), "fixed loader registration path")
    reg = read(args.plan)
    require(reg["schema"] == "arc_native_loader.registration/v1" and
            reg["status"] == "REGISTERED_READY_SINGLE_EXECUTION", "draft is not executable")
    require(reg["budgets"] == BUDGET and reg["stage"] == "<SCRATCH_ROOT>/"+STAGE_REL,
            "registered fixed stage/budget")
    require(args.plan.read_bytes() == subprocess.check_output(
        ["git", "show", args.registration_commit+":"+args.plan.relative_to(ROOT).as_posix()], cwd=ROOT),
        "registration plan not committed")
    source_check(reg, args.registration_commit)
    aliases = reg["aliases"]
    scratch = ROOT.parent.parent/"LegSA-GINS-SCRATCH"
    require(expand("<CODE_ROOT>", aliases) == ROOT and
            expand("<SCRATCH_ROOT>", aliases) == scratch.resolve(), "fixed checkout/scratch identity")
    stage = expand(reg["stage"], aliases)
    require(stage == (scratch/STAGE_REL).resolve(), "stage alias escape")
    return reg, aliases, stage


def audit_openat(log, aliases, allowed, output):
    """Check successful protected-tree opens; no raw/reference/provider payload.

    Compiler/system runtime headers/libraries outside the named research roots
    remain normal build dependencies. This is not a system-wide sandbox claim.
    """
    protected = {ROOT, expand("<SCRATCH_ROOT>", aliases)}
    for key in ("<CLEAN_ROOT>", "<RAW_ROOT>", "<EXT_REPRO_ROOT>"):
        if key in aliases:
            protected.add(expand(key, aliases))
    allowed = {p.resolve() for p in allowed}
    records, bad, pending = [], [], {}
    for line in log.read_text(errors="replace").splitlines():
        if "openat(" not in line and "openat resumed>" not in line:
            continue
        pid_match = re.match(r"\s*(\d+)\s+", line)
        pid = pid_match.group(1) if pid_match else "root"
        if "<unfinished ...>" in line:
            require(pid not in pending, "nested unfinished openat")
            pending[pid] = line
            continue
        if "openat resumed>" in line:
            require(pid in pending, "resumed openat without origin")
            line = pending.pop(pid)+line
        if re.search(r"= -1\b", line):
            continue
        # -yy prints the resolved successful fd path, including openat-relative names.
        match = re.search(r"= [0-9]+<([^>]+)>", line)
        if match is None:
            raise ValueError("unresolved successful openat in audit: "+line)
        path = Path(match.group(1).removesuffix(" (deleted)")).resolve()
        if not any(path == q or path.is_relative_to(q) for q in protected):
            continue
        writing = any(flag in line for flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC"))
        directory_only = "O_DIRECTORY" in line and any(path in p.parents for p in allowed)
        ok = (path == output or path.is_relative_to(output) or
              (not writing and (path in allowed or directory_only)))
        records.append({"path": str(path), "writing": writing, "allowed": ok})
        if not ok:
            bad.append(records[-1])
    require(not pending, "unresolved unfinished openat at process end")
    return {"passed": not bad, "protected_opens": records, "unexpected": bad,
            "scope": "successful openat inside frozen research roots"}


def launch(command, destination, timeout_s, aliases, allowed, role, ordinal, output_scope=None):
    destination.mkdir()
    trace = destination/"OPENAT.strace"
    argv = ["/usr/bin/strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve",
            "-o", str(trace), *map(str, command)]
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", LEGSA_ARC_NATIVE_TELEMETRY="0")
    # Reserve before process start. The parent attempt directory itself is exclusive.
    emit(destination/"INVOCATION.json", {"ordinal": ordinal, "role": role, "argv": argv,
         "timeout_s": timeout_s, "native_calls": 0, "retry": 0})
    before = time.monotonic()
    with (destination/"stdout.log").open("x") as out, (destination/"stderr.log").open("x") as err:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err, env=env, start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    audit = audit_openat(trace, aliases, allowed, destination if output_scope is None else output_scope)
    emit(destination/"ACCESS_AUDIT.json", audit)
    result = {"returncode": code, "timed_out": timed_out, "elapsed_s": time.monotonic()-before,
              "audit_passed": audit["passed"], "retry": 0}
    emit(destination/"RESULT.json", result)
    require(code == 0 and not timed_out and audit["passed"], "first loader-stage failure; preserve logs, no retry")
    print(role, "PASS", flush=True)
    return result


def loader(args):
    global OWN_ATTEMPT
    reg, aliases, stage = registration(args)
    prepared = read(stage/"PREPARED.json")
    require(prepared["plan_sha256"] == digest(stage/"PLAN.json"), "prepared plan seal")
    plan = read(stage/"PLAN.json")
    require(plan["schema"] == "arc_native_telemetry.prepared/v1", "prepared schema")
    prepare_commit = args.registration_commit if reg["prepare_registration_commit"] == "SELF" else reg["prepare_registration_commit"]
    require(plan["registration_commit"] == prepare_commit, "prepared registration identity")
    require(tuple(r["sequence_id"] for r in plan["runs"]) == SEQUENCES, "exactly three shared configs")
    require(plan["aliases"] == aliases, "loader aliases differ from metadata preparation")
    require(plan["total_blocks"] == 921 and plan["total_endpoints"] == 1842, "full denominator")
    for role in ("library", "binary"):
        require(expand(plan[role]["path"], aliases) == expand(reg[role]["path"], aliases) and
                plan[role]["sha256"] == reg[role]["sha256"], "frozen newly built "+role)
        if "size_bytes" in plan[role] and "size_bytes" in reg[role]:
            require(plan[role]["size_bytes"] == reg[role]["size_bytes"], role+" size pin differs")
    library = check(reg["library"], aliases)
    check(reg["binary"], aliases)  # Pin only; this gate never launches it.
    compiler = check(reg["compiler"], aliases)
    check(reg["strace"], aliases)
    require(compiler == Path("/usr/bin/g++").resolve() and
            expand(reg["strace"]["path"], aliases) == Path("/usr/bin/strace"), "fixed build/instrumentation tools")
    metadata = [stage/"PLAN.json", stage/"PREPARED.json"]
    configs = []
    for run in plan["runs"]:
        sid = run["sequence_id"]
        require(run["run_id"] == sid+"__ARC_EMPTY_MODEL", "same scientific run per arm")
        config = check(run["config"], aliases);configs.append(config)
        metadata.extend([config, check(run["events"], aliases), check(run["manifest"], aliases),
                         check(run["original_checker_echo"], aliases)])
    before = {str(p): digest(p) for p in metadata}
    out = stage/"LOADER_CHECK"
    require(not out.exists(), "loader attempt already exists; no retry or alternate stage")
    out.mkdir();OWN_ATTEMPT = out
    emit(out/"REGISTERED_PLAN.json", reg)
    emit(out/"INPUT_METADATA_PINS.json", {"files": before,
         "provider_payload_pins": "INHERITED_FROM_OLD_SEAL_NOT_REHASHED_THIS_STAGE",
         "provider_payload_reads": 0, "registration_commit": args.registration_commit})
    source = out/"config_check.cpp";source.write_text(CHECKER)
    executable = out/"config_check"
    # Headers are source-pinned by the registration; no unconstrained checkout header opens.
    headers = [ROOT/s for s in reg["source_pins"] if s.endswith((".h", ".hpp"))]
    compile_dir = out/"COMPILE"
    command = [compiler, "-std=c++17", "-O2", "-I", ROOT/"cpp/legsa_v23_port_core/include",
               source, library, "-o", executable]
    # The compiler output and source are in the enclosing exclusive loader attempt.
    result = launch(command, compile_dir, 60, aliases, [source, library, *headers], "CHECKER_COMPILE", 1, output_scope=out)
    records = []
    for index, (run, config) in enumerate(zip(plan["runs"], configs), 1):
        dest = out/run["sequence_id"]
        result = launch([executable, config, dest/"ECHO"], dest, 60, aliases,
                        [executable, config, expand(run["events"]["path"], aliases)],
                        "LOADER_"+run["sequence_id"], index+1)
        parsed_counts = read(dest/"stdout.log")
        expected_blocks = {"BY2": 274, "BY2H": 270, "BY2O": 377}[run["sequence_id"]]
        require(run["block_count"] == expected_blocks and
                parsed_counts == {"source_rows": 2*expected_blocks, "source_blocks": expected_blocks},
                "real generated ARC metadata CSV parser count mismatch")
        echo = read(dest/"ECHO/RUN_MANIFEST.json")
        expected = {"run_id": run["run_id"], "arc_clone_mode": "NULL_ARC_DIAGNOSTIC",
                    "arc_source_events_path": str(expand(run["events"]["path"], aliases)),
                    "arc_source_events_sha256": run["events"]["sha256"],
                    "arc_schedule_manifest_sha256": run["manifest"]["sha256"],
                    "arc_source_time_scale_id": "UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS",
                    "arc_availability_policy": "source_time_replay_assumption",
                    "arc_actual_available_time": None, "arc_phase_state_cross": "UNKNOWN",
                    "heading_source_policy": "pvt_priority_control", "dual_yaw_prediction_model": "euler_yaw",
                    "arc_source_time_mapping_id": run["sequence_id"]+":SEALED_RAWX_UTC_AND_CALIBRATED_IMU_BASE_V1"}
        expected.update({k: run["metadata_fields"][k] for k in
                         ("stage_id", "protocol_id", "case_id", "run_id", "run_label", "outputpath")})
        # The output path is a CLI-overridden config token, not a manifest identity field.
        expected.pop("outputpath", None)
        for key, value in expected.items():
            require(echo.get(key) == value, "loader ARC/static echo mismatch: "+key)
        original = read(expand(run["original_checker_echo"]["path"], aliases))
        science_keys = sorted(set(SCIENCE_FIELDS) | {k for k in original if k.startswith("init_")})
        for key in science_keys:
            require(key in original and key in echo and original[key] == echo[key],
                    "original scientific config changed in loader echo: "+key)
        actual_inputs = dict(echo["actual_solver_input_paths"])
        require(actual_inputs.pop("arc_source_time_metadata_only") == expected["arc_source_events_path"],
                "ARC source role missing")
        # Compare inherited provider paths; do not open those payloads here.
        expected_paths = {str(expand(p["path"], aliases)) for p in run["providers"].values()}
        expected_paths.add(str(expand(run["carrier"]["path"], aliases)))
        require(set(actual_inputs.values()) == expected_paths, "inherited provider path identity")
        records.append({"sequence_id": run["sequence_id"], "config": run["config"],
                        "echo": pin(dest/"ECHO/RUN_MANIFEST.json"), "result": result,
                        "arc_and_metadata_echo": expected,
                        "original_scientific_echo": {k: echo[k] for k in science_keys},
                        "original_checker_echo": run["original_checker_echo"],
                        "production_real_csv_parser_called": True,
                        "production_csv_parse_counts": parsed_counts,
                        "event_execution_qualified": False})
    source_check(reg, args.registration_commit)
    check(reg["library"], aliases);check(reg["binary"], aliases)
    require(all(digest(Path(p)) == h for p, h in before.items()), "metadata changed during loader gate")
    emit(out/"COMPLETE.json", {"status": "COMPLETE_LOADER_ONLY_NO_REAL_NATIVE",
         "registration_commit": args.registration_commit, "prepared_plan_sha256": before[str(stage/"PLAN.json")],
         "checker": pin(executable), "registered_budget": BUDGET,
         "actual_calls": {"checker_compiles": 1, "config_loader_calls": 3,
                          "real_csv_parser_calls": 3, "native_calls": 0, "evaluator_calls": 0},
         "records": records,
         "source_pins": reg["source_pins"], "metadata_pins": before,
         "provider_payload_pin_status": "INHERITED_NOT_REHASHED_THIS_STAGE",
         "next_gate": "separately registered input hash budget and six matched empty-phase native calls"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("loader",))
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--registration-commit", required=True)
    args = parser.parse_args()
    try:
        loader(args)
    except BaseException as exc:
        if OWN_ATTEMPT is not None and not (OWN_ATTEMPT/"FAILED.json").exists():
            emit(OWN_ATTEMPT/"FAILED.json", {"error": repr(exc), "traceback": traceback.format_exc(),
                 "first_failure_preserved": True, "retry_allowed": False, "native_calls": 0})
        raise


if __name__ == "__main__":
    main()
