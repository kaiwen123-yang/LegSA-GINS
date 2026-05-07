"""Dual-antenna heading mounting diagnostics for BY2.

中文说明：横向双天线只生成候选 heading offset，不根据 trace 做正式选择。
"""

from __future__ import annotations

from typing import Any


def wrap_deg360(angle: float) -> float:
    wrapped = angle % 360.0
    return wrapped + 360.0 if wrapped < 0.0 else wrapped


def apply_transverse_heading_offset(heading_deg: float, offset_deg: float) -> float:
    return wrap_deg360(heading_deg + offset_deg)


def candidate_heading_offsets() -> list[dict[str, Any]]:
    return [
        {"heading_offset_mode": "no_offset", "heading_offset_deg": 0.0},
        {"heading_offset_mode": "plus90", "heading_offset_deg": 90.0},
        {"heading_offset_mode": "minus90", "heading_offset_deg": -90.0},
    ]


def heading_offset_deg_for_mode(mode: str) -> float:
    for item in candidate_heading_offsets():
        if item["heading_offset_mode"] == mode:
            return float(item["heading_offset_deg"])
    raise ValueError(f"Unknown heading offset mode: {mode}")


def make_dual_antenna_heading_report(rows_by_candidate: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "mounting": "transverse_dual_antenna",
        "receiver_rel_pos_heading": "antenna_baseline_heading",
        "body_forward_heading_rule": "baseline_heading_plus_mounting_offset_candidate",
        "candidate_offsets": candidate_heading_offsets(),
        "candidate_summaries": rows_by_candidate,
        "heading_mounting_diagnostic_only": True,
        "trace_used_for_formal_selection": False,
        "selected_formal_offset": "evidence_missing_until_antenna_order_confirmed",
        "formal_heading_offset_selected": False,
        "evidence_status": "diagnostic_candidates_only",
    }

