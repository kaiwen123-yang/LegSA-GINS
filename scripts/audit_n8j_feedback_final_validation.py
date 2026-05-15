#!/usr/bin/env python3
"""Audit N8J feedback final-validation reports.

中文说明：若没有真实 runtime 路径，则生成 toy 报告审计合同；N8J 不做调参或论文性能宣称。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_final_visual_plots import REQUIRED_N8J_FIGURES
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


REQUIRED_REPORTS = [
    "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json",
    "N8J_FINAL_FEEDBACK_VARIANT_SUMMARIES.json",
    "N8J_FINAL_FEEDBACK_COMPARISON_REPORT.json",
    "N8J_FINAL_FEEDBACK_EVALUATION_REPORT.json",
    "N8J_FINAL_FEEDBACK_MANIFEST.json",
    "N8J_FINAL_FEEDBACK_SANITY_REPORT.json",
    "N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json",
    "N8J_FIGURE_MANIFEST.json",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8j_feedback_final_validation failed: {message}")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_root() -> Path | None:
    value = os.environ.get("N8J_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            _fail(f"missing report {name}")
    selected = _json(root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json")
    manifest = _json(root / "N8J_FINAL_FEEDBACK_MANIFEST.json")
    sanity = _json(root / "N8J_FINAL_FEEDBACK_SANITY_REPORT.json")
    decision = _json(root / "N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json")
    figures = _json(root / "N8J_FIGURE_MANIFEST.json")
    if selected.get("n8i_selected_policy_match") is not True:
        _fail("selected policy does not match N8I")
    if manifest.get("runtime_outputs_generated") is not True:
        _fail("runtime outputs missing")
    if sanity.get("all_checks_passed") is not True:
        _fail("final sanity failed")
    if decision.get("status") not in {
        "feedback_joint_filter_ready_for_BY2_packaging",
        "selected_policy_mismatch",
        "runtime_output_missing",
        "feedback_not_entering_ekf",
        "output_substitution_blocker",
        "selected_feedback_policy_not_ready",
    }:
        _fail(f"unexpected decision {decision.get('status')}")
    if decision.get("fgo_feedback_output_substitution") is not False or decision.get("fgo_feedback_direct_nav_override") is not False:
        _fail("decision allows substitution or direct NAV overwrite")
    if decision.get("trace_solver_input") is not False or decision.get("final_v23_output_solver_input") is not False:
        _fail("decision allows forbidden solver input")
    if decision.get("paper_performance_claim") is not False:
        _fail("decision allows paper claim")
    if figures.get("figure_count_total") != len(REQUIRED_N8J_FIGURES):
        _fail("wrong N8J figure count")
    if figures.get("all_required_figures_nonempty") is not True:
        _fail("required figures are not nonempty")


def make_toy_n8j_root(root: Path, figure_root: Path | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    figure_root = figure_root or root / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    boundary = {
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    write_json(root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json", _toy_selected_policy())
    variants = _toy_variants()
    write_json(
        root / "N8J_FINAL_FEEDBACK_VARIANT_SUMMARIES.json",
        {
            "stage": "N8J",
            "variant_count": len(variants),
            "variants": variants,
            "selected_feedback_variant": "n8j_selected_conservative_feedback",
            "reject_all_sanity_passed": True,
            "gross_degradation_present": False,
            **boundary,
        },
    )
    write_json(
        root / "N8J_FINAL_FEEDBACK_COMPARISON_REPORT.json",
        {
            "stage": "N8J",
            "selected_gross_degradation": False,
            "selected_feedback_delta": {"horizontal_m": {"p95": 0.1}, "yaw_deg": {"p95": 0.1}},
            **boundary,
        },
    )
    write_json(
        root / "N8J_FINAL_FEEDBACK_EVALUATION_REPORT.json",
        {
            "stage": "N8J",
            "feedback_counts": {"observations": 6, "accepted": 4, "rejected": 2},
            "feedback_correction_stats": {
                "position_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                "velocity_mps": {"p50": 0.1, "p95": 0.2, "max": 0.3},
                "attitude_deg": {"p50": 1.0, "p95": 2.0, "max": 3.0},
                "yaw_abs_deg": {"p50": 0.5, "p95": 1.0, "max": 2.0},
            },
            "metric_namespaces": ["feedback_vs_baseline_delta", "reject_all_sanity_delta"],
            **boundary,
        },
    )
    write_json(root / "N8J_FINAL_FEEDBACK_MANIFEST.json", _toy_manifest())
    write_json(
        root / "N8J_FINAL_FEEDBACK_SANITY_REPORT.json",
        {
            "stage": "N8J",
            "all_checks_passed": True,
            "checks": {"selected_policy_fixed": True, "runtime_artifacts_not_committed": True, "no_paper_claim": True},
            "runtime_outputs_generated": True,
            **boundary,
        },
    )
    write_json(
        root / "N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json",
        {
            "stage": "N8J",
            "status": "feedback_joint_filter_ready_for_BY2_packaging",
            "recommended_next_stage": "N9_BY2_paper_experiment_packaging_or_BY3_replication",
            "fgo_feedback_output_substitution": False,
            "fgo_feedback_direct_nav_override": False,
            "output_substitution": False,
            "direct_nav_override": False,
            "fgo_feedback_no_future_data": True,
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            **boundary,
        },
    )
    for name in REQUIRED_N8J_FIGURES:
        (figure_root / name).write_bytes(b"\x89PNG\r\n\x1a\nN8J")
    write_json(
        root / "N8J_FIGURE_MANIFEST.json",
        {
            "stage": "N8J",
            "figure_count_total": len(REQUIRED_N8J_FIGURES),
            "required_figures": [{"filename": name, "present": True, "nonempty": True} for name in REQUIRED_N8J_FIGURES],
            "all_required_figures_present": True,
            "all_required_figures_nonempty": True,
            **boundary,
        },
    )


def _toy_selected_policy() -> dict[str, Any]:
    return {
        "stage": "N8J",
        "policy_name": "n8i_selected_conservative_feedback",
        "feedback_mode": "horizontal_velocity_attitude_feedback",
        "position_feedback_enabled": False,
        "horizontal_velocity_feedback_enabled": True,
        "attitude_feedback_enabled": True,
        "gate_policy": "combined_conservative_gate",
        "covariance_policy": "inflation_auto_from_residual_proxy",
        "window_duration_s": 5.0,
        "stride_s": 1.0,
        "no_future_data_required": True,
        "output_substitution": False,
        "direct_nav_override": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "n8i_selected_policy_match": True,
        "hidden_policy_change": False,
    }


def _toy_manifest() -> dict[str, Any]:
    return {
        "stage": "N8J",
        "selected_policy_name": "n8i_selected_conservative_feedback",
        "feedback_mode": "horizontal_velocity_attitude_feedback",
        "feedback_observations": 6,
        "accepted": 4,
        "rejected": 2,
        "position_feedback_enabled": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "no_future_data": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "runtime_outputs_generated": True,
        "runtime_artifacts_committed": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _toy_variants() -> list[dict[str, Any]]:
    return [
        {"policy_id": "baseline_no_feedback", "eval_nav_generated": True, "feedback_accept_count": 0, "feedback_reject_count": 0, "gross_degradation": False},
        {"policy_id": "n8j_selected_conservative_feedback", "eval_nav_generated": True, "nav_generated": True, "std_generated": True, "feedback_accept_count": 4, "feedback_reject_count": 2, "gross_degradation": False},
        {"policy_id": "reject_all_sanity", "eval_nav_generated": True, "feedback_accept_count": 0, "feedback_reject_count": 6, "gross_degradation": False, "baseline_delta": {"horizontal_m": {"max": 0.0}, "yaw_deg": {"max": 0.0}}},
    ]


def audit_toy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "n8j"
        make_toy_n8j_root(root)
        audit_runtime(root)


def main() -> int:
    root = report_root()
    if root is not None:
        audit_runtime(root)
    else:
        audit_toy()
    print("audit_n8j_feedback_final_validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
