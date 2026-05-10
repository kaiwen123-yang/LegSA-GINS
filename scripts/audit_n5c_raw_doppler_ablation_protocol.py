#!/usr/bin/env python3
"""Audit N5C raw Doppler ablation protocol boundaries.

中文说明：本审计只检查 N5C 消融协议、诊断报告边界和 artifact hygiene，不运行真实数据。
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_ablation_decision import make_n5c_decision
from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import compare_variants
from legsa_gins.raw_gnss.raw_doppler_ablation_matrix import build_n5c_ablation_matrix
from legsa_gins.raw_gnss.raw_doppler_factor_diagnostics import analyze_raw_doppler_factor_csv
from legsa_gins.raw_gnss.raw_doppler_time_alignment import analyze_factor_time_alignment
from legsa_gins.raw_gnss.raw_doppler_velocity_comparison import compare_raw_doppler_velocity_to_receiver_velocity

def _fail(message: str) -> None:
    raise SystemExit(f"FAILED: {message}")


def _must_exist(paths: list[str]) -> None:
    for rel in paths:
        if not (ROOT / rel).exists():
            _fail(f"missing {rel}")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    patterns = [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]
    for pattern in patterns:
        if _git_lines(["grep", "-n", pattern, "--", "."]):
            _fail(f"local path leak: {pattern}")


def _check_no_artifacts() -> None:
    tracked = _git_lines(["ls-files"])
    bad_suffixes = (".ubx", ".obs", ".nav", ".sp3", ".clk", ".imu", ".png", ".pdf", ".svg", ".jpg", ".jpeg")
    bad_names = {
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "input.gnss",
        "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt",
        "RAW_DOPPLER_VELOCITY_FACTORS.csv",
        "summary.json",
        "error_series.csv",
    }
    for path in tracked:
        name = Path(path).name
        if name in bad_names or path.endswith(bad_suffixes):
            _fail(f"generated/raw artifact tracked: {path}")


def _toy_ablation() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n5c_audit_") as tmp:
        root = Path(tmp)
        factor = root / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
        with factor.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "time",
                    "vn",
                    "ve",
                    "vd",
                    "std_vn",
                    "std_ve",
                    "std_vd",
                    "sat_count",
                    "doppler_obs_count",
                    "gdop_like",
                    "provider_status",
                    "source_epoch_time",
                    "quality_flag",
                ],
            )
            writer.writeheader()
            for idx in range(6):
                writer.writerow(
                    {
                        "time": 10.0 + idx,
                        "vn": 1.0 + idx * 0.01,
                        "ve": 0.2,
                        "vd": -0.1,
                        "std_vn": 0.2,
                        "std_ve": 0.2,
                        "std_vd": 0.3,
                        "sat_count": 8,
                        "doppler_obs_count": 8,
                        "gdop_like": 1.5,
                        "provider_status": "available",
                        "source_epoch_time": 10.0 + idx,
                        "quality_flag": "ok",
                    }
                )
        clean = root / "clean.gnss"
        clean.write_text("\n".join(f"{10.0+i} 0 0 0 0 0 0 {1.2+i*0.01} 0.1 -0.2 0 0 0 0 0" for i in range(6)) + "\n", encoding="utf-8")
        matrix = build_n5c_ablation_matrix(factor, root)
        variants = {row["variant_id"]: row for row in matrix["matrix"]}
        if set(variants) != {
            "baseline_full",
            "baseline_plus_raw_doppler_r1",
            "position_yaw_plus_raw_doppler_r1",
            "position_yaw_only",
            "baseline_plus_raw_doppler_r0p5",
            "baseline_plus_raw_doppler_r2",
            "baseline_plus_raw_doppler_r5",
        }:
            _fail("ablation matrix missing required variants")
        for row in matrix["matrix"]:
            if row["proposed_candidate"] != (row["variant_id"] == "baseline_plus_raw_doppler_r1"):
                _fail("only baseline_plus_raw_doppler_r1 may be proposed candidate")
            if row.get("paper_performance_claim", True):
                _fail("matrix makes paper performance claim")
        factor_diag = analyze_raw_doppler_factor_csv(factor, clean_start=10.0, clean_end=15.0)
        comp = compare_raw_doppler_velocity_to_receiver_velocity(factor, clean)
        time = analyze_factor_time_alignment(factor, [10.0 + i for i in range(6)], [10.0 + i * 0.5 for i in range(11)], {"raw_doppler_update_count": 6})
        reports = [
            {"variant_id": "baseline_full", "summary": {"horizontal_rmse_m": 1.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
            {"variant_id": "baseline_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 0.9, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 6, "raw_doppler_reject_count": 0},
            {"variant_id": "position_yaw_only", "summary": {"horizontal_rmse_m": 2.0, "up_rmse_m": 2.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
            {"variant_id": "position_yaw_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 1.8, "up_rmse_m": 2.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 6},
        ]
        comparison = compare_variants(reports)
        decision = make_n5c_decision(factor_diag, comp, time, comparison)
        for report in [matrix, decision, comparison]:
            if report.get("paper_performance_claim", False):
                _fail("toy report claims paper performance")
            if not report.get("no_outperform_final_v23_claim", True):
                _fail("toy report lacks final_v23 claim boundary")
        if decision["raw_doppler_update_count"] <= 0:
            _fail("toy ablation did not preserve raw Doppler update count")


def main() -> int:
    _must_exist(
        [
            "src/legsa_gins/raw_gnss/raw_doppler_ablation_matrix.py",
            "src/legsa_gins/raw_gnss/raw_doppler_factor_diagnostics.py",
            "src/legsa_gins/raw_gnss/raw_doppler_velocity_comparison.py",
            "src/legsa_gins/raw_gnss/raw_doppler_time_alignment.py",
            "src/legsa_gins/raw_gnss/raw_doppler_ablation_evaluator.py",
            "src/legsa_gins/raw_gnss/raw_doppler_ablation_decision.py",
            "scripts/experiments/run_n5c_raw_doppler_ablation_protocol.py",
            "docs/experiments/n5c_raw_doppler_ablation_protocol.md",
            "docs/experiments/n5c_raw_doppler_factor_diagnostics.md",
            "docs/experiments/n5c_raw_doppler_velocity_comparison.md",
            "docs/experiments/n5c_ablation_decision.md",
            "docs/experiments/n5c_next_stage_plan.md",
            "docs/codex_prompts/N5C_raw_doppler_ablation_protocol.md",
        ]
    )
    _toy_ablation()
    _check_no_artifacts()
    _check_no_local_path_leak()
    print("audit_n5c_raw_doppler_ablation_protocol passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
