#!/usr/bin/env python3
"""Run N5C raw Doppler ablation protocol.

中文说明：真实输入路径只来自命令行；tracked 脚本中不硬编码本机绝对路径。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_ablation_decision import make_n5c_decision, write_decision
from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import (
    compare_variants,
    load_clean_time_window,
    run_matrix_variants,
)
from legsa_gins.raw_gnss.raw_doppler_ablation_matrix import build_n5c_ablation_matrix, write_matrix
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config, find_clean_gnss
from legsa_gins.raw_gnss.raw_doppler_factor_diagnostics import (
    analyze_raw_doppler_factor_csv,
    write_report as write_factor_diag,
)
from legsa_gins.raw_gnss.raw_doppler_time_alignment import analyze_factor_time_alignment, read_first_column_times, write_report as write_time_report
from legsa_gins.raw_gnss.raw_doppler_velocity_comparison import (
    compare_raw_doppler_velocity_to_receiver_velocity,
    write_report as write_velocity_report,
)


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _find_factor_csv(n5b_root: str | Path) -> Path:
    root = Path(n5b_root)
    direct = root / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    if direct.exists():
        return direct
    matches = sorted(root.rglob("RAW_DOPPLER_VELOCITY_FACTORS.csv"))
    if matches:
        return matches[0]
    raise FileNotFoundError("RAW_DOPPLER_VELOCITY_FACTORS.csv missing under N5B root")


def _find_clean_imu(clean_root: str | Path, clean_config: Path | None) -> Path | None:
    root = Path(clean_root)
    preferred = root / "CLEAN_STATUS_YAW.imu"
    if preferred.exists():
        return preferred
    if clean_config and clean_config.exists():
        for line in clean_config.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith(("imupath:", "imu_path:")):
                value = line.split(":", 1)[1].strip().strip('"').strip("'")
                path = Path(value)
                if path.exists():
                    return path
    matches = sorted(root.glob("*.imu"))
    return matches[0] if matches else None


def _filter_window(times: list[float], start: float | None, end: float | None) -> list[float]:
    out = []
    for time in times:
        if not math.isfinite(time):
            continue
        if start is not None and time <= start:
            continue
        if end is not None and time > end:
            continue
        out.append(time)
    return out


def _case_review(decision: dict[str, Any], comparison: dict[str, Any], path: str | Path) -> None:
    text = "\n".join(
        [
            "# N5C raw Doppler ablation case review",
            "",
            "This runtime report is diagnostic engineering evidence only.",
            "",
            f"- status: {decision.get('status')}",
            f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
            f"- raw_doppler_update_count: {decision.get('raw_doppler_update_count')}",
            f"- baseline_plus_raw_doppler_delta: {comparison.get('delta_baseline_plus_raw_doppler_minus_baseline')}",
            f"- velocity_isolation_delta: {comparison.get('velocity_isolation_delta')}",
            "- paper_performance_claim: false",
            "- no_outperform_final_v23_claim: true",
            "- final_v23_output_solver_input: false",
            "- trace_solver_input: false",
            "- output_only_correction: false",
            "- bad_epoch_deletion_for_metric: false",
        ]
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir")
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-rscale-screen", default="true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N5C runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.figure_output_dir:
        Path(args.figure_output_dir).mkdir(parents=True, exist_ok=True)

    factor_csv = _find_factor_csv(args.n5b_root)
    clean_config = find_clean_config(args.clean_root)
    clean_gnss = find_clean_gnss(args.clean_root)
    clean_imu = _find_clean_imu(args.clean_root, clean_config)
    if clean_gnss is None or clean_imu is None:
        raise FileNotFoundError("clean GNSS/IMU input missing")
    start, end = load_clean_time_window(args.clean_root)

    factor_diag = analyze_raw_doppler_factor_csv(factor_csv, clean_start=start, clean_end=end)
    write_factor_diag(factor_diag, out / "RAW_DOPPLER_FACTOR_DIAGNOSTICS_REPORT.json")

    velocity_comp = compare_raw_doppler_velocity_to_receiver_velocity(factor_csv, clean_gnss)
    write_velocity_report(velocity_comp, out / "RAW_DOPPLER_VELOCITY_COMPARISON_REPORT.json")

    matrix = build_n5c_ablation_matrix(factor_csv, out, run_rscale_screen=str(args.run_rscale_screen).lower() == "true")
    write_matrix(matrix, out / "N5C_ABLATION_MATRIX.json")

    runs, variant_reports = run_matrix_variants(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        build_dir=args.build_dir,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    del runs
    comparison = compare_variants(variant_reports)
    _write_json(out / "N5C_ABLATION_COMPARISON_REPORT.json", comparison)

    plus_manifest = _read_json(out / "variants" / "baseline_plus_raw_doppler_r1" / "RUN_MANIFEST.json")
    gnss_times = _filter_window(read_first_column_times(clean_gnss), start, end)
    imu_times = _filter_window(read_first_column_times(clean_imu), start, end)
    time_align = analyze_factor_time_alignment(factor_csv, gnss_times, imu_times, plus_manifest, tolerance=0.08)
    write_time_report(time_align, out / "RAW_DOPPLER_TIME_ALIGNMENT_REPORT.json")

    decision = make_n5c_decision(factor_diag, velocity_comp, time_align, comparison)
    write_decision(decision, out / "N5C_RAW_DOPPLER_ABLATION_DECISION_REPORT.json")
    _case_review(decision, comparison, out / "n5c_raw_doppler_ablation_case_review.md")
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
