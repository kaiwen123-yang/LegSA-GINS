#!/usr/bin/env python3
"""Isolated GNSS-only explorations; never creates a LegSA/F04 result row."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import build_rtklib_doppler_helper
from legsa_gins.paper_rebuild.audit_xbpg.run_validation import validate_output, terminal_status, permits_full_after_smoke

EXPECTED_RNX = "3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda"
EXPECTED_CONVBIN = "85b6b981374c7df957492d9423a3c650a35cb5e7253598651070adf4d9f1df2a"
EXPECTED_CONFIG = "97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def invoke(argv, directory, role, timeout, *, data_mode="real_xb_pg_raw", kind=None):
    directory.mkdir(parents=True, exist_ok=False)
    receipt = dict(role=role, argv=[str(x) for x in argv], status="STARTED", start_utc=datetime.now(timezone.utc).isoformat(),
                   data_mode=data_mode, synthetic_data_used=data_mode == "synthetic_test", semisynthetic_data_used=False,
                   trace_used_online=False, receiver_imu_as_body_imu=False, final_v23_output_solver_input=False,
                   LegSA_output_solver_input=False, per_case_tuning=False, output_only_correction=False,
                   epoch_deleted_for_metric=False, old_runtime_input_count=0)
    dump(directory / "COMMAND.json", receipt)
    environment = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    started = time.monotonic()
    with (directory / "stdout.log").open("w") as out, (directory / "stderr.log").open("w") as err:
        try:
            proc = subprocess.Popen(["strace", "-f", "-qq", "-s", "1024", "-e", "trace=openat,execve", "-o", str(directory / "ACCESS.strace"), *map(str, argv)], cwd=directory, env=environment, stdout=out, stderr=err, start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                receipt.update(returncode=proc.returncode, status="TIMEOUT", exception="TimeoutExpired", process_group_killed=True)
            else:
                receipt.update(returncode=proc.returncode, status="COMPLETED" if proc.returncode == 0 else "TECHNICAL_FAILURE")
        except OSError as exc:
            receipt.update(returncode=None, status="LAUNCH_ERROR", exception=type(exc).__name__, exception_message=str(exc))
    receipt["wall_seconds_including_strace"] = time.monotonic() - started
    receipt["end_utc"] = datetime.now(timezone.utc).isoformat()
    access_path = directory / "ACCESS.strace"
    accesses = access_path.read_text(errors="replace") if access_path.is_file() else ""
    if not access_path.is_file() and receipt["status"] != "LAUNCH_ERROR":
        receipt["status"] = "ACCESS_AUDIT_MISSING"
    receipt["reference_path_access_lines"] = [s for s in accesses.splitlines() if "openat(" in s and any(n in s.lower() for n in ("trace_vrtk", "poi_odometry", "poi_geodetic", "poi_smooth"))]
    if receipt["reference_path_access_lines"]:
        receipt["status"] = "FORBIDDEN_REFERENCE_ACCESS"
    receipt["artifacts"] = {p.name: sha(p) for p in directory.iterdir() if p.suffix in (".pos", ".csv")}
    if kind:
        receipt["process_status"] = receipt["status"]
        receipt["output_validation"] = validate_output(directory, kind)
        receipt["status"] = terminal_status(receipt, receipt["output_validation"])
    dump(directory / "COMMAND.json", receipt)
    print(role, receipt["status"], receipt["returncode"], round(receipt["wall_seconds_including_strace"], 3), flush=True)
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", type=Path, required=True)
    ap.add_argument("--phase", choices=("prepare", "run", "validate-retained"), required=True)
    paths = yaml.safe_load(ap.parse_args().local.read_text())["paths"]
    args = ap.parse_args()
    output = Path(paths["audit_root"]) / "gnss_exploration"
    scratch = Path(paths["audit_scratch"]) / "gnss_exploration"
    root = Path(paths["code_root"])
    ext = Path(paths["horizontal_literature_rtklib_root"])
    convbin = Path(paths["horizontal_literature_convbin"])
    executable = ext / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    if args.phase == "validate-retained":
        for directory in sorted(output.iterdir()):
            receipt_path = directory / "COMMAND.json"
            if not directory.is_dir() or not receipt_path.is_file() or not any(s in directory.name for s in ("_RTK_", "_RD_")):
                continue
            receipt = json.loads(receipt_path.read_text())
            validation = validate_output(directory, "rtk" if "_RTK_" in directory.name else "rd")
            record = {"original_receipt_sha256": sha(receipt_path), "original_status": receipt["status"],
                      "validation": validation, "terminal_status": terminal_status(receipt, validation),
                      "post_hoc_validation": True, "scientific_reruns": 0,
                      "recorded_output_hashes_match": all((directory / n).is_file() and sha(directory / n) == h for n, h in receipt["artifacts"].items())}
            if not record["recorded_output_hashes_match"]:
                record["terminal_status"] = "OUTPUT_IDENTITY_MISMATCH"
            with (directory / "OUTPUT_VALIDATION.json").open("x") as stream:
                json.dump(record, stream, indent=2, allow_nan=False)
                stream.write("\n")
            print(directory.name, record["terminal_status"], validation["finite_rows"])
        return
    assert sha(convbin) == EXPECTED_CONVBIN and sha(executable) == EXPECTED_RNX
    if args.phase == "prepare":
        output.mkdir(parents=True, exist_ok=False)
        scratch.mkdir(parents=True, exist_ok=False)
        source = Path(paths["clean_root"]) / "stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/01_INPUT_PINS/RTKLIB_UNMODIFIED_MOVING_BASE.conf"
        original = source.read_bytes()
        assert hashlib.sha256(original).hexdigest() == EXPECTED_CONFIG
        lines = original.splitlines(keepends=True)
        changed = []
        for i, line in enumerate(lines):
            if line.lstrip().startswith(b"pos2-baselen"):
                assert b"0.350" in line
                lines[i] = line.replace(b"0.350", b"0.000")
                changed.append(i + 1)
        assert len(changed) == 1
        config = output / "UNCONSTRAINED_MOVING_BASE.conf"
        config.write_bytes(b"".join(lines))
        preparations = []
        for seq in ("S1", "S2", "S3", "S4"):
            for receiver in (1, 2):
                ubx = Path(paths["audit_root"]) / "data_audit/decoded" / seq / f"gnss{receiver}-raw.ubx"
                target = output / f"{seq}_gnss{receiver}_rinex"
                obs, nav = target / "raw.obs", target / "broadcast.nav"
                receipt = invoke([convbin, "-r", "ubx", "-o", obs, "-n", nav, ubx], target, f"{seq}_CONVBIN_{receiver}", 600)
                receipt["input_sha256"] = sha(ubx)
                receipt["rinex"] = {p.name: sha(p) for p in (obs, nav) if p.exists()}
                dump(target / "COMMAND.json", receipt)
                preparations.append(receipt)
        helper = build_rtklib_doppler_helper(ext, None, scratch / "rd_build")
        dump(output / "RD_BUILD.json", helper)
        helper_path = Path(helper["helper_executable_path"]) if helper["helper_executable_path"] else None
        dump(output / "PREPARATION.json", dict(config_sha256=sha(config), source_config_sha256=EXPECTED_CONFIG,
             changed_line_1based=changed, change_reason="Unknown XB antenna length; disable BY2 length constraint before outcomes", rnx_sha256=sha(executable), convbin_sha256=sha(convbin),
             rtklib_source_commit=subprocess.check_output(["git", "-C", str(ext), "rev-parse", "HEAD"], text=True).strip(),
             helper_sha256=sha(helper_path) if helper_path else None, helper_build_status=helper["helper_compile_status"],
             code_commit=subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
             convbin_invocations=len(preparations), all_convbin_completed=all(x["status"] == "COMPLETED" for x in preparations)))
        return
    # User requires a committed protocol before any reference performance analysis.
    protocol = root / "docs/paper_rebuild/audit_xbpg_20261001/EXPLORATORY_PROTOCOL.md"
    assert protocol.is_file()
    subprocess.run(["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--", str(protocol)], check=True)
    subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", str(protocol)], check=True, stdout=subprocess.DEVNULL)
    prep = json.loads((output / "PREPARATION.json").read_text())
    config = output / "UNCONSTRAINED_MOVING_BASE.conf"
    assert sha(config) == prep["config_sha256"]
    rtk_gate = True
    for seq in ("S1", "S2", "S3", "S4"):
        obs = [output / f"{seq}_gnss{r}_rinex/raw.obs" for r in (1, 2)]
        nav = [output / f"{seq}_gnss{r}_rinex/broadcast.nav" for r in (1, 2)]
        if seq == "S1":
            # Technical smoke uses the first recorded interval, never a chosen-good span.
            smoke = output / "S1_RTK_SMOKE"
            raw = np.load(Path(paths["audit_root"]) / "data_audit/decoded/S1/gnss1-raw.npz", allow_pickle=False)
            end = datetime(1980, 1, 6) + timedelta(weeks=int(raw["RXM_RAWX__week"][0]), seconds=float(raw["RXM_RAWX__rcv_tow"][0]) + 30.)
            command = [executable, "-k", config, "-o", smoke / "solution.pos", "-te", end.strftime("%Y/%m/%d"), end.strftime("%H:%M:%S.%f")[:12], obs[1], obs[0], *nav]
            smoke_receipt = invoke(command, smoke, "S1_RTK_FIRST30S_TECHNICAL_SMOKE", 120, kind="rtk")
            rtk_gate = permits_full_after_smoke(smoke_receipt["status"])
        run = output / f"{seq}_RTK_FULL"
        if rtk_gate:
            receipt = invoke([executable, "-k", config, "-o", run / "solution.pos", obs[1], obs[0], *nav], run, f"{seq}_EXPLORATORY_RTKLIB_UNCONSTRAINED", 600, kind="rtk")
            receipt.update(code_commit=subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                       binary_sha256=EXPECTED_RNX, config_hash=sha(config), input_hashes={str(p.relative_to(output)): sha(p) for p in [*obs, *nav]},
                       performance_evaluation="NOT_RUN_REFERENCE_POINT_GEOMETRY_UNVERIFIED")
            dump(run / "COMMAND.json", receipt)
        else:
            run.mkdir(exist_ok=False)
            dump(run / "SKIPPED.json", {"status": "BLOCKED_BY_SMOKE_TECHNICAL_FAILURE", "native_invocations": 0, "reason": smoke_receipt["status"]})
        helper = json.loads((output / "RD_BUILD.json").read_text())
        if helper["helper_compile_status"] == "success":
            helper_path = Path(helper["helper_executable_path"])
            assert sha(helper_path) == prep["helper_sha256"]
            rd = output / f"{seq}_RD_FULL"
            rec = invoke([helper_path, obs[0], nav[0], rd / "doppler_ecef.csv"], rd, f"{seq}_EXPLORATORY_CURRENT_RAW_DOPPLER_HELPER", 180, kind="rd")
            rec.update(binary_sha256=prep["helper_sha256"], input_hashes={str(p.relative_to(output)): sha(p) for p in (obs[0], nav[0])},
                       covariance_frame="ECEF_DIAGONAL_FLOORED_NO_NED_RELABELLING", performance_evaluation="NOT_RUN")
            dump(rd / "COMMAND.json", rec)
        else:
            rd = output / f"{seq}_RD_FULL"
            rd.mkdir(exist_ok=False)
            dump(rd / "SKIPPED.json", {"status":"BLOCKED_BY_HELPER_BUILD_FAILURE", "native_invocations":0,
                                      "reason":helper["helper_compile_status"]})


if __name__ == "__main__":
    main()
