#!/usr/bin/env python3
"""Audit N8F legged candidate factor activation on toy runtime.

中文说明：用临时 runtime 验证 contact/foot/yaw-rate/relative-odometry 因子真实
进入 residual/Jacobian/toggle 链路，同时检查 no-feedback 和 no-claim 边界。
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
    "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json",
    "FGO_CONTACT_AWARE_WEIGHTING_TIMESERIES.csv",
    "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json",
    "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_TABLE.csv",
    "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json",
    "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json",
    "FGO_LEGGED_FACTOR_JACOBIAN_CHECK_REPORT.json",
    "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json",
    "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json",
    "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json",
    "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json",
    "N8F_FIGURE_MANIFEST.json",
    "n8f_legged_candidate_factor_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES|GO2_RELATIVE_ODOMETRY|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8f_legged_candidate_factor_activation failed: {message}")


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


def _write_ekf_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(18):
            writer.writerow(
                {
                    "index": index,
                    "time": index * 0.2,
                    "lat_deg": 30.0 + index * 1.0e-6,
                    "lon_deg": 120.0 + index * 1.2e-6,
                    "height_m": 10.0 + 0.01 * index,
                    "roll_deg": 0.04 * index,
                    "pitch_deg": 0.015 * index,
                    "yaw_deg": 2.0 * index,
                    "vn_mps": 1.0 + 0.02 * index,
                    "ve_mps": 0.12 + 0.005 * index,
                    "vd_mps": 0.0,
                }
            )


def _write_raw_doppler_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "doppler_obs_count", "provider_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(18):
            writer.writerow(
                {
                    "time": index * 0.2,
                    "vn": 0.95 + 0.018 * index,
                    "ve": 0.08 + 0.004 * index,
                    "vd": 0.0,
                    "std_vn": 0.25,
                    "std_ve": 0.25,
                    "std_vd": 0.35,
                    "sat_count": 20,
                    "doppler_obs_count": 32,
                    "provider_status": "available",
                }
            )


def _write_n7c5_runtime(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "time",
            "candidate_vn",
            "candidate_ve",
            "candidate_vd",
            "weight_sum",
            "stance_foot_count",
            "slip_risk",
            "go2_vn",
            "go2_ve",
            "receiver_vn",
            "receiver_ve",
            "raw_vn",
            "raw_ve",
            "residual_to_go2",
            "residual_to_receiver",
            "residual_to_raw",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(18):
            writer.writerow(
                {
                    "time": index * 0.2,
                    "candidate_vn": 0.90 + 0.016 * index,
                    "candidate_ve": 0.07 + 0.004 * index,
                    "candidate_vd": 0.0,
                    "weight_sum": 2.0,
                    "stance_foot_count": 2,
                    "slip_risk": 0.25 + 0.02 * (index % 4),
                    "go2_vn": 0.91 + 0.016 * index,
                    "go2_ve": 0.07 + 0.004 * index,
                    "receiver_vn": 1.0 + 0.02 * index,
                    "receiver_ve": 0.12 + 0.005 * index,
                    "raw_vn": 0.95 + 0.018 * index,
                    "raw_ve": 0.08 + 0.004 * index,
                    "residual_to_go2": 0.05,
                    "residual_to_receiver": 0.10,
                    "residual_to_raw": 0.08,
                }
            )
    with (root / "GO2_MODE_GAIT_PHASE_TIMESERIES.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["time", "mode", "gait_type", "velocity_norm", "yaw_speed_abs", "body_height", "support_probability", "phase", "reason_codes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(18):
            writer.writerow(
                {
                    "time": index * 0.2,
                    "mode": "walk",
                    "gait_type": "trot",
                    "velocity_norm": 1.0,
                    "yaw_speed_abs": 0.15,
                    "body_height": 0.32,
                    "support_probability": 0.72 - 0.03 * (index % 3),
                    "phase": "support",
                    "reason_codes": "toy",
                }
            )
    _write_json(
        root / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json",
        {"activation_candidate": "diagnostic_only", "row_count": 18, "not_truth": True, "no_trace_tuning": True},
    )
    _write_json(
        root / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json",
        {"row_count": 18, "recommended_use": "weighting_only", "contact_truth_claim": False, "no_trace_tuning": True},
    )
    _write_json(
        root / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json",
        {"row_count": 18, "recommendation": "between_factor", "go2_yaw_truth_claim": False},
    )
    _write_json(
        root / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json",
        {"window_count": 17, "recommendation": "between_factor", "absolute_position_truth_claim": False, "relative_odometry_scale_hint": 1.0},
    )


def _prepare_runtime(root: Path) -> dict[str, Path]:
    paths = {
        "n8a": root / "N8A_no_feedback_fgo_foundation",
        "n8a2": root / "N8A2_fgo_yaw_convention_fix",
        "n8b": root / "N8B_fgo_factor_graph_policy_review",
        "n8e": root / "N8E_formal_engineering_ablation_with_caveat",
        "n8d": root / "N8D_fgo_factor_weight_policy_review",
        "n8c3": root / "N8C3_raw_doppler_fgo_factor_fix",
        "n7c5": root / "N7C5_go2_full_proprioceptive_factor_mining",
        "n7c6": root / "N7C6_go2_proprioceptive_joint_factor",
        "n5b": root / "N5B_rtklib_doppler_provider_activation",
        "n6b": root / "N6B_source_aware_policy_refinement",
    }
    _write_ekf_csv(paths["n8a"] / "N8A_EKF_STATE_NODES.csv")
    _write_raw_doppler_csv(paths["n5b"] / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_n7c5_runtime(paths["n7c5"])
    _write_json(paths["n8a2"] / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(paths["n7c6"] / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", {"status": "go2_joint_factor_review_passed"})
    _write_json(paths["n8e"] / "N8E_FORMAL_ABLATION_WITH_CAVEAT_DECISION_REPORT.json", {"status": "formal_engineering_ablation_ready_with_caveats"})
    _write_json(paths["n8d"] / "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json", {"status": "raw_doppler_active_but_low_fgo_marginal_value"})
    _write_json(paths["n8c3"] / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json", {"status": "raw_doppler_active_consistent_or_dominated"})
    _write_json(paths["n6b"] / "N6B_SOURCE_AWARE_DECISION_REPORT.json", {"status": "ready"})
    return paths


def _run_n8f(root: Path) -> Path:
    paths = _prepare_runtime(root)
    out = root / "N8F_legged_candidate_factor_activation"
    figs = root / "N8F_figs"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8f_legged_candidate_factor_activation.py"),
            "--n8e-root",
            str(paths["n8e"]),
            "--n8d-root",
            str(paths["n8d"]),
            "--n8c3-root",
            str(paths["n8c3"]),
            "--n8b-root",
            str(paths["n8b"]),
            "--n8a2-root",
            str(paths["n8a2"]),
            "--n7c5-root",
            str(paths["n7c5"]),
            "--n7c6-root",
            str(paths["n7c6"]),
            "--n5b-root",
            str(paths["n5b"]),
            "--n6b-root",
            str(paths["n6b"]),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
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


def _check_contact(out: Path) -> None:
    report = _read(out / "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json")
    if report.get("rows", 0) <= 0 or report.get("finite_ratio", 0.0) <= 0.9:
        _fail("contact-aware weighting rows/finite ratio invalid")
    if report.get("hard_contact_truth") or report.get("direct_state_residual"):
        _fail("contact-aware weighting claimed hard truth or direct residual")
    if not report.get("no_trace_tuning"):
        _fail("contact-aware weighting trace tuning boundary failed")


def _check_foot(out: Path) -> None:
    report = _read(out / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json")
    if report.get("factor_rows", 0) <= 0 or report.get("residual_rows", 0) <= 0 or report.get("jacobian_nonzero_count", 0) <= 0:
        _fail("foot kinematic factor did not enter residual/Jacobian")
    if not report.get("toggle_works"):
        _fail("foot kinematic toggle did not change residual rows")
    if report.get("go2_truth_claim") or report.get("no_vertical_velocity_factor") is not True:
        _fail("foot kinematic truth/vertical boundary failed")


def _check_yawrate(out: Path) -> None:
    report = _read(out / "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json")
    if report.get("factor_rows", 0) <= 0 or report.get("residual_rows", 0) <= 0:
        _fail("yaw-rate factor did not enter residual vector")
    if not report.get("wrap_boundary_test_passed") or report.get("absolute_yaw_truth_claim"):
        _fail("yaw-rate wrap or truth boundary failed")


def _check_relative(out: Path) -> None:
    report = _read(out / "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json")
    if report.get("factor_rows", 0) <= 0 or report.get("residual_rows", 0) <= 0:
        _fail("relative odometry factor did not enter residual vector")
    if report.get("absolute_go2_position_factor") or report.get("go2_position_truth_claim"):
        _fail("relative odometry absolute position/truth boundary failed")


def _check_jacobian(out: Path) -> None:
    contracts = _read(out / "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json")
    jac = _read(out / "FGO_LEGGED_FACTOR_JACOBIAN_CHECK_REPORT.json")
    if not jac.get("all_passed") or not contracts.get("all_jacobian_checks_passed"):
        _fail("Jacobian toy checks failed")
    if not contracts.get("all_no_truth_claim"):
        _fail("contract truth boundary failed")


def _check_variant_decision(out: Path) -> None:
    variants = _read(out / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json")
    comparison = _read(out / "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json")
    decision = _read(out / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json")
    figures = _read(out / "N8F_FIGURE_MANIFEST.json")
    if variants.get("variant_count") != 12 or not variants.get("all_real_solver_reruns"):
        _fail("N8F variant rerun count invalid")
    if not comparison.get("candidate_solver_injection_passed"):
        _fail("candidate solver injection failed")
    if not figures.get("required_figures_generated") or not figures.get("required_figures_nonempty"):
        _fail("N8F figures missing or empty")
    if not decision.get("status") or decision.get("paper_performance_claim") or decision.get("fgo_output_feedback_to_ekf"):
        _fail("N8F decision boundary failed")


def _check_no_trace(out: Path) -> None:
    variants = _read(out / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json")
    if not variants.get("all_no_trace_finalv23_tuning"):
        _fail("trace/final_v23 tuning boundary failed")


def _check_no_feedback(out: Path) -> None:
    variants = _read(out / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json")
    decision = _read(out / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json")
    if not variants.get("all_no_feedback") or not variants.get("all_no_substitution"):
        _fail("variant feedback/substitution boundary failed")
    if decision.get("fgo_output_feedback_to_ekf") or decision.get("output_substitution"):
        _fail("decision feedback/substitution boundary failed")


def _check_no_truth(out: Path) -> None:
    contracts = _read(out / "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json")
    variants = _read(out / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json")
    decision = _read(out / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json")
    if not contracts.get("all_no_truth_claim") or not variants.get("all_no_go2_truth_claim") or not decision.get("no_go2_truth_claim"):
        _fail("Go2 truth boundary failed")


CHECKS = {
    "all": [_check_contact, _check_foot, _check_yawrate, _check_relative, _check_jacobian, _check_variant_decision, _check_no_trace, _check_no_feedback, _check_no_truth],
    "contact": [_check_contact],
    "foot": [_check_foot],
    "yawrate": [_check_yawrate],
    "relative": [_check_relative],
    "jacobian": [_check_jacobian],
    "no_trace": [_check_no_trace],
    "no_feedback": [_check_no_feedback],
    "no_truth": [_check_no_truth],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=sorted(CHECKS), default="all")
    args = parser.parse_args()
    _check_hygiene()
    with tempfile.TemporaryDirectory(prefix="n8f_audit_") as tmp:
        out = _run_n8f(Path(tmp))
        _check_outputs(out)
        for check in CHECKS[args.check]:
            check(out)
    print(f"audit_n8f_legged_candidate_factor_activation passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

