"""N8A1 diagnostic-only factor ablation review.

中文说明：本模块只做诊断性消融代理，不选择最终权重。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_factor_policy_review import N8A1_RECOMMENDED_ABLATIONS
from legsa_gins.fgo.fgo_yaw_convention_audit import as_float, rmse, yaw_delta_deg, yaw_series


STATE_COLUMNS = ["lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]


def _copy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _blend_rows(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]], *, alpha: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        row = dict(fgo)
        for column in STATE_COLUMNS:
            if column == "yaw_deg":
                row[column] = as_float(ekf.get(column)) + alpha * yaw_delta_deg(as_float(fgo.get(column)), as_float(ekf.get(column)))
            else:
                row[column] = as_float(ekf.get(column)) + alpha * (as_float(fgo.get(column)) - as_float(ekf.get(column)))
        rows.append(row)
    return rows


def _copy_columns_from_ekf(rows: list[dict[str, Any]], ekf_rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    out = _copy_rows(rows)
    for row, ekf in zip(out, ekf_rows):
        for column in columns:
            if column in ekf:
                row[column] = ekf[column]
    return out


def _horizontal_rmse_m(ekf_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for ekf, candidate in zip(ekf_rows, candidate_rows):
        lat0 = math.radians(as_float(ekf.get("lat_deg")))
        north = (as_float(candidate.get("lat_deg")) - as_float(ekf.get("lat_deg"))) * 111_320.0
        east = (as_float(candidate.get("lon_deg")) - as_float(ekf.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
        values.append(math.sqrt(north * north + east * east))
    return rmse(values)


def _yaw_rmse_deg(ekf_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> float:
    ekf_yaw = yaw_series(ekf_rows)
    candidate_yaw = yaw_series(candidate_rows)
    return rmse([yaw_delta_deg(candidate, ekf) for ekf, candidate in zip(ekf_yaw, candidate_yaw)])


def _finite_rows(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        for column in STATE_COLUMNS:
            value = as_float(row.get(column))
            if not math.isfinite(value) or abs(value) > 1e12:
                return False
    return True


def _variant_rows(name: str, ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if name == "default_active_stack":
        return _copy_rows(fgo_rows), "N8A default no-feedback diagnostic output."
    if name == "no_smoothness":
        return _copy_rows(ekf_rows), "Diagnostic proxy removes offline smoothing; no EKF feedback or output substitution."
    if name == "weak_smoothness":
        return _blend_rows(ekf_rows, fgo_rows, alpha=0.25), "Diagnostic proxy weakens offline smoothing using solver-visible EKF state nodes only."
    if name == "dual_yaw_stronger_diagnostic":
        return _blend_rows(ekf_rows, fgo_rows, alpha=0.10), "Diagnostic proxy anchors yaw residual more strongly; not a selected final weight."
    if name == "no_go2_joint":
        return _copy_columns_from_ekf(fgo_rows, ekf_rows, ["roll_deg", "pitch_deg", "vn_mps", "ve_mps"]), "Proxy disables Go2 joint-touched state deltas."
    if name == "no_raw_doppler":
        return _copy_columns_from_ekf(fgo_rows, ekf_rows, ["vn_mps", "ve_mps", "vd_mps"]), "Proxy disables velocity delta from raw-Doppler-touched block."
    if name == "no_go2_horizontal_component":
        return _copy_columns_from_ekf(fgo_rows, ekf_rows, ["vn_mps", "ve_mps"]), "Proxy disables horizontal component from Go2 joint block."
    if name == "no_go2_rollpitch_component":
        return _copy_columns_from_ekf(fgo_rows, ekf_rows, ["roll_deg", "pitch_deg"]), "Proxy disables roll/pitch component from Go2 joint block."
    if name == "active_stack_no_diagnostic_candidates":
        return _copy_rows(fgo_rows), "Same as default if diagnostic candidates did not leak."
    if name == "diagnostic_candidate_stack_if_available":
        return _copy_rows(fgo_rows), "No separate diagnostic-candidate runtime output available in N8A; retained for policy review."
    if name == "no_dual_yaw":
        return _copy_rows(fgo_rows), "No separate no-dual-yaw runtime output available in N8A; retained as default proxy."
    return _copy_rows(fgo_rows), "Unknown variant retained as default proxy."


def run_factor_ablation_review(
    *,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    variants: list[str] | None = None,
) -> dict[str, Any]:
    names = variants or list(N8A1_RECOMMENDED_ABLATIONS)
    count = min(len(ekf_rows), len(fgo_rows))
    ekf = ekf_rows[:count]
    fgo = fgo_rows[:count]
    default_yaw_rmse = _yaw_rmse_deg(ekf, fgo) if count else 0.0
    results: list[dict[str, Any]] = []
    for name in names:
        rows, note = _variant_rows(name, ekf, fgo)
        yaw_rmse = _yaw_rmse_deg(ekf, rows)
        horizontal_rmse = _horizontal_rmse_m(ekf, rows)
        finite = _finite_rows(rows)
        solve_status = "diagnostic_proxy_solved" if finite and count else "missing_input"
        gross_degradation = bool(default_yaw_rmse > 0.0 and yaw_rmse > 1.5 * default_yaw_rmse)
        results.append(
            {
                "variant": name,
                "ablation_mode": "diagnostic_proxy_from_n8a_runtime_outputs",
                "yaw_delta_rmse_deg": yaw_rmse,
                "horizontal_delta_rmse_m": horizontal_rmse,
                "solve_status": solve_status,
                "finite_output": finite,
                "gross_degradation": gross_degradation,
                "notes": note,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "fgo_output_feedback_to_ekf": False,
                "fgo_output_replaces_ekf_nav": False,
            }
        )
    best = min(results, key=lambda row: as_float(row.get("yaw_delta_rmse_deg")), default={})
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "source_role_alias": "N8A_REPORT_OUTPUT_DIR",
        "ablation_mode": "diagnostic_proxy_from_n8a_runtime_outputs",
        "separate_variant_runtime_outputs_available": False,
        "real_solver_rerun": False,
        "diagnostic_proxy_note": "Variants are bounded runtime-output probes used to localize yaw-delta sources; they are not final weight selection.",
        "variant_count": len(results),
        "variants": results,
        "best_yaw_delta_variant": best.get("variant"),
        "best_yaw_delta_rmse_deg": best.get("yaw_delta_rmse_deg", 0.0),
        "diagnostic_only": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "uses_trace_for_weight_selection": False,
        "uses_final_v23_for_weight_selection": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
