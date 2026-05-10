#!/usr/bin/env python3
"""Run the N5A raw Doppler factor diagnostic trial.

中文说明：若 readiness 未允许 activation，本脚本不会启用 solver；若未来 provider
可用但 raw_doppler_update_count 为 0，必须标记 real activation failed。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_factor_report import read_json_report, write_json_report


def _run_probe(args: argparse.Namespace) -> None:
    command = [
        "python3",
        "scripts/experiments/run_raw_doppler_readiness_probe.py",
        "--fix-root",
        args.fix_root,
        "--rtklib-root",
        args.rtklib_root,
        "--output-dir",
        args.output_dir,
        "--allow-run",
    ]
    for root in args.ephemeris_search_root:
        command.extend(["--ephemeris-search-root", root])
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--ephemeris-search-root", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for runtime trial")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _run_probe(args)
    decision = read_json_report(out / "RAW_DOPPLER_READINESS_DECISION.json")
    provider = read_json_report(out / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")
    scan = read_json_report(out / "RAW_GNSS_MESSAGE_SCAN_REPORT.json")
    ephemeris = read_json_report(out / "EPHEMERIS_DISCOVERY_REPORT.json")
    rtklib = read_json_report(out / "RTKLIB_DISCOVERY_REPORT.json")

    report = {
        "stage": "N5A",
        "factor_name": "raw_doppler_auxiliary_factor",
        "factor_family": "raw_gnss",
        "clean_root_exists": Path(args.clean_root).exists(),
        "activation_allowed": decision.get("activation_allowed", False),
        "solver_enabled": False,
        "raw_doppler_update_count": 0,
        "trial_status": "not_started",
        "blocking_issue": decision.get("blocking_issue", "unknown"),
        "recommended_next_stage": decision.get("recommended_next_stage", "N5B_blocker_resolution"),
        "rawx_found": scan.get("rawx_found", False),
        "ephemeris_available": ephemeris.get("ephemeris_available", False),
        "rtklib_found": rtklib.get("rtklib_provider_available", False),
        "satellite_state_provider_status": provider.get("satellite_state_provider_status", "missing"),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
    }
    if not decision.get("activation_allowed", False):
        report["trial_status"] = decision.get("blocking_issue", "activation_blocked")
        if report["trial_status"] == "provider_missing_sat_state_export":
            report["trial_status"] = "skipped_provider_missing"
    else:
        # 中文说明：provider 可用时才允许真实 EKF diagnostic；当前脚本不伪造 factor CSV。
        report["trial_status"] = "activation_allowed_but_runtime_replay_not_implemented"
        report["solver_enabled"] = False
        report["blocking_issue"] = "real_replay_runner_missing"
        report["recommended_next_stage"] = "N5B_raw_doppler_ablation_or_replay_runner"
    if report["solver_enabled"] and report["raw_doppler_update_count"] == 0:
        report["trial_status"] = "activation_failed_zero_raw_doppler_updates"
        report["blocking_issue"] = "raw_doppler_update_count_zero"
    write_json_report(report, out / "N5A_RAW_DOPPLER_FACTOR_TRIAL_REPORT.json")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
