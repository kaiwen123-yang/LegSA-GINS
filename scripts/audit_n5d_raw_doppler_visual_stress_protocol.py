#!/usr/bin/env python3
"""Audit N5D raw Doppler visual/stress protocol.

中文说明：该审计只检查模块、docs、toy 图像/报告链路和边界旗标；不读取真实
大数据，不提交图像，不做 paper performance claim。
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_n5d_decision import make_n5d_decision
from legsa_gins.raw_gnss.raw_doppler_stress_evaluator import evaluate_n5d_stress_pairs
from legsa_gins.raw_gnss.raw_doppler_stress_matrix import REQUIRED_VARIANT_IDS, build_n5d_stress_matrix
from legsa_gins.raw_gnss.raw_doppler_visual_loader import load_n5d_visual_inputs
from legsa_gins.raw_gnss.raw_doppler_visual_plots import REQUIRED_FIGURE_NAMES, generate_n5d_visual_plots
from legsa_gins.raw_gnss.raw_doppler_visual_sanity import build_visual_sanity_report

ARTIFACT_RE = re.compile(
    r"(gnss1-raw\.csv|gnss2-raw\.csv|corr-raw\.csv|\.ubx$|\.obs$|\.nav$|\.sp3$|\.clk$|"
    r"input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|RAW_DOPPLER_VELOCITY_FACTORS\.csv|"
    r"summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"FAILED: {message}")


def _must_exist(paths: list[str]) -> None:
    missing = [rel for rel in paths if not (ROOT / rel).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for pattern in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", pattern, "--", "."]):
            _fail(f"local path leak: {pattern}")


def _check_no_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("generated/raw artifact tracked: " + ", ".join(hits[:8]))


def _write_factor(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for index in range(40):
            writer.writerow(
                {
                    "time": float(index),
                    "vn": 1.0 + 0.01 * math.sin(index / 3.0),
                    "ve": 0.2,
                    "vd": -0.1,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 8 + index % 3,
                    "provider_status": "available",
                    "quality_flag": "ok",
                }
            )


def _toy_reports(tmp: Path) -> list[dict[str, object]]:
    def summary(h: float, up: float, yaw: float, roll: float = 0.1, pitch: float = 0.1) -> dict[str, float]:
        return {"horizontal_rmse_m": h, "up_rmse_m": up, "yaw_rmse_deg": yaw, "roll_rmse_deg": roll, "pitch_rmse_deg": pitch}

    rows = [
        ("baseline_full", summary(1.0, 1.0, 1.0), 0, False, "none"),
        ("baseline_plus_raw_doppler_r1", summary(0.98, 1.0, 0.9), 40, True, "none"),
        ("position_yaw_only", summary(2.0, 1.2, 1.6), 0, False, "disabled"),
        ("position_yaw_plus_raw_doppler_r1", summary(1.8, 1.1, 1.1), 40, True, "disabled"),
        ("receiver_velocity_disabled_no_raw", summary(2.4, 1.3, 1.7), 0, False, "disabled"),
        ("receiver_velocity_disabled_plus_raw", summary(1.9, 1.2, 1.1), 40, True, "disabled"),
        ("receiver_velocity_std_scale_5_no_raw", summary(1.5, 1.1, 1.4), 0, False, "std_scale"),
        ("receiver_velocity_std_scale_5_plus_raw", summary(1.3, 1.0, 1.1), 40, True, "std_scale"),
        ("receiver_velocity_outage_30s_no_raw", summary(2.1, 1.4, 1.5), 0, False, "outage"),
        ("receiver_velocity_outage_30s_plus_raw", summary(1.8, 1.3, 1.2), 40, True, "outage"),
        ("receiver_velocity_noise_0p5_no_raw", summary(1.8, 1.2, 1.6), 0, False, "additive_noise"),
        ("receiver_velocity_noise_0p5_plus_raw", summary(1.5, 1.1, 1.2), 40, True, "additive_noise"),
    ]
    reports = []
    for name, metrics, updates, raw_enabled, mode in rows:
        variant_dir = tmp / "variants" / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        reports.append(
            {
                "variant_id": name,
                "summary": metrics,
                "parity_metrics": metrics,
                "raw_doppler_update_count": updates,
                "raw_doppler_reject_count": 0,
                "enable_raw_doppler": raw_enabled,
                "raw_doppler_solver_enabled": raw_enabled,
                "receiver_velocity_stress_mode": mode,
                "diagnostic_only": name not in {"baseline_full", "baseline_plus_raw_doppler_r1"},
                "diagnostic_stress_only": name not in {"baseline_full", "baseline_plus_raw_doppler_r1"},
                "output_dir": str(variant_dir),
                "paper_performance_claim": False,
                "proposed_factor_claim": False,
                "no_outperform_final_v23_claim": True,
            }
        )
    return reports


def _toy_visual() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n5d_visual_audit_") as tmp_value:
        tmp = Path(tmp_value)
        factor = tmp / "factor.csv"
        _write_factor(factor)
        clean = tmp / "clean"
        clean.mkdir()
        (clean / "clean.gnss").write_text("\n".join(f"{i} 0 0 0 0 0 0 {1.05+i*0.001} 0.2 -0.1 0 0 0 0 0" for i in range(40)) + "\n", encoding="utf-8")
        matrix = build_n5d_stress_matrix(factor, tmp / "out")
        rows = {row["variant_id"]: row for row in matrix["matrix"]}
        for required in REQUIRED_VARIANT_IDS:
            if required not in rows:
                _fail(f"stress matrix missing {required}")
        reports = _toy_reports(tmp)
        stress = evaluate_n5d_stress_pairs(reports)
        inputs = load_n5d_visual_inputs(factor_csv=factor, clean_root=clean, n5c_root=None, variant_reports=reports)
        inputs["variant_error_rows"] = {
            name: [
                {
                    "timestamp": float(index),
                    "horizontal_error_m": float(report["summary"]["horizontal_rmse_m"]) + index * 0.0,
                    "up_error_m": float(report["summary"]["up_rmse_m"]),
                    "yaw_error_deg": float(report["summary"]["yaw_rmse_deg"]),
                    "roll_error_deg": float(report["summary"]["roll_rmse_deg"]),
                    "pitch_error_deg": float(report["summary"]["pitch_rmse_deg"]),
                }
                for index in range(40)
            ]
            for name, report in {str(row["variant_id"]): row for row in reports}.items()
        }
        manifest = generate_n5d_visual_plots(inputs, output_dir=tmp / "reports", figure_output_dir=tmp / "figs", stress_eval=stress)
        sanity = build_visual_sanity_report(inputs=inputs, figure_manifest=manifest, stress_eval=stress)
        decision = make_n5d_decision(sanity, stress)
        final_manifest = generate_n5d_visual_plots(inputs, output_dir=tmp / "reports", figure_output_dir=tmp / "figs", stress_eval=stress, visual_sanity=sanity, decision=decision)
        if final_manifest["figure_count_total"] < 25:
            _fail("toy figure count below requirement")
        if not all((tmp / "figs" / rel).exists() for rel in REQUIRED_FIGURE_NAMES):
            _fail("toy missing required figures")
        for report in [stress, sanity, decision]:
            if report.get("paper_performance_claim") is not False or report.get("proposed_factor_claim") is not False:
                _fail("toy report boundary flags invalid")


def main() -> int:
    _must_exist(
        [
            "src/legsa_gins/raw_gnss/raw_doppler_visual_loader.py",
            "src/legsa_gins/raw_gnss/raw_doppler_visual_plots.py",
            "src/legsa_gins/raw_gnss/raw_doppler_visual_sanity.py",
            "src/legsa_gins/raw_gnss/raw_doppler_stress_matrix.py",
            "src/legsa_gins/raw_gnss/raw_doppler_stress_runner.py",
            "src/legsa_gins/raw_gnss/raw_doppler_stress_evaluator.py",
            "src/legsa_gins/raw_gnss/raw_doppler_n5d_decision.py",
            "scripts/experiments/run_n5d_raw_doppler_visual_stress_protocol.py",
            "docs/experiments/n5d_raw_doppler_visual_validation.md",
            "docs/experiments/n5d_raw_doppler_stress_protocol.md",
            "docs/experiments/n5d_raw_doppler_visual_plot_catalog.md",
            "docs/experiments/n5d_decision.md",
            "docs/experiments/n5d_next_stage_plan.md",
            "docs/codex_prompts/N5D_raw_doppler_visual_stress_protocol.md",
        ]
    )
    _toy_visual()
    _check_no_artifacts()
    _check_no_local_path_leak()
    print("audit_n5d_raw_doppler_visual_stress_protocol passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
