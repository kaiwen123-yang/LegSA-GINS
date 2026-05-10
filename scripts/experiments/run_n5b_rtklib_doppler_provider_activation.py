#!/usr/bin/env python3
"""Run N5B RTKLIB Doppler velocity provider and EKF activation trial.

中文说明：本脚本把 N5A 的 RAWX/convbin/星历结果接到 runtime-only RTKLIB helper，
生成 Doppler-derived velocity factor，并在合法时运行 raw Doppler enabled EKF。
不会把 RTKLIB position solution、NAV-PVT velocity、.gnss velocity、trace 或
final_v23 output 输入 solver。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.ephemeris_discovery import discover_ephemeris
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_gnss, run_n5b_activation_trial
from legsa_gins.raw_gnss.raw_doppler_factor_report import read_json_report, write_json_report
from legsa_gins.raw_gnss.raw_doppler_n5b_decision import decide_n5b_activation
from legsa_gins.raw_gnss.raw_doppler_velocity_factor_builder import build_factor_file_from_provider
from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import build_rtklib_doppler_helper
from legsa_gins.raw_gnss.rtklib_doppler_velocity_provider import run_rtklib_doppler_velocity_provider


def _load_report(path: Path) -> dict[str, Any]:
    return read_json_report(path) if path.exists() else {}


def _run_n5a_probe(args: argparse.Namespace, out: Path) -> None:
    command = [
        "python3",
        "scripts/experiments/run_raw_doppler_readiness_probe.py",
        "--fix-root",
        args.fix_root,
        "--rtklib-root",
        args.rtklib_root,
        "--output-dir",
        str(out),
        "--allow-run",
    ]
    for root in args.ephemeris_search_root:
        command.extend(["--ephemeris-search-root", root])
    subprocess.run(command, check=True)


def _n5a_provider_report(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    n5a_root = Path(args.n5a_root) if args.n5a_root else out
    report = _load_report(n5a_root / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")
    if report.get("generated_obs_files"):
        return report
    _run_n5a_probe(args, out)
    return _load_report(out / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")


def _first_existing(paths: list[str | None]) -> str:
    for item in paths:
        if item and Path(item).exists():
            return item
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--ephemeris-search-root", action="append", default=[])
    parser.add_argument("--n5a-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for runtime activation trial")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    n5a_provider = _n5a_provider_report(args, out)
    ephemeris = _load_report(Path(args.n5a_root) / "EPHEMERIS_DISCOVERY_REPORT.json")
    if not ephemeris:
        ephemeris = discover_ephemeris(args.ephemeris_search_root or [args.rtklib_root])
    helper_report = build_rtklib_doppler_helper(args.rtklib_root, args.build_dir, out)
    write_json_report(helper_report, out / "RTKLIB_DOPPLER_HELPER_BUILD_REPORT.json")

    clean_gnss = find_clean_gnss(args.clean_root)
    obs = _first_existing(n5a_provider.get("generated_obs_files", []))
    nav = _first_existing(n5a_provider.get("generated_nav_files", []))
    if not nav:
        nav = ephemeris.get("best_broadcast_nav_candidate", "")
    provider_report = run_rtklib_doppler_velocity_provider(
        obs_path=obs,
        nav_path=nav,
        sp3_path=ephemeris.get("best_sp3_candidate", ""),
        clk_path=ephemeris.get("best_clk_candidate", ""),
        helper_exe=helper_report.get("helper_executable_path", ""),
        approx_position_source=clean_gnss,
        output_dir=out,
    )
    write_json_report(provider_report, out / "RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json")

    factor_report = build_factor_file_from_provider(
        provider_report.get("factor_csv_path", ""),
        out,
        clean_gnss_path=clean_gnss,
        source_type=provider_report.get("source_provenance", "rtklib_doppler_helper_velocity"),
    )
    write_json_report(factor_report, out / "RAW_DOPPLER_FACTOR_BUILD_REPORT.json")

    trial_report, comparison_report = run_n5b_activation_trial(
        clean_root=args.clean_root,
        factor_build_report=factor_report,
        output_dir=out,
        exe=args.exe,
    )
    decision = decide_n5b_activation(helper_report, provider_report, factor_report, trial_report)
    write_json_report(trial_report, out / "N5B_RAW_DOPPLER_ACTIVATION_TRIAL_REPORT.json")
    write_json_report(comparison_report, out / "N5B_RAW_DOPPLER_FACTOR_COMPARISON_REPORT.json")
    write_json_report(decision, out / "N5B_RAW_DOPPLER_DECISION_REPORT.json")

    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
