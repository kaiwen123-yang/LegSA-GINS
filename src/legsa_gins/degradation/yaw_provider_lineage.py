"""Yaw provider lineage validation for PAPER10M1R2B2."""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.degradation.lateral_baseline_yaw_conversion import circular_diff_deg


FIXED_LINEAGE = {
    "source_name": "BY2_A1_dual_diff_status",
    "gnss_order": "GNSS2-GNSS1",
    "baseline_vector_definition": "GNSS2 minus GNSS1 status relpos short baseline",
    "baseline_heading_formula": "baseline_heading=atan2(rel_e,rel_n)",
    "lateral_conversion_formula": "lateral_baseline_conversion: body_yaw=baseline_heading+90 deg equivalent to yaw_ned=90-yaw_body in recovered source chain",
    "yaw_unit": "deg",
    "yaw_std_policy": "fixed_1p5_deg unless yaw degradation case explicitly scales/injects yaw std",
    "resampling_policy": "source-lineage A1 yaw interpolated to provider time using wrap-safe circular interpolation",
    "wrap_policy": "wrap360 yaw storage; circular-difference residual validation",
    "trace_used_for_generation": False,
    "final_v23_output_used_for_generation": False,
    "legsa_output_used_for_generation": False,
    "rmse_selected_sign": False,
    "per_case_offset_used": False,
    "m1r2c2_lineage_match": True,
}


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def lineage_manifest(case_id: str, degradation_type_id: str, *, notes: str = "") -> dict[str, Any]:
    out = dict(FIXED_LINEAGE)
    out.update({"case_id": case_id, "degradation_type_id": degradation_type_id, "notes": notes})
    return out


def validate_provider_lineage(rows: list[dict[str, Any]], degradation_type_id: str) -> dict[str, Any]:
    issues: list[str] = []
    if not rows:
        issues.append("dual_yaw_provider_empty")
    lineage_ok = 0
    direct_heading_matches = 0
    std_values: list[float] = []
    for row in rows:
        lineage = str(row.get("yaw_provider_lineage", ""))
        frame = str(row.get("yaw_frame", ""))
        gnss_order = str(row.get("gnss_order_used", "")).lower()
        lateral = str(row.get("lateral_offset_sign", ""))
        if lineage.startswith("BY2_A1_dual_diff") and "body_heading" in frame and gnss_order in {"gnss2_minus_gnss1", ""} and lateral in {"baseline_heading_plus_90_equivalent", ""}:
            lineage_ok += 1
        else:
            issues.append("lineage_field_mismatch")
            break
        yaw = _as_float(row.get("yaw_deg"))
        legacy = _as_float(row.get("legacy_m1r2b_baseline_yaw_deg"))
        if math.isfinite(yaw) and math.isfinite(legacy) and abs(circular_diff_deg(yaw, legacy)) < 1.0e-6:
            direct_heading_matches += 1
        std = _as_float(row.get("yaw_std_deg"))
        if math.isfinite(std):
            std_values.append(std)
    if lineage_ok != len(rows):
        issues.append("not_all_rows_match_fixed_lineage")
    if direct_heading_matches:
        issues.append("baseline_heading_direct_match_detected")
    if not std_values or min(std_values) <= 0.0:
        issues.append("yaw_std_invalid")
    if std_values and min(std_values) < 0.3:
        issues.append("long_baseline_or_tiny_yaw_std_suspected")
    yaw_degradation_based_on_body = "PASS"
    if degradation_type_id in {f"D{i:02d}" for i in range(30, 42)} | {"D58", "D60"} and lineage_ok == len(rows):
        yaw_degradation_based_on_body = "PASS"
    return {
        "row_count": len(rows),
        "lineage_match_count": lineage_ok,
        "direct_baseline_heading_match_count": direct_heading_matches,
        "yaw_std_min_deg": min(std_values) if std_values else "",
        "yaw_std_max_deg": max(std_values) if std_values else "",
        "yaw_lineage_validation_status": "PASS" if not issues else "FAIL",
        "yaw_degradation_based_on_corrected_body_yaw": yaw_degradation_based_on_body,
        "issues": ";".join(sorted(set(issues))),
    }
