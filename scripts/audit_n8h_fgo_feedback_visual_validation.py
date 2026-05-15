#!/usr/bin/env python3
"""Audit N8H feedback visual-validation reports.

中文说明：审计 N8H 报告、图像和禁止边界，缺少运行期路径时使用 toy。
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import N8G_VARIANT_ORDER, write_json


REQUIRED_REPORTS = [
    "N8H_VISUAL_INPUT_MANIFEST.json",
    "FGO_FEEDBACK_POSITION_DISABLED_AUDIT_REPORT.json",
    "N8H_FEEDBACK_VARIANT_ABLATION_REVIEW.json",
    "FGO_FEEDBACK_GATE_VISUAL_REVIEW_REPORT.json",
    "FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json",
    "N8H_PLOT_SEMANTIC_GUARD_REPORT.json",
    "N8H_PLOT_DATA_COVERAGE_REPORT.json",
    "N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json",
    "N8H_FIGURE_MANIFEST.json",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8h_fgo_feedback_visual_validation failed: {message}")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_root() -> Path | None:
    value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            _fail(f"missing report {name}")
    manifest = _json(root / "N8H_VISUAL_INPUT_MANIFEST.json")
    decision = _json(root / "N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json")
    coverage = _json(root / "N8H_PLOT_DATA_COVERAGE_REPORT.json")
    if not manifest.get("all_required_n8g_reports_found"):
        _fail("N8G required reports not all found")
    if decision.get("fgo_feedback_output_substitution") is not False:
        _fail("decision allows output substitution")
    if decision.get("fgo_feedback_direct_nav_override") is not False:
        _fail("decision allows direct NAV override")
    if decision.get("trace_solver_input") is not False or decision.get("final_v23_output_solver_input") is not False:
        _fail("decision allows trace/final_v23 solver input")
    if decision.get("paper_performance_claim") is not False:
        _fail("decision allows paper claim")
    if coverage.get("all_required_figures_nonempty") is not True:
        _fail("required figures are not nonempty")


def audit_toy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        n8g = tmp_root / "n8g"
        n8h = tmp_root / "n8h"
        figs = tmp_root / "figs"
        make_toy_n8g_root(n8g)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n8h_fgo_feedback_visual_validation.py"),
                "--n8g-root",
                str(n8g),
                "--n8f1-root",
                str(tmp_root / "n8f1"),
                "--n8f-root",
                str(tmp_root / "n8f"),
                "--n8e-root",
                str(tmp_root / "n8e"),
                "--output-dir",
                str(n8h),
                "--figure-output-dir",
                str(figs),
                "--allow-run",
                "--rerun-missing-timeseries",
                "true",
            ],
            check=True,
        )
        audit_runtime(n8h)


def make_toy_n8g_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    times = [float(index) for index in range(6)]
    write_json(
        root / "SLIDING_WINDOW_MANAGER_REPORT.json",
        {
            "stage": "N8G",
            "window_count": 6,
            "feedback_time": times,
            "window_start": [max(0.0, time - 2.0) for time in times],
            "window_end": times,
            "window_duration_s": 2.0,
            "feedback_stride_s": 1.0,
            "window_epoch_count": [3, 3, 3, 3, 3, 3],
            "no_future_data_verified": True,
            "overlap_stats": {"min_epoch_count": 3, "max_epoch_count": 3},
        },
    )
    write_json(root / "FGO_FEEDBACK_OBSERVATION_BUILD_REPORT.json", {"stage": "N8G", "feedback_rows": 6})
    write_json(root / "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json", {"stage": "N8G", "no_R_shrink": True, "no_trace_tuning": True})
    write_json(
        root / "FGO_FEEDBACK_GATE_REPORT.json",
        {
            "stage": "N8G",
            "feedback_count": 6,
            "accept_count": 6,
            "reject_count": 0,
            "reject_reasons": {},
            "correction_norm_stats": {
                "position_m": {"p50": 0.1, "p95": 0.2, "max": 0.3},
                "velocity_mps": {"p50": 0.02, "p95": 0.03, "max": 0.04},
                "attitude_deg": {"p50": 0.2, "p95": 0.4, "max": 0.5},
            },
            "gate_thresholds": {
                "max_position_correction_m": 6.0,
                "max_velocity_correction_mps": 1.5,
                "max_attitude_correction_deg": 8.0,
                "max_yaw_correction_deg": 8.0,
            },
            "no_future_data": True,
        },
    )
    summaries = []
    eval_results = []
    for variant in N8G_VARIANT_ORDER:
        position_enabled = "position_velocity" in variant
        velocity_enabled = "velocity" in variant
        attitude_enabled = "attitude" in variant
        reject_all = "reject_all" in variant
        baseline = variant == "ekf_baseline_no_fgo_feedback"
        accept_count = 0 if baseline or reject_all else 6
        summaries.append(
            {
                "variant_id": variant,
                "feedback_mode": "no_feedback_baseline" if baseline else "horizontal_velocity_attitude_feedback",
                "position_enabled": position_enabled,
                "velocity_enabled": velocity_enabled,
                "attitude_enabled": attitude_enabled,
                "reject_all": reject_all,
                "diagnostic_only": position_enabled,
                "feedback_update_count": accept_count,
                "feedback_accept_count": accept_count,
                "feedback_reject_count": 0,
                "fgo_feedback_enabled": not baseline,
                "no_output_substitution": True,
                "no_direct_nav_override": True,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "paper_performance_claim": False,
            }
        )
        if not baseline:
            max_delta = 0.0 if reject_all else 0.01
            eval_results.append(
                {
                    "variant_id": variant,
                    "row_count_compared": 6,
                    "accepted": accept_count,
                    "rejected": 0,
                    "feedback_vs_baseline_delta": {
                        "horizontal_m": {"p50": 0.0, "p95": max_delta, "max": max_delta},
                        "yaw_deg": {"p50": 0.0, "p95": max_delta, "max": max_delta},
                        "roll_pitch_deg": {"p50": 0.0, "p95": max_delta, "max": max_delta},
                    },
                    "clean_gross_degradation": False,
                    "trace_solver_input": False,
                    "final_v23_output_solver_input": False,
                    "paper_performance_claim": False,
                }
            )
    boundary = {
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    write_json(root / "N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json", {"stage": "N8G", "variants": summaries, **boundary})
    write_json(root / "N8G_FGO_FEEDBACK_COMPARISON_REPORT.json", {"stage": "N8G", "gross_degradation_status": "absent", **boundary})
    write_json(root / "N8G_FGO_FEEDBACK_EVALUATION_REPORT.json", {"stage": "N8G", "variant_results": eval_results, **boundary})
    write_json(root / "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json", {"stage": "N8G", "status": "fgo_feedback_ekf_foundation_ready", "fgo_feedback_no_future_data": True, **boundary})
    write_json(root / "N8G_FIGURE_MANIFEST.json", {"stage": "N8G", "figure_count_total": 12, "all_required_figures_present": True})
    for variant in N8G_VARIANT_ORDER:
        _write_variant_toy(root, variant, times)


def _write_variant_toy(root: Path, variant: str, times: list[float]) -> None:
    variant_root = root / "variants" / variant
    run_root = variant_root / "run"
    run_root.mkdir(parents=True, exist_ok=True)
    position_enabled = "position_velocity" in variant
    velocity_enabled = "velocity" in variant
    attitude_enabled = "attitude" in variant
    reject_all = "reject_all" in variant
    baseline = variant == "ekf_baseline_no_fgo_feedback"
    _write_csv(
        run_root / "EVAL_NAV.csv",
        ["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"],
        [
            {
                "time": time,
                "lat_deg": 30.0 + time * 1.0e-6 + (0.0 if baseline or reject_all else 1.0e-9),
                "lon_deg": 120.0 + time * 1.0e-6,
                "height_m": 10.0,
                "vn": 1.0,
                "ve": 0.0,
                "vd": 0.0,
                "roll_deg": 0.0,
                "pitch_deg": 0.0,
                "yaw_deg": time * 0.1 + (0.0 if baseline or reject_all else 0.001),
            }
            for time in times
        ],
    )
    write_json(
        run_root / "RUN_MANIFEST.json",
        {
            "fgo_feedback_enabled": not baseline,
            "feedback_observation_count": 6 if not baseline else 0,
            "feedback_update_count": 0 if baseline or reject_all else 6,
            "feedback_accept_count": 0 if baseline or reject_all else 6,
            "feedback_reject_count": 0,
            "feedback_position_enabled": position_enabled,
            "feedback_velocity_enabled": velocity_enabled,
            "feedback_attitude_enabled": attitude_enabled,
            "fgo_feedback_output_substitution": False,
            "fgo_feedback_direct_nav_override": False,
            "fgo_feedback_no_future_data": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        },
    )
    if baseline:
        return
    obs_rows = []
    trace_rows = []
    for time in times:
        valid = 0 if reject_all else 1
        obs_rows.append(
            {
                "time": time,
                "pN": time * 0.1,
                "pE": time * 0.01,
                "pD": 0.0,
                "vN": 1.0,
                "vE": 0.0,
                "vD": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": time * 0.1,
                "std_pN": 5.0,
                "std_pE": 5.0,
                "std_pD": 5.0,
                "std_vN": 1.0,
                "std_vE": 1.0,
                "std_vD": 1.0,
                "std_roll": 5.0,
                "std_pitch": 5.0,
                "std_yaw": 5.0,
                "source_window_start": max(0.0, time - 2.0),
                "source_window_end": time,
                "feedback_valid": valid,
                "window_epoch_count": 3,
                "feedback_mode": "position_velocity_attitude_feedback" if position_enabled else "horizontal_velocity_attitude_feedback",
            }
        )
        if valid:
            trace_rows.append(
                {
                    "update_time": time,
                    "observation_time": time,
                    "accepted": 1,
                    "reject_reason": "",
                    "position_norm_m": 0.1 if position_enabled else 0.2,
                    "velocity_norm_mps": 0.02 if velocity_enabled else 0.0,
                    "attitude_norm_deg": 0.3 if attitude_enabled else 0.0,
                    "yaw_residual_deg": 0.1,
                    "source_window_start": max(0.0, time - 2.0),
                    "source_window_end": time,
                    "trace_solver_input": 0,
                    "final_v23_output_solver_input": 0,
                    "output_substitution": 0,
                    "direct_nav_override": 0,
                }
            )
    _write_csv(variant_root / "FGO_FEEDBACK_OBSERVATIONS.csv", list(obs_rows[0]), obs_rows)
    if trace_rows:
        _write_csv(run_root / "FGO_FEEDBACK_UPDATE_TRACE.csv", list(trace_rows[0]), trace_rows)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    root = report_root()
    if root is not None:
        audit_runtime(root)
    else:
        audit_toy()
    print("audit_n8h_fgo_feedback_visual_validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
