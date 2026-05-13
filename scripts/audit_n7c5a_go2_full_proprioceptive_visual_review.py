#!/usr/bin/env python3
"""Audit N7C5A Go2 full proprioceptive visual review workflow.

中文说明：检查 N7C5A 图像复核产物、边界和 toy runtime。
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_full_proprioceptive_visual_loader.py",
    "src/legsa_gins/go2_prior/go2_full_proprioceptive_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_full_proprioceptive_visual_sanity.py",
    "src/legsa_gins/go2_prior/go2_full_proprioceptive_plot_coverage.py",
    "src/legsa_gins/go2_prior/go2_n7c5a_decision.py",
    "scripts/experiments/run_n7c5a_go2_full_proprioceptive_visual_review.py",
    "scripts/audit_n7c5a_required_figures_nonempty.py",
    "docs/experiments/n7c5a_go2_full_proprioceptive_visual_review.md",
    "docs/experiments/n7c5a_plot_catalog.md",
    "docs/experiments/n7c5a_decision.md",
    "docs/codex_prompts/N7C5A_go2_full_proprioceptive_visual_review.md",
]

REQUIRED_OUTPUTS = [
    "N7C5A_VISUAL_SANITY_REPORT.json",
    "N7C5A_PLOT_DATA_COVERAGE_REPORT.json",
    "N7C5A_VISUAL_DECISION_REPORT.json",
    "N7C5A_FIGURE_MANIFEST.json",
    "N7C5A_VISUAL_REVIEW_RUN_REPORT.json",
    "n7c5a_visual_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_PROPRIOCEPTIVE_FACTOR_PRIORS\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c5a_go2_full_proprioceptive_visual_review failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for token in ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users", "/home/kaiwen/" + "legsa_external_artifacts"]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")


def _check_no_forbidden_tracked_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden runtime/figure artifact tracked: " + ", ".join(hits[:8]))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _prepare_n7c5_root(root: Path, count: int = 80) -> Path:
    n7c5 = root / "n7c5"
    times = [index * 0.1 for index in range(count)]
    _write_json(
        n7c5 / "GO2_FULL_FIELD_INVENTORY_REPORT.json",
        {
            "row_count": count,
            "not_truth": True,
            "fields": {
                name: {"available": True}
                for name in [
                    "quaternion",
                    "rpy",
                    "gyroscope",
                    "accelerometer",
                    "position",
                    "velocity",
                    "yaw_speed",
                    "mode",
                    "gait_type",
                    "foot_force",
                    "foot_position_body",
                    "foot_speed_body",
                ]
            },
            "update_rate": {"rate_hz_p50": 10.0, "time_span_sec": times[-1] if times else 0.0},
        },
    )
    _write_json(
        n7c5 / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json",
        {
            "usable_as_weight": True,
            "usable_as_factor": False,
            "support_probability_mean": 0.7,
            "uncertainty_probability_mean": 0.2,
            "swing_probability_mean": 0.3,
            "foot_probability_stats": {f"foot_{foot}_contact_probability": {"mean": 0.7, "p95": 0.9} for foot in range(4)},
            "contact_truth_claim": False,
        },
    )
    _write_json(
        n7c5 / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json",
        {
            "candidate_generated": True,
            "fused_velocity_availability": 1.0,
            "physical_plausibility": "plausible",
            "activation_candidate": "diagnostic_only",
            "go2_velocity_truth_claim": False,
        },
    )
    _write_json(n7c5 / "GO2_MODE_GAIT_PHASE_MODEL_REPORT.json", {"phase_counts": {"walking": count}, "paper_performance_claim": False})
    _write_json(
        n7c5 / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json",
        {
            "stability_status": "stable",
            "yaw_speed_vs_yaw_derivative_rmse_radps": 0.01,
            "yaw_speed_derivative_corr": 0.95,
            "yaw_speed_vs_gyro_z_rmse_radps": 0.01,
            "yaw_speed_gyro_z_corr": 0.96,
        },
    )
    _write_json(
        n7c5 / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json",
        {
            "relative_odometry_stability": "stable",
            "go2_position_delta_rmse_m": 0.05,
            "integrated_go2_velocity_delta_rmse_m": 0.04,
            "position_vs_integrated_velocity_error_rmse_m": 0.03,
            "ekf_displacement_delta_rmse_m": 0.06,
        },
    )
    _write_json(
        n7c5 / "GO2_PROPRIOCEPTIVE_FACTOR_RANKING_REPORT.json",
        {
            "candidates": [
                {"factor_id": "go2_horizontal_velocity_fixed_1p0", "score": 86, "risk_level": "low", "novelty_value": 65},
                {"factor_id": "foot_kinematic_velocity_candidate", "score": 68, "risk_level": "medium", "novelty_value": 80},
                {"factor_id": "contact_probability_weighting", "score": 64, "risk_level": "low", "novelty_value": 60},
            ],
            "recommended_EKF_next_factor": "go2_horizontal_velocity_fixed_1p0",
        },
    )
    _write_json(
        n7c5 / "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_DECISION_REPORT.json",
        {"status": "go2_horizontal_velocity_and_attitude_factor_sufficient", "go2_not_truth": True},
    )
    _write_json(n7c5 / "N7C5_FIGURE_MANIFEST.json", {"figure_count_total": 10, "required_figures_generated": True, "required_figures_nonempty": True})
    _write_csv(
        n7c5 / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv",
        [
            {
                "time": t,
                "foot_0_contact_probability": 0.7,
                "foot_1_contact_probability": 0.8,
                "foot_2_contact_probability": 0.6,
                "foot_3_contact_probability": 0.75,
                "support_probability": 0.72,
                "uncertainty_probability": 0.18,
                "swing_probability": 0.28,
            }
            for t in times
        ],
    )
    _write_csv(
        n7c5 / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv",
        [
            {
                "time": t,
                "candidate_vn": 1.0,
                "candidate_ve": 0.2,
                "go2_vn": 1.0,
                "go2_ve": 0.2,
                "receiver_vn": 1.02,
                "receiver_ve": 0.22,
                "raw_vn": 0.98,
                "raw_ve": 0.18,
                "residual_to_receiver": 0.03,
                "residual_to_raw": 0.03,
                "residual_to_go2": 0.0,
                "slip_risk": 0.2,
            }
            for t in times
        ],
    )
    _write_csv(n7c5 / "GO2_MODE_GAIT_PHASE_TIMESERIES.csv", [{"time": t, "phase": "walking"} for t in times])
    return n7c5


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c5a_visual_") as tmp_value:
        tmp = Path(tmp_value)
        n7c5 = _prepare_n7c5_root(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        proc = _run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n7c5a_go2_full_proprioceptive_visual_review.py"),
                "--n7c5-root",
                str(n7c5),
                "--output-dir",
                str(out),
                "--figure-output-dir",
                str(figs),
                "--allow-run",
            ]
        )
        if proc.returncode != 0:
            _fail(proc.stdout + proc.stderr)
        for rel in REQUIRED_OUTPUTS:
            if not (out / rel).exists():
                _fail(f"missing output {rel}")
        decision = json.loads((out / "N7C5A_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
        figures = json.loads((out / "N7C5A_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        sanity = json.loads((out / "N7C5A_VISUAL_SANITY_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") != "n7c5_visual_review_passed":
            _fail(f"unexpected decision {decision}")
        if decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_vertical_velocity_prior_enabled"):
            _fail("forbidden prior enabled")
        if figures.get("figure_count_total") != 18 or not figures.get("required_figures_nonempty"):
            _fail("required figures missing or empty")
        if sanity.get("visual_blocker"):
            _fail("toy visual sanity unexpectedly blocked")


def main() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c5a_go2_full_proprioceptive_visual_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
