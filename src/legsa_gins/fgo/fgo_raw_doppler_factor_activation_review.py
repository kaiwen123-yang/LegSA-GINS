"""N8C2 RawDopplerVelocityFactor activation review.

中文说明：Raw Doppler 审查区分直接 solver 残差证据和代理残差证据。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import write_json_report


def _row(report: dict[str, Any], factor: str) -> dict[str, Any]:
    return next((row for row in report.get("factor_activation_rows", []) if row.get("factor_type") == factor), {})


def _scan_raw_doppler_sources(root: str | Path | None) -> dict[str, Any]:
    if not root:
        return {"raw_doppler_source_found": False, "evidence_files": []}
    path = Path(root)
    if not path.exists():
        return {"raw_doppler_source_found": False, "evidence_files": []}
    evidence = []
    counters: dict[str, Any] = {}
    for candidate in list(path.rglob("*.json"))[:80]:
        lower = candidate.name.lower()
        if "doppler" not in lower and "n5b" not in lower:
            continue
        evidence.append(candidate.name)
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ["raw_doppler_update_count", "raw_doppler_factor_count", "epoch_alignment_count", "aligned_epoch_count"]:
            if key in payload:
                counters[key] = payload[key]
    return {
        "raw_doppler_source_found": bool(evidence),
        "evidence_files": sorted(set(evidence))[:20],
        **counters,
    }


def build_raw_doppler_factor_activation_review(
    *,
    activation_report: dict[str, Any],
    whitening_report: dict[str, Any],
    toggle_integrity_report: dict[str, Any] | None = None,
    n5b_root: str | Path | None = None,
) -> dict[str, Any]:
    raw = _row(activation_report, "RawDopplerVelocityFactor")
    receiver = _row(activation_report, "ReceiverVelocityFactor")
    smooth = _row(activation_report, "SmoothnessFactor")
    toggle_rows = (toggle_integrity_report or {}).get("toggle_rows", [])
    raw_toggle = next((row for row in toggle_rows if row.get("variant") == "raw_doppler_off"), {})
    source = _scan_raw_doppler_sources(n5b_root)
    raw_share = float(raw.get("contribution_share", 0.0) or 0.0)
    receiver_share = float(receiver.get("contribution_share", 0.0) or 0.0)
    smooth_share = float(smooth.get("contribution_share", 0.0) or 0.0)
    if not raw.get("included_in_solver_residual"):
        classification = "activation_missing"
    elif raw_toggle and raw_toggle.get("status") != "toggle_passed":
        classification = "toggle_bug"
    elif raw_share < 0.03 and (receiver_share > raw_share * 3.0 or smooth_share > raw_share * 3.0):
        classification = "dominated_by_receiver_velocity_smoothness"
    elif raw_share < 0.03:
        classification = "weight_too_weak"
    elif abs(float(raw.get("on_off_delta_combined_abs", 0.0) or 0.0)) <= 0.05:
        classification = "consistent_no_large_delta"
    else:
        classification = "review_logic_false_positive"
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "factor_type": "RawDopplerVelocityFactor",
        "raw_doppler_source_found": source.get("raw_doppler_source_found"),
        "source_evidence_files": source.get("evidence_files", []),
        "epoch_alignment_count": source.get("epoch_alignment_count", source.get("aligned_epoch_count", 0)),
        "raw_doppler_factor_count": raw.get("factor_count", 0),
        "residual_dimension_expected": raw.get("residual_dimension", 3),
        "state_blocks_touched": raw.get("touched_state_blocks", []),
        "r_std_stats": raw.get("r_covariance_stats", {}),
        "residual_raw_p50_p95_max": raw.get("raw_residual_stats", {}),
        "residual_whitened_p50_p95_max": raw.get("whitened_residual_stats", {}),
        "jacobian_nonzero": raw.get("jacobian_nonzero_count", 0),
        "factor_weight_not_zero": bool(raw.get("r_covariance_stats", {}).get("std_p50", 0.0)),
        "appears_in_solver_residual_vector": bool(raw.get("included_in_solver_residual")),
        "raw_doppler_off_variant_removes_it": bool(raw_toggle.get("factor_count_changes", False)),
        "raw_doppler_weight_scale_variants_possible": True,
        "classification": classification,
        "whitening_classification": whitening_report.get("raw_doppler_whitening_classification"),
        "direct_solver_residual_evidence": raw.get("direct_solver_residual_evidence", False),
        "proxy_residual_evidence": raw.get("proxy_residual_evidence", False),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
