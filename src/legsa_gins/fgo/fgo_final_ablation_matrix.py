"""N8E final engineering ablation matrix.

中文说明：N8E 只汇总工程消融证据，不把 FGO 输出反馈 EKF。

N8E summarizes engineering evidence from the EKF front end and no-feedback FGO
backend. It does not reroute FGO output into the EKF and does not use
trace/final_v23 outputs as solver input or weight-tuning evidence.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


N8E_GROUPS = {
    "A_EKF_front_end_modules": [
        "source_backed_ekf_baseline",
        "raw_doppler_ekf_factor",
        "source_aware_lsim_oim",
        "go2_horizontal_velocity_factor",
        "go2_proprioceptive_joint_factor",
    ],
    "B_no_feedback_FGO_modules": [
        "n8a2_default_no_feedback_fgo",
        "n8b_weak_yaw_smoothness_fgo",
        "n8d_conservative_policy",
        "n8d_raw_receiver_balanced_policy",
        "n8d_dual_yaw_x2_policy",
        "n8d_go2_joint_x2_policy",
        "n8d_best_balance_policy",
    ],
    "C_diagnostic_removals": [
        "no_raw_doppler",
        "no_go2_joint",
        "no_dual_yaw",
        "no_smoothness_diagnostic_only",
        "no_candidate_factors",
    ],
    "D_candidate_factors": [
        "foot_kinematic_diagnostic",
        "yaw_rate_between_diagnostic",
        "relative_odometry_diagnostic",
        "contact_weighting_diagnostic",
        "candidate_stack_diagnostic",
    ],
}

N8E_REQUIRED_VARIANTS = [variant for variants in N8E_GROUPS.values() for variant in variants]

CSV_FIELDS = [
    "group",
    "variant",
    "run_status",
    "source_of_result",
    "active_factors",
    "diagnostic_only",
    "no_feedback",
    "fgo_output_substitution",
    "metric_namespace",
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "fgo_vs_ekf_delta",
    "factor_contribution_notes",
    "caveat_notes",
]


def read_json_report(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_report(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _variants(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("variant")): row for row in report.get("variants", []) if row.get("variant")}


def _status(*reports: dict[str, Any], default: str = "available") -> str:
    for report in reports:
        value = report.get("status") or report.get("decision_status") or report.get("solve_status")
        if value:
            return str(value)
    return default


def _metric(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_bundle(row: dict[str, Any] | None) -> dict[str, float | None]:
    row = row or {}
    return {
        "horizontal_rmse_m": _metric(row, "horizontal_delta_rmse_m"),
        "up_rmse_m": _metric(row, "up_delta_rmse_m"),
        "yaw_rmse_deg": _metric(row, "yaw_delta_wrapped_rmse_deg"),
        "roll_rmse_deg": _metric(row, "roll_delta_rmse_deg"),
        "pitch_rmse_deg": _metric(row, "pitch_delta_rmse_deg"),
    }


def _delta_note(row: dict[str, Any] | None) -> str:
    metrics = _metric_bundle(row)
    pairs = [
        ("H", metrics["horizontal_rmse_m"]),
        ("Up", metrics["up_rmse_m"]),
        ("Yaw", metrics["yaw_rmse_deg"]),
        ("Roll", metrics["roll_rmse_deg"]),
        ("Pitch", metrics["pitch_rmse_deg"]),
    ]
    available = [f"{name}={value:.6g}" for name, value in pairs if value is not None]
    return "; ".join(available) if available else "metric not available in source report"


def _row(
    *,
    group: str,
    variant: str,
    run_status: str,
    source_of_result: str,
    active_factors: list[str],
    diagnostic_only: bool,
    no_feedback: bool,
    metric_namespace: str,
    factor_contribution_notes: str,
    caveat_notes: str,
    source_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = _metric_bundle(source_row)
    return {
        "group": group,
        "variant": variant,
        "run_status": run_status,
        "source_of_result": source_of_result,
        "active_factors": active_factors,
        "diagnostic_only": bool(diagnostic_only),
        "no_feedback": bool(no_feedback),
        "fgo_output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "fgo_output_feedback_to_ekf": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "metric_namespace": metric_namespace,
        **metrics,
        "fgo_vs_ekf_delta": _delta_note(source_row) if no_feedback else "not a no-feedback FGO row",
        "factor_contribution_notes": factor_contribution_notes,
        "caveat_notes": caveat_notes,
    }


def _best_row(variants: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return variants.get(name, {})


def build_final_engineering_ablation_matrix(stage_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the required 22-entry N8E matrix from prior stage reports."""

    n5b_decision = stage_reports.get("n5b_decision", {})
    n6b_decision = stage_reports.get("n6b_decision", {})
    n7c6_decision = stage_reports.get("n7c6_decision", {})
    n8a2_decision = stage_reports.get("n8a2_decision", {})
    n8b_decision = stage_reports.get("n8b_decision", {})
    n8c3_decision = stage_reports.get("n8c3_decision", {})
    n8d_decision = stage_reports.get("n8d_decision", {})
    n8d_formal = stage_reports.get("n8d_formal_matrix", {})
    n8d_variants = _variants(stage_reports.get("n8d_variant_summaries", {}))
    raw_receiver = stage_reports.get("n8d_raw_receiver", {})
    raw_receiver_rows = _variants(raw_receiver)
    go2_policy = stage_reports.get("n8d_go2_policy", {})
    go2_rows = _variants(go2_policy)
    dual_yaw = stage_reports.get("n8d_dual_yaw", {})
    dual_rows = _variants(dual_yaw)

    rows: list[dict[str, Any]] = []
    add = rows.append

    add(
        _row(
            group="A_EKF_front_end_modules",
            variant="source_backed_ekf_baseline",
            run_status="source_backed_baseline_available",
            source_of_result="source-backed EKF lineage / N8D ekf_baseline_no_fgo_reference",
            active_factors=["receiver_native_position_velocity_heading", "source_backed_ekf_backbone"],
            diagnostic_only=False,
            no_feedback=False,
            metric_namespace="ekf_frontend_engineering",
            factor_contribution_notes="baseline row for front-end module deltas",
            caveat_notes="baseline is engineering reference, not a paper performance claim",
            source_row=_best_row(n8d_variants, "ekf_baseline_no_fgo_reference"),
        )
    )
    add(
        _row(
            group="A_EKF_front_end_modules",
            variant="raw_doppler_ekf_factor",
            run_status=_status(n5b_decision, default="active_effective_frontend_factor"),
            source_of_result="N5B_RAW_DOPPLER_DECISION_REPORT",
            active_factors=["RawDoppler EKF auxiliary velocity factor"],
            diagnostic_only=False,
            no_feedback=False,
            metric_namespace="ekf_frontend_engineering",
            factor_contribution_notes="Raw Doppler is active as an EKF front-end auxiliary factor",
            caveat_notes="FGO low marginal value in N8D does not invalidate EKF Raw Doppler activation",
        )
    )
    add(
        _row(
            group="A_EKF_front_end_modules",
            variant="source_aware_lsim_oim",
            run_status=_status(n6b_decision, default="active_R_scaling_layer"),
            source_of_result="N6B_SOURCE_AWARE_DECISION_REPORT",
            active_factors=["source-aware LSIM/OIM R scaling"],
            diagnostic_only=False,
            no_feedback=False,
            metric_namespace="ekf_frontend_engineering",
            factor_contribution_notes="source-aware weighting acts as an R scaling layer",
            caveat_notes="stress evidence remains limited and should not be overstated",
        )
    )
    add(
        _row(
            group="A_EKF_front_end_modules",
            variant="go2_horizontal_velocity_factor",
            run_status="active_frontend_factor_from_N7C_lineage",
            source_of_result="N7C/N7C6 lineage",
            active_factors=["Go2 horizontal velocity observation factor"],
            diagnostic_only=False,
            no_feedback=False,
            metric_namespace="ekf_frontend_engineering",
            factor_contribution_notes="Go2 horizontal velocity contributes through proprioceptive observations",
            caveat_notes="Go2 velocity is not truth; vertical/yaw/position priors are not implied",
        )
    )
    add(
        _row(
            group="A_EKF_front_end_modules",
            variant="go2_proprioceptive_joint_factor",
            run_status=_status(n7c6_decision, default="active_ekf_factor"),
            source_of_result="N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT",
            active_factors=["Go2 roll/pitch", "Go2 horizontal velocity joint observation"],
            diagnostic_only=False,
            no_feedback=False,
            metric_namespace="ekf_frontend_engineering",
            factor_contribution_notes="joint factor is active with small but stable engineering deltas",
            caveat_notes="Go2 fields are proprioceptive observations, not truth",
        )
    )

    add(
        _row(
            group="B_no_feedback_FGO_modules",
            variant="n8a2_default_no_feedback_fgo",
            run_status=_status(n8a2_decision, default="no_feedback_fgo_available"),
            source_of_result="N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT",
            active_factors=["default no-feedback FGO smoother"],
            diagnostic_only=False,
            no_feedback=True,
            metric_namespace="fgo_vs_ekf_engineering_delta",
            factor_contribution_notes="default FGO foundation after yaw convention fix",
            caveat_notes="FGO output is not fed back and does not replace EKF NAV",
        )
    )
    add(
        _row(
            group="B_no_feedback_FGO_modules",
            variant="n8b_weak_yaw_smoothness_fgo",
            run_status=_status(_best_row(n8d_variants, "n8b_weak_yaw_default"), n8b_decision, default="solved"),
            source_of_result="N8B policy / N8D n8b_weak_yaw_default rerun",
            active_factors=["weak yaw smoothness", "receiver velocity", "Raw Doppler FGO", "Go2 joint", "dual yaw"],
            diagnostic_only=False,
            no_feedback=True,
            metric_namespace="fgo_vs_ekf_engineering_delta",
            factor_contribution_notes="N8B weak-yaw-smoothness policy is the default no-feedback FGO baseline",
            caveat_notes="smoothness remains active and is not deleted as a final shortcut",
            source_row=_best_row(n8d_variants, "n8b_weak_yaw_default"),
        )
    )
    for variant, source_name, active, source_row in [
        (
            "n8d_conservative_policy",
            "N8D conservative_policy",
            ["conservative smoothness", "Raw Doppler FGO", "receiver velocity", "Go2 joint", "dual yaw"],
            _best_row(n8d_variants, "conservative_policy"),
        ),
        (
            "n8d_raw_receiver_balanced_policy",
            "N8D receiver_vel_x0p5_raw_x1",
            ["Raw Doppler FGO", "receiver velocity balanced policy"],
            _best_row(raw_receiver_rows, str(raw_receiver.get("best_solver_visible_raw_receiver_balance"))),
        ),
        (
            "n8d_dual_yaw_x2_policy",
            "N8D dual_yaw_x2",
            ["dual yaw x2", "no-feedback FGO"],
            _best_row(dual_rows, str(dual_yaw.get("best_solver_visible_dual_yaw_policy"))),
        ),
        (
            "n8d_go2_joint_x2_policy",
            "N8D go2_joint_x2",
            ["Go2 joint x2", "no-feedback FGO"],
            _best_row(go2_rows, str(go2_policy.get("best_solver_visible_go2_joint_policy"))),
        ),
        (
            "n8d_best_balance_policy",
            "N8D best solver-visible balance",
            ["conservative policy", "balanced no-feedback FGO stack"],
            _best_row(n8d_variants, str(n8d_formal.get("best_solver_visible_balance_variant"))),
        ),
    ]:
        add(
            _row(
                group="B_no_feedback_FGO_modules",
                variant=variant,
                run_status=_status(source_row, n8d_decision, default="solved"),
                source_of_result=source_name,
                active_factors=active,
                diagnostic_only=False,
                no_feedback=True,
                metric_namespace="fgo_vs_ekf_engineering_delta",
                factor_contribution_notes="solver-visible no-feedback FGO policy contribution",
                caveat_notes="engineering delta only; no paper performance claim",
                source_row=source_row,
            )
        )

    for variant, source_variant, factors, note in [
        ("no_raw_doppler", "no_raw_doppler_diagnostic", ["Raw Doppler FGO removed"], "removal diagnostic; not an activation failure"),
        ("no_go2_joint", "no_go2_joint_diagnostic", ["Go2 joint removed"], "removal diagnostic; Go2 joint remains active in default stack"),
        ("no_dual_yaw", "no_dual_yaw_diagnostic", ["dual yaw removed"], "removal diagnostic only"),
        ("no_smoothness_diagnostic_only", "no_smoothness_diagnostic", ["smoothness removed"], "diagnostic-only row; not a final shortcut"),
        ("no_candidate_factors", "n8b_weak_yaw_default", ["candidate factors excluded"], "candidate factors remain diagnostic unless promoted later"),
    ]:
        add(
            _row(
                group="C_diagnostic_removals",
                variant=variant,
                run_status=_status(_best_row(n8d_variants, source_variant), default="diagnostic_rerun_available"),
                source_of_result=f"N8D {source_variant}",
                active_factors=factors,
                diagnostic_only=True,
                no_feedback=True,
                metric_namespace="fgo_vs_ekf_diagnostic_delta",
                factor_contribution_notes="diagnostic removal row",
                caveat_notes=note,
                source_row=_best_row(n8d_variants, source_variant),
            )
        )

    candidate_stack = _best_row(n8d_variants, "candidate_stack_diagnostic")
    for variant, factor, note, source_row in [
        (
            "foot_kinematic_diagnostic",
            "Go2 foot kinematic velocity candidate",
            "high slip risk; needs FGO-specific review before promotion",
            {},
        ),
        (
            "yaw_rate_between_diagnostic",
            "Go2 yaw-rate between-state candidate",
            "diagnostic only and not a formal factor",
            {},
        ),
        (
            "relative_odometry_diagnostic",
            "relative odometry candidate",
            "diagnostic only and not a formal factor",
            {},
        ),
        (
            "contact_weighting_diagnostic",
            "contact probability weighting candidate",
            "contact probability is weighting evidence, not a direct factor",
            {},
        ),
        (
            "candidate_stack_diagnostic",
            "candidate stack diagnostic",
            "candidate stack remains diagnostic-only",
            candidate_stack,
        ),
    ]:
        add(
            _row(
                group="D_candidate_factors",
                variant=variant,
                run_status=_status(source_row, default="diagnostic_candidate_reviewed"),
                source_of_result="N7C5/N8B/N8D candidate diagnostics",
                active_factors=[factor],
                diagnostic_only=True,
                no_feedback=True,
                metric_namespace="candidate_factor_diagnostic",
                factor_contribution_notes="candidate evidence is recorded but not promoted to a formal factor",
                caveat_notes=note,
                source_row=source_row,
            )
        )

    present = [str(row["variant"]) for row in rows]
    missing = [name for name in N8E_REQUIRED_VARIANTS if name not in present]
    group_counts = {group: sum(1 for row in rows if row["group"] == group) for group in N8E_GROUPS}
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "matrix_rows": rows,
        "row_count": len(rows),
        "required_variants": N8E_REQUIRED_VARIANTS,
        "missing_required_variants": missing,
        "group_counts": group_counts,
        "expected_group_counts": {group: len(variants) for group, variants in N8E_GROUPS.items()},
        "matrix_complete": not missing and len(rows) == len(N8E_REQUIRED_VARIANTS),
        "all_rows_no_feedback_or_frontend": all(row["no_feedback"] or row["group"].startswith("A_") for row in rows),
        "no_fgo_feedback": all(not row["fgo_output_feedback_to_ekf"] for row in rows),
        "no_fgo_output_substitution": all(not row["fgo_output_substitution"] for row in rows),
        "no_trace_finalv23_solver_input_or_tuning": all(
            not row["trace_solver_input"]
            and not row["trace_weight_tuning"]
            and not row["final_v23_output_solver_input"]
            and not row["final_v23_weight_tuning"]
            for row in rows
        ),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "raw_doppler_fgo_active_but_low_marginal_value": bool(
            raw_receiver.get("raw_doppler_remains_low_marginal_value")
            or n8d_decision.get("raw_doppler_remains_low_marginal_value")
        ),
        "raw_doppler_low_marginal_value_is_not_failure": True,
        "best_balance_policy": n8d_formal.get("best_solver_visible_balance_variant"),
        "best_raw_receiver_policy": raw_receiver.get("best_solver_visible_raw_receiver_balance"),
        "best_go2_joint_policy": go2_policy.get("best_solver_visible_go2_joint_policy"),
        "best_dual_yaw_policy": dual_yaw.get("best_solver_visible_dual_yaw_policy"),
        "runtime_only_outputs": [
            "N8E_FINAL_ENGINEERING_ABLATION_MATRIX.json",
            "N8E_FINAL_ENGINEERING_ABLATION_TABLE.csv",
            "N8E_FINAL_ENGINEERING_ABLATION_SUMMARY.md",
        ],
    }


def write_ablation_table_csv(path: str | Path, report: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in report.get("matrix_rows", []):
            flat = dict(row)
            flat["active_factors"] = "; ".join(row.get("active_factors", []))
            writer.writerow({field: flat.get(field) for field in CSV_FIELDS})


def write_ablation_summary_md(path: str | Path, report: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# N8E Final Engineering Ablation Matrix",
        "",
        "Runtime role aliases:",
        "",
        "- N5B_REPORT_OUTPUT_DIR",
        "- N6B_REPORT_OUTPUT_DIR",
        "- N7C6_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8C3_REPORT_OUTPUT_DIR",
        "- N8D_REPORT_OUTPUT_DIR",
        "- N8E_REPORT_OUTPUT_DIR",
        "",
        f"- row_count: {report.get('row_count')}",
        f"- matrix_complete: {report.get('matrix_complete')}",
        f"- group_counts: {report.get('group_counts')}",
        f"- best_balance_policy: {report.get('best_balance_policy')}",
        f"- raw_doppler_fgo_active_but_low_marginal_value: {report.get('raw_doppler_fgo_active_but_low_marginal_value')}",
        "",
        "Boundaries:",
        "",
        "- FGO output is not fed back into EKF.",
        "- FGO output does not replace EKF NAV.",
        "- Trace/final_v23 outputs are not solver input and are not used for tuning.",
        "- Raw Doppler FGO low marginal value is recorded as a caveat, not a failure.",
        "- Candidate factors remain diagnostic-only unless a later stage promotes them.",
        "- No paper performance claim and no outperform final_v23 claim.",
        "",
        "| group | variant | status | diagnostic | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.get("matrix_rows", []):
        lines.append(
            f"| {row.get('group')} | {row.get('variant')} | {row.get('run_status')} | "
            f"{row.get('diagnostic_only')} | {row.get('caveat_notes')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
