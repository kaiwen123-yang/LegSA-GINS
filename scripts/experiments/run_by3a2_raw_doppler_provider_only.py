#!/usr/bin/env python3
"""Materialize a BY3 Raw Doppler provider with the accepted BY2 N5A/N5B chain.

This helper intentionally stops at provider/factor CSV generation. It does not
run EKF, evaluator, degradation cases, or selected-feedback stages.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.ephemeris_discovery import discover_ephemeris
from legsa_gins.raw_gnss.raw_doppler_factor_report import write_json_report
from legsa_gins.raw_gnss.raw_doppler_readiness import decide_readiness
from legsa_gins.raw_gnss.raw_doppler_velocity_factor_builder import build_factor_file_from_provider
from legsa_gins.raw_gnss.rtklib_discovery import discover_rtklib
from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import build_rtklib_doppler_helper
from legsa_gins.raw_gnss.rtklib_doppler_provider import attempt_rtklib_provider
from legsa_gins.raw_gnss.rtklib_doppler_velocity_provider import run_rtklib_doppler_velocity_provider
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import rebuild_fix_root
from legsa_gins.raw_gnss.ubx_raw_message_scanner import scan_fix_root
from legsa_gins.raw_gnss.ubx_rawx_parser import parse_fix_root, report_measurements, write_epochs_jsonl
from legsa_gins.raw_gnss.ubx_sfrbx_scanner import scan_fix_root as scan_sfrbx_fix_root


def _sha256(path: str | Path) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_count(path: str | Path) -> int:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return 0
    with p.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _csv_columns(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return []
    with p.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def _time_range(path: str | Path) -> tuple[float | None, float | None]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return (None, None)
    values: list[float] = []
    with p.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                value = float(row.get("time", "nan"))
            except ValueError:
                continue
            if math.isfinite(value):
                values.append(value)
    return (min(values), max(values)) if values else (None, None)


def _csv_report(path: str | Path) -> dict[str, Any]:
    if not str(path).strip():
        return {
            "path": "",
            "exists": False,
            "row_count": 0,
            "columns": [],
            "time_min": None,
            "time_max": None,
            "sha256": "",
        }
    p = Path(path)
    t0, t1 = _time_range(p)
    return {
        "path": str(p),
        "exists": p.exists(),
        "row_count": _row_count(p),
        "columns": _csv_columns(p),
        "time_min": t0,
        "time_max": t1,
        "sha256": _sha256(p),
    }


def _first_existing(paths: list[str | None]) -> str:
    for item in paths:
        if item and Path(item).exists():
            return item
    return ""


def _fresh_convbin_success(rinex_report: dict[str, Any]) -> bool:
    runs = rinex_report.get("convbin_run_status", {}).get("runs", [])
    if not runs:
        return False
    return all(int(run.get("returncode", 1)) == 0 for run in runs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True, help="BY3 receiver folder containing gnss*-raw.csv")
    parser.add_argument("--clean-gnss", required=True, help="BY3 repaired dual GNSS used only for position/time alignment")
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--ephemeris-search-root", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required for provider materialization")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rtklib_report = discover_rtklib(args.rtklib_root)
    ephemeris_report = discover_ephemeris(args.ephemeris_search_root or [args.rtklib_root])
    scan_report = scan_fix_root(args.fix_root)
    rebuild_report = rebuild_fix_root(args.fix_root, out)
    rebuilt_ubx = [
        item.get("output_ubx", "")
        for item in rebuild_report.get("files", {}).values()
        if item.get("rebuilt_ubx_available")
    ]
    measurements = parse_fix_root(args.fix_root, rebuilt_ubx)
    rawx_report = report_measurements(measurements)
    sfrbx_report = scan_sfrbx_fix_root(args.fix_root)
    rinex_report = attempt_rtklib_provider(
        rtklib_report=rtklib_report,
        ephemeris_report=ephemeris_report,
        rebuild_report=rebuild_report,
        output_dir=out,
    )
    readiness = decide_readiness(scan_report, ephemeris_report, rtklib_report, rinex_report).to_dict()

    helper_report = build_rtklib_doppler_helper(args.rtklib_root, args.build_dir, out)
    fresh_rinex = _fresh_convbin_success(rinex_report)
    obs_path = _first_existing(rinex_report.get("generated_obs_files", [])) if fresh_rinex else ""
    nav_path = _first_existing(rinex_report.get("generated_nav_files", [])) if fresh_rinex else ""
    if not nav_path:
        nav_path = ephemeris_report.get("best_broadcast_nav_candidate", "")

    velocity_report = run_rtklib_doppler_velocity_provider(
        obs_path=obs_path,
        nav_path=nav_path,
        sp3_path=ephemeris_report.get("best_sp3_candidate", ""),
        clk_path=ephemeris_report.get("best_clk_candidate", ""),
        helper_exe=helper_report.get("helper_executable_path", ""),
        approx_position_source=args.clean_gnss,
        output_dir=out,
    )
    velocity_csv = velocity_report.get("factor_csv_path", "")
    if velocity_csv and Path(velocity_csv).is_file():
        factor_report = build_factor_file_from_provider(
            velocity_csv,
            out,
            clean_gnss_path=args.clean_gnss,
            source_type=velocity_report.get("source_provenance", "rtklib_doppler_helper_velocity"),
        )
    else:
        factor_report = {
            "factor_csv_generated": False,
            "factor_csv_path": "",
            "factor_epoch_count": 0,
            "factor_valid_epoch_count": 0,
            "sat_count_min": 0,
            "sat_count_median": 0,
            "sat_count_max": 0,
            "time_alignment_policy": "not_available",
            "time_offset_sec": 0.0,
            "clean_replay_time_range": None,
            "factor_time_range": None,
            "raw_doppler_solver_activation_allowed": False,
            "not_sourced_from_nav_pvt": True,
            "not_sourced_from_gnss_15col_velocity": True,
            "rtklib_position_solution_used_as_solver_input": False,
            "final_v23_output_solver_input": False,
            "trace_solver_input": False,
            "blocker_reasons": ["velocity_provider_csv_missing_or_empty"],
        }

    provider_index = [
        {
            "provider": "rtklib_velocity_provider",
            "role": "intermediate_provider",
            "ready_for_solver": bool(velocity_report.get("solver_activation_allowed", False)),
            **_csv_report(velocity_report.get("factor_csv_path", "")),
        },
        {
            "provider": "raw_doppler_velocity_factors",
            "role": "solver_provider",
            "ready_for_solver": bool(factor_report.get("raw_doppler_solver_activation_allowed", False)),
            **_csv_report(factor_report.get("factor_csv_path", "")),
        },
    ]

    combined_blockers = sorted(
        set(
            readiness.get("blocker_reasons", [])
            + helper_report.get("blocker_reasons", [])
            + velocity_report.get("blocker_reasons", [])
            + factor_report.get("blocker_reasons", [])
        )
    )
    if not fresh_rinex:
        combined_blockers = sorted(set(combined_blockers + ["convbin_current_run_failed_or_not_fresh"]))
    factor_ready = bool(factor_report.get("raw_doppler_solver_activation_allowed", False))
    warnings = combined_blockers
    if factor_ready and "provider_missing_sat_state_export" in warnings:
        warnings = [
            "N5A_probe_provider_missing_sat_state_export_resolved_by_N5B_helper"
            if item == "provider_missing_sat_state_export"
            else item
            for item in warnings
        ]
    materialization = {
        "stage": "BY3A2_raw_doppler_provider_only",
        "by2_logic_reference": "N5A rebuild UBX/convbin RINEX plus N5B RTKLIB Doppler helper velocity provider",
        "solver_run": False,
        "evaluator_run": False,
        "degradation_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "gnss_velocity_used_as_raw_doppler": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "rtklib_position_solution_used_as_solver_input": False,
        "receiver_imu_as_body_imu": False,
        "rtklib_ready": bool(rtklib_report.get("rtklib_provider_available", False)),
        "ephemeris_available": bool(ephemeris_report.get("ephemeris_available", False)),
        "rebuilt_ubx_available": bool(rebuild_report.get("rebuilt_ubx_available", False)),
        "rinex_obs_generated": bool(rinex_report.get("obs_generated", False) and fresh_rinex),
        "rinex_nav_generated": bool(rinex_report.get("nav_generated", False) and fresh_rinex),
        "fresh_convbin_success": fresh_rinex,
        "velocity_provider_ready": bool(velocity_report.get("solver_activation_allowed", False)),
        "factor_provider_ready": factor_ready,
        "decision": "BY3A2_raw_doppler_provider_ready"
        if factor_ready
        else "BY3A2_raw_doppler_provider_blocked_missing_rinex_nav",
        "blocker_reasons": [] if factor_ready else combined_blockers,
        "warning_reasons": warnings if factor_ready else [],
        "reports": {
            "readiness": "RAW_DOPPLER_READINESS_DECISION.json",
            "rinex": "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json",
            "velocity_provider": "RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json",
            "factor_build": "RAW_DOPPLER_FACTOR_BUILD_REPORT.json",
        },
        "provider_index": provider_index,
    }

    write_json_report(scan_report, out / "RAW_GNSS_MESSAGE_SCAN_REPORT.json")
    write_json_report(rebuild_report, out / "UBX_REBUILD_REPORT.json")
    write_json_report(rawx_report, out / "RAWX_DOPPLER_EPOCH_REPORT.json")
    write_epochs_jsonl(measurements, out / "RAW_DOPPLER_EPOCHS.jsonl")
    write_json_report(sfrbx_report, out / "SFRBX_READINESS_REPORT.json")
    write_json_report(rtklib_report, out / "RTKLIB_DISCOVERY_REPORT.json")
    write_json_report(ephemeris_report, out / "EPHEMERIS_DISCOVERY_REPORT.json")
    write_json_report(rinex_report, out / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")
    write_json_report(readiness, out / "RAW_DOPPLER_READINESS_DECISION.json")
    write_json_report(helper_report, out / "RTKLIB_DOPPLER_HELPER_BUILD_REPORT.json")
    write_json_report(velocity_report, out / "RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json")
    write_json_report(factor_report, out / "RAW_DOPPLER_FACTOR_BUILD_REPORT.json")
    write_json_report(materialization, out / "BY3A2_RAW_DOPPLER_PROVIDER_MATERIALIZATION_REPORT.json")

    with (out / "BY3A2_RAW_DOPPLER_PROVIDER_INDEX.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "provider",
            "role",
            "ready_for_solver",
            "path",
            "exists",
            "row_count",
            "columns",
            "time_min",
            "time_max",
            "sha256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in provider_index:
            row = dict(row)
            row["columns"] = "|".join(row.get("columns", []))
            writer.writerow(row)

    print(json.dumps(materialization, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
