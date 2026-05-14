"""N8C visual input loader for no-feedback FGO validation.

中文说明：如果 N8B runtime 没保存 time series，本模块只在内存中重跑
N8B 已登记 policy，生成可视化输入；不改 solver、不调权、不提交输出。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry
from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid
from legsa_gins.fgo.fgo_yaw_convention_audit import read_csv_rows, read_json_report


def _find_n8a_root(n8b_root: Path, n8a2_root: Path) -> Path | None:
    candidates = [
        n8b_root.parent / "N8A_no_feedback_fgo_foundation",
        n8a2_root.parent / "N8A_no_feedback_fgo_foundation",
    ]
    for candidate in candidates:
        if (candidate / "N8A_EKF_STATE_NODES.csv").exists():
            return candidate
    return None


def load_n8c_visual_inputs(
    *,
    n8b_root: str | Path,
    n8a2_root: str | Path,
    rerun_missing_timeseries: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    n8b = Path(n8b_root)
    n8a2 = Path(n8a2_root)
    reports = {
        "n8b_policy_grid": read_json_report(n8b / "N8B_FGO_POLICY_GRID.json"),
        "n8b_ablation_summary": read_json_report(n8b / "N8B_FGO_POLICY_ABLATION_SUMMARIES.json"),
        "n8b_comparison": read_json_report(n8b / "N8B_FGO_POLICY_COMPARISON_REPORT.json"),
        "n8b_smoothness_review": read_json_report(n8b / "FGO_SMOOTHNESS_POLICY_REVIEW_REPORT.json"),
        "n8b_factor_weight_review": read_json_report(n8b / "FGO_FACTOR_WEIGHT_REVIEW_REPORT.json"),
        "n8b_candidate_review": read_json_report(n8b / "FGO_CANDIDATE_FACTOR_REVIEW_REPORT.json"),
        "n8b_decision": read_json_report(n8b / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json"),
        "n8a2_decision": read_json_report(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json"),
        "n8a2_comparison": read_json_report(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json"),
        "factor_registry": build_default_factor_registry(),
    }
    n8a_root = _find_n8a_root(n8b, n8a2)
    ekf_rows = read_csv_rows(n8a_root / "N8A_EKF_STATE_NODES.csv") if n8a_root else []
    rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    rerun_performed = False
    ablation_summary = reports["n8b_ablation_summary"]
    if ekf_rows and rerun_missing_timeseries:
        grid = reports["n8b_policy_grid"] or build_n8b_policy_grid()
        ablation_summary, rows_by_variant = run_n8b_policy_ablations(ekf_rows=ekf_rows, policy_grid=grid)
        rerun_performed = True
    weak_found = any(row.get("variant") == "weak_yaw_smoothness" for row in ablation_summary.get("variants", []))
    default_found = any(row.get("variant") == "default_active_stack_n8a2" for row in ablation_summary.get("variants", []))
    candidate_review = reports["n8b_candidate_review"]
    manifest = {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        "n8b_reports_found": all(bool(reports[name]) for name in ["n8b_policy_grid", "n8b_ablation_summary", "n8b_factor_weight_review", "n8b_candidate_review"]),
        "n8a2_reports_found": bool(reports["n8a2_decision"] or reports["n8a2_comparison"]),
        "weak_yaw_variant_found": weak_found,
        "default_variant_found": default_found,
        "ekf_baseline_found": bool(ekf_rows),
        "factor_residuals_found": bool(reports["n8b_factor_weight_review"].get("per_factor_residual_p95")),
        "candidate_factors_diagnostic_only": bool(candidate_review.get("candidate_factors_remain_diagnostic", False)),
        "timeseries_rerun_performed_runtime_only": rerun_performed,
        "timeseries_source_role_alias": "N8A_REPORT_OUTPUT_DIR" if n8a_root else "missing",
        "n8b_role_alias": "N8B_REPORT_OUTPUT_DIR",
        "n8a2_role_alias": "N8A2_REPORT_OUTPUT_DIR",
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
    }
    data = {
        "reports": reports,
        "ekf_rows": ekf_rows,
        "rows_by_variant": rows_by_variant,
        "ablation_summary": ablation_summary,
    }
    return manifest, data


def write_visual_input_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
