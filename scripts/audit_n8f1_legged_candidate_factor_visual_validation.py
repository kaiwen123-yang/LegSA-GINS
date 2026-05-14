#!/usr/bin/env python3
"""Audit N8F1 legged candidate factor visual validation on toy runtime.

中文说明：生成临时 N8F runtime 输入，验证 N8F1 图像、覆盖率、语义和边界。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    "N8F1_VISUAL_INPUT_MANIFEST.json",
    "N8F1_PLOT_DATA_COVERAGE_REPORT.json",
    "N8F1_FACTOR_SIGNAL_REVIEW_REPORT.json",
    "N8F1_PLOT_SEMANTIC_GUARD_REPORT.json",
    "N8F1_VISUAL_SANITY_REPORT.json",
    "N8F1_LEGGED_FACTOR_VISUAL_DECISION_REPORT.json",
    "N8F1_FIGURE_MANIFEST.json",
    "n8f1_visual_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES|GO2_RELATIVE_ODOMETRY|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8f1_legged_candidate_factor_visual_validation failed: {message}")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_hygiene() -> None:
    for token in ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users"]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden tracked artifact: " + ", ".join(hits[:6]))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_n8f_runtime(root: Path) -> Path:
    n8f = root / "N8F"
    n8f.mkdir(parents=True, exist_ok=True)
    rows = 620
    _write_json(
        n8f / "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json",
        {
            "rows": rows,
            "finite_ratio": 1.0,
            "scale_p50": 1.2,
            "scale_p95": 2.1,
            "scale_max": 2.5,
            "used_by_factor": ["FootKinematicVelocityFactor", "RelativeOdometryBetweenFactor"],
            "hard_contact_truth": False,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8f / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json",
        {
            "factor_rows": rows,
            "residual_rows": rows * 2,
            "jacobian_nonzero_count": rows * 2,
            "toggle_works": True,
            "go2_truth_claim": False,
            "whitened_residual_p95": 0.8,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8f / "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json",
        {
            "factor_rows": rows - 1,
            "residual_rows": rows - 1,
            "jacobian_nonzero_count": (rows - 1) * 2,
            "toggle_works": True,
            "wrap_boundary_test_passed": True,
            "absolute_yaw_truth_claim": False,
            "whitened_residual_p50": 0.1,
            "whitened_residual_p95": 0.8,
            "whitened_residual_max": 1.2,
        },
    )
    _write_json(
        n8f / "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json",
        {
            "factor_rows": rows - 1,
            "residual_rows": (rows - 1) * 2,
            "jacobian_nonzero_count": (rows - 1) * 4,
            "toggle_works": True,
            "absolute_go2_position_factor": False,
            "go2_position_truth_claim": False,
            "whitened_residual_p50": 0.2,
            "whitened_residual_p95": 0.9,
            "whitened_residual_max": 1.4,
        },
    )
    _write_json(
        n8f / "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json",
        {"all_jacobian_checks_passed": True, "all_no_truth_claim": True, "all_trace_input_false": True, "all_finalv23_input_false": True},
    )
    variants = []
    names = [
        "n8d_best_balance_baseline",
        "foot_kinematic_velocity_factor",
        "yawrate_between_factor",
        "relative_odometry_between_factor",
        "all_legged_candidate_stack",
    ]
    for index, name in enumerate(names):
        enabled = name != "n8d_best_balance_baseline"
        variants.append(
            {
                "variant": name,
                "solve_status": "solved",
                "finite_output": True,
                "real_solver_rerun": True,
                "foot_kinematic_velocity_enabled": "foot" in name or "all" in name,
                "yawrate_between_enabled": "yawrate" in name or "all" in name,
                "relative_odometry_between_enabled": "relative" in name or "all" in name,
                "candidate_solver_residual_dim": 0 if not enabled else 100 + index,
                "solver_residual_dim_delta_vs_baseline": 0 if not enabled else 100 + index,
                "candidate_whitened_residual_p95": 0.0 if not enabled else 0.7 + index * 0.03,
                "horizontal_delta_p95_m": 0.05 + index * 0.01,
                "yaw_delta_p95_deg": 0.4 + index * 0.02,
                "roll_delta_p95_deg": 0.05,
                "pitch_delta_p95_deg": 0.06,
                "factor_rows_by_type": {
                    "FootKinematicVelocityFactor": rows if "foot" in name or "all" in name else 0,
                    "YawRateBetweenFactor": rows - 1 if "yawrate" in name or "all" in name else 0,
                    "RelativeOdometryBetweenFactor": rows - 1 if "relative" in name or "all" in name else 0,
                },
                "gross_degradation_flag": False,
                "no_feedback": True,
                "output_substitution": False,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "go2_truth_claim": False,
                "paper_performance_claim": False,
            }
        )
    _write_json(
        n8f / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json",
        {
            "variant_count": len(variants),
            "variants": variants,
            "all_real_solver_reruns": True,
            "all_no_feedback": True,
            "all_no_substitution": True,
            "all_no_trace_finalv23_tuning": True,
            "all_no_go2_truth_claim": True,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8f / "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json",
        {
            "variant_count": len(variants),
            "solved_variant_count": len(variants),
            "candidate_solver_injection_passed": True,
            "gross_degradation_variants": [],
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8f / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json",
        {
            "status": "foot_kinematic_factor_ready_for_N8G_feedback_review",
            "recommended_next_stage": "N8G_fgo_feedback_ekf_foundation",
            "no_feedback": True,
            "output_substitution": False,
            "go2_truth_claim": False,
            "paper_performance_claim": False,
        },
    )
    _write_json(n8f / "N8F_FIGURE_MANIFEST.json", {"figure_count_total": 14, "required_figures_nonempty": True})
    with (n8f / "FGO_CONTACT_AWARE_WEIGHTING_TIMESERIES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "contact_weight_scale", "support_confidence", "slip_risk", "uncertainty"])
        writer.writeheader()
        for index in range(rows):
            writer.writerow(
                {
                    "time": index * 0.1,
                    "contact_weight_scale": 1.0 + (index % 50) / 60.0,
                    "support_confidence": 0.8 - (index % 20) / 100.0,
                    "slip_risk": 0.2 + (index % 30) / 100.0,
                    "uncertainty": 0.2,
                }
            )
    with (n8f / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_TABLE.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["factor_type", "state_index", "time", "vn_mps", "ve_mps", "std_vn_mps", "std_ve_mps", "slip_risk", "contact_weight_scale", "measurement_source"],
        )
        writer.writeheader()
        for index in range(rows):
            writer.writerow(
                {
                    "factor_type": "FootKinematicVelocityFactor",
                    "state_index": index,
                    "time": index * 0.1,
                    "vn_mps": 0.4 + index * 0.0005,
                    "ve_mps": 0.1 + index * 0.0003,
                    "std_vn_mps": 1.0,
                    "std_ve_mps": 1.0,
                    "slip_risk": 0.2,
                    "contact_weight_scale": 1.1,
                    "measurement_source": "toy",
                }
            )
    with (n8f / "N8F_LEGGED_CANDIDATE_FACTOR_TABLE.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["variant", "factor_type", "factor_count", "residual_rows", "jacobian_nonzero", "enabled", "diagnostic_only"])
        writer.writeheader()
        for variant in variants:
            for factor_type in ["FootKinematicVelocityFactor", "YawRateBetweenFactor", "RelativeOdometryBetweenFactor"]:
                count = variant["factor_rows_by_type"].get(factor_type, 0)
                writer.writerow(
                    {
                        "variant": variant["variant"],
                        "factor_type": factor_type,
                        "factor_count": count,
                        "residual_rows": count,
                        "jacobian_nonzero": count * 2,
                        "enabled": count > 0,
                        "diagnostic_only": False,
                    }
                )
    return n8f


def _run_n8f1(root: Path) -> Path:
    n8f = _prepare_n8f_runtime(root)
    out = root / "N8F1"
    figs = root / "N8F1_figs"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8f1_legged_candidate_factor_visual_validation.py"),
            "--n8f-root",
            str(n8f),
            "--n8e-root",
            str(root / "N8E"),
            "--n8d-root",
            str(root / "N8D"),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
            "--rerun-missing-timeseries",
            "true",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _fail(proc.stderr[-3000:] or proc.stdout[-3000:])
    return out


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_outputs(out: Path) -> None:
    missing = [name for name in REQUIRED_OUTPUTS if not (out / name).exists()]
    if missing:
        _fail("missing outputs: " + ", ".join(missing))
    for name in REQUIRED_OUTPUTS:
        if (out / name).stat().st_size <= 0:
            _fail(f"empty output: {name}")


def _check_figures(out: Path) -> None:
    manifest = _read(out / "N8F1_FIGURE_MANIFEST.json")
    if manifest.get("figure_count_total") != 23 or not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
        _fail("required N8F1 figures missing or empty")


def _check_signal(out: Path) -> None:
    report = _read(out / "N8F1_FACTOR_SIGNAL_REVIEW_REPORT.json")
    if not report.get("all_new_factors_have_real_signal"):
        _fail("factor signal review failed")
    for key in ["contact_aware_weighting", "foot_kinematic_velocity", "yawrate_between", "relative_odometry_between"]:
        if report.get(key, {}).get("signal_status") == "inactive":
            _fail(f"inactive factor signal: {key}")


def _check_semantics(out: Path) -> None:
    report = _read(out / "N8F1_PLOT_SEMANTIC_GUARD_REPORT.json")
    if not report.get("semantic_guard_passed") or report.get("paper_performance_claim") or report.get("go2_truth_claim"):
        _fail("plot semantic guard failed")


def _check_no_feedback(out: Path) -> None:
    for name in [
        "N8F1_VISUAL_INPUT_MANIFEST.json",
        "N8F1_VISUAL_SANITY_REPORT.json",
        "N8F1_LEGGED_FACTOR_VISUAL_DECISION_REPORT.json",
    ]:
        report = _read(out / name)
        if not report.get("no_feedback") or report.get("output_substitution") or report.get("paper_performance_claim") or report.get("go2_truth_claim"):
            _fail(f"boundary failed in {name}")


def _check_decision(out: Path) -> None:
    report = _read(out / "N8F1_LEGGED_FACTOR_VISUAL_DECISION_REPORT.json")
    if report.get("status") != "legged_candidate_factor_visual_validation_passed":
        _fail("N8F1 decision did not pass visual validation")


CHECKS = {
    "all": [_check_figures, _check_signal, _check_semantics, _check_no_feedback, _check_decision],
    "figures": [_check_figures],
    "signal": [_check_signal],
    "semantics": [_check_semantics],
    "no_feedback": [_check_no_feedback],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=sorted(CHECKS), default="all")
    args = parser.parse_args()
    _check_hygiene()
    with tempfile.TemporaryDirectory(prefix="n8f1_audit_") as tmp:
        out = _run_n8f1(Path(tmp))
        _check_outputs(out)
        for check in CHECKS[args.check]:
            check(out)
    print(f"audit_n8f1_legged_candidate_factor_visual_validation passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

