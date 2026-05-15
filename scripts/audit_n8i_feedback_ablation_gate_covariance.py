#!/usr/bin/env python3
"""Audit N8I feedback ablation gate/covariance reports.

中文说明：若没有真实 runtime 路径，则生成 toy 报告审计合同；不读取 trace/final_v23
作为调参输入。
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

from legsa_gins.fgo_feedback.fgo_feedback_n8i_visual_plots import REQUIRED_N8I_FIGURES
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


REQUIRED_REPORTS = [
    "N8I_FEEDBACK_POLICY_GRID.json",
    "FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json",
    "FGO_FEEDBACK_COVARIANCE_REFINEMENT_REPORT.json",
    "FGO_FEEDBACK_WINDOW_POLICY_REVIEW_REPORT.json",
    "N8I_FEEDBACK_MODE_ABLATION_SUMMARIES.json",
    "N8I_FEEDBACK_MODE_COMPARISON_REPORT.json",
    "FGO_FEEDBACK_ATTITUDE_SPIKE_REVIEW_REPORT.json",
    "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json",
    "N8I_FIGURE_MANIFEST.json",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8i_feedback_ablation_gate_covariance failed: {message}")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_root() -> Path | None:
    value = os.environ.get("N8I_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            _fail(f"missing report {name}")
    decision = _json(root / "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json")
    figure_manifest = _json(root / "N8I_FIGURE_MANIFEST.json")
    grid = _json(root / "N8I_FEEDBACK_POLICY_GRID.json")
    if decision.get("status") not in {
        "feedback_policy_not_ready",
        "default_feedback_policy_ready",
        "conservative_feedback_gate_ready",
        "refined_covariance_policy_ready",
        "velocity_feedback_only_recommended",
    }:
        _fail(f"unexpected decision status {decision.get('status')}")
    if decision.get("fgo_feedback_output_substitution") is not False or decision.get("fgo_feedback_direct_nav_override") is not False:
        _fail("decision allows output substitution or direct NAV overwrite")
    if decision.get("trace_solver_input") is not False or decision.get("final_v23_output_solver_input") is not False:
        _fail("decision allows trace/final_v23 solver input")
    if decision.get("paper_performance_claim") is not False:
        _fail("decision allows paper claim")
    if figure_manifest.get("figure_count_total") != len(REQUIRED_N8I_FIGURES):
        _fail("wrong N8I figure count")
    if figure_manifest.get("all_required_figures_nonempty") is not True:
        _fail("required N8I figures are not nonempty")
    if grid.get("trace_solver_input") is not False or grid.get("final_v23_output_solver_input") is not False:
        _fail("policy grid records forbidden solver input")


def make_toy_n8i_root(root: Path, figure_root: Path | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    figure_root = figure_root or root / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    boundary = {
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    write_json(
        root / "N8I_FEEDBACK_POLICY_GRID.json",
        {
            "stage": "N8I",
            "runtime_curated_policy_count": 9,
            "dimensions": {"feedback_mode": ["horizontal_velocity_attitude_primary"], "gate_policy": ["default_gate"]},
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        },
    )
    write_json(
        root / "FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json",
        {
            "stage": "N8I",
            "classification": "conservative_gate_recommended",
            "selected_gate_policy": "combined_conservative_gate",
            "gate_sweep": [
                {"policy_id": "gate_default_primary", "feedback_count": 6, "pre_runtime_accept_count": 6, "pre_runtime_reject_count": 0},
                {"policy_id": "gate_combined_conservative", "feedback_count": 6, "pre_runtime_accept_count": 4, "pre_runtime_reject_count": 2},
            ],
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            **boundary,
        },
    )
    write_json(
        root / "FGO_FEEDBACK_COVARIANCE_REFINEMENT_REPORT.json",
        {
            "stage": "N8I",
            "selected_covariance_policy": "block_velocity_x2_attitude_x4",
            "covariance_sweep": [{"policy_id": "cov_velocity_x2_attitude_x4", "no_R_shrink": True, "gross_degradation": False}],
            "no_R_shrink_claim": True,
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            **boundary,
        },
    )
    write_json(
        root / "FGO_FEEDBACK_WINDOW_POLICY_REVIEW_REPORT.json",
        {
            "stage": "N8I",
            "selected_window_policy": "window_5s_stride_1s",
            "selected_window_duration_s": 5.0,
            "selected_feedback_stride_s": 1.0,
            "window_policy_sweep": [{"policy_id": "window_5s_stride_1s", "no_future_data": True, "solve_success": True}],
            "no_future_data_feedback": True,
            **boundary,
        },
    )
    variants = _toy_variants()
    write_json(
        root / "N8I_FEEDBACK_MODE_ABLATION_SUMMARIES.json",
        {
            "stage": "N8I",
            "variant_count": len(variants),
            "variants": variants,
            "reject_all_sanity_passed": True,
            "gross_degradation_present": False,
            **boundary,
        },
    )
    write_json(
        root / "N8I_FEEDBACK_MODE_COMPARISON_REPORT.json",
        {"stage": "N8I", "gross_degradation_status": "absent", "variant_results": [], **boundary},
    )
    write_json(
        root / "FGO_FEEDBACK_ATTITUDE_SPIKE_REVIEW_REPORT.json",
        {
            "stage": "N8I",
            "default_attitude_spike_count": 2,
            "conservative_gate_reject_count_for_attitude_or_yaw": 2,
            "would_conservative_gate_reject_spikes": True,
            "spike_pattern": "isolated",
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            **boundary,
        },
    )
    for name in REQUIRED_N8I_FIGURES:
        (figure_root / name).write_bytes(b"\x89PNG\r\n\x1a\nN8I")
    write_json(
        root / "N8I_FIGURE_MANIFEST.json",
        {
            "stage": "N8I",
            "figure_count_total": len(REQUIRED_N8I_FIGURES),
            "required_figures": [
                {"filename": name, "path_role": "n8i_figure_output_dir", "present": True, "nonempty": True}
                for name in REQUIRED_N8I_FIGURES
            ],
            "all_required_figures_present": True,
            "all_required_figures_nonempty": True,
            **boundary,
        },
    )
    write_json(
        root / "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json",
        {
            "stage": "N8I",
            "status": "conservative_feedback_gate_ready",
            "recommended_next_stage": "N8J_feedback_final_validation",
            "selected_feedback_policy": "primary_hv_att_conservative_gate",
            "selected_gate_policy": "combined_conservative_gate",
            "selected_covariance_policy": "block_velocity_x2_attitude_x4",
            "selected_window_policy": "window_5s_stride_1s",
            "fgo_feedback_output_substitution": False,
            "fgo_feedback_direct_nav_override": False,
            "output_substitution": False,
            "direct_nav_override": False,
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            "fgo_feedback_no_future_data": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        },
    )


def _toy_variants() -> list[dict[str, Any]]:
    ids = [
        "baseline_no_feedback",
        "primary_horizontal_velocity_attitude_default",
        "primary_hv_att_conservative_gate",
        "diagnostic_PVA",
        "velocity_only",
        "attitude_only",
        "reject_all_sanity",
    ]
    variants = []
    for policy_id in ids:
        reject = policy_id == "reject_all_sanity"
        baseline = policy_id == "baseline_no_feedback"
        variants.append(
            {
                "policy_id": policy_id,
                "feedback_accept_count": 0 if baseline or reject else 6,
                "feedback_reject_count": 0 if not policy_id.endswith("conservative_gate") else 2,
                "feedback_update_count": 0 if baseline or reject else 6,
                "attitude_spike_count_over_4deg": 0 if "conservative" in policy_id or "velocity_only" in policy_id else 2,
                "baseline_delta": {
                    "horizontal_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                    "yaw_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                    "roll_pitch_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                },
                "gross_degradation": False,
                "no_output_substitution": True,
                "no_direct_nav_override": True,
            }
        )
    return variants


def audit_toy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "n8i"
        make_toy_n8i_root(root)
        audit_runtime(root)


def main() -> int:
    root = report_root()
    if root is not None:
        audit_runtime(root)
    else:
        audit_toy()
    print("audit_n8i_feedback_ablation_gate_covariance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
