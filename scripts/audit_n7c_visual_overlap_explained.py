#!/usr/bin/env python3
"""Audit N7C2 visual overlap explanation logic.

中文说明：该审计确认曲线高度重合会被解释为小效应，而不是绘图失败。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c_visual_overlap_audit import build_n7c2_visual_overlap_audit


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c_visual_overlap_explained failed: {message}")


def _rows(offset: float, count: int = 300) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(count):
        rows.append(
            {
                "time": f"{index * 0.25:.6f}",
                "lat_deg": f"{39.0 + index * 1.0e-9 + offset:.12f}",
                "lon_deg": f"{116.0 + index * 1.0e-9 + offset:.12f}",
                "height_m": f"{40.0 + offset:.12f}",
                "vn": "1.0",
                "ve": "0.2",
                "vd": "0.0",
                "roll_deg": f"{offset:.12f}",
                "pitch_deg": f"{offset:.12f}",
                "yaw_deg": f"{1.0 + offset:.12f}",
            }
        )
    return rows


def main() -> int:
    source_data = {
        "baseline_eval_nav": _rows(0.0),
        "main_eval_nav": _rows(1.0e-12),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    report = build_n7c2_visual_overlap_audit(source_data)
    items = report.get("overlap_items", [])
    if len(items) < 5:
        _fail("expected at least five overlap items")
    statuses = {item.get("visible_difference_status") for item in items}
    if not ({"mostly_overlapped", "identical_or_near_identical"} & statuses):
        _fail("synthetic near-identical curves did not classify as overlapped")
    for item in items:
        if item.get("visible_difference_status") in {"mostly_overlapped", "identical_or_near_identical"}:
            reasons = set(item.get("reason_codes", []))
            if "overlap_due_to_small_effect" not in reasons:
                _fail(f"missing overlap_due_to_small_effect for {item.get('figure_name')}")
            if item.get("overlap_is_failure"):
                _fail("overlap incorrectly marked as failure")
    if not report.get("summary", {}).get("delta_zoom_required"):
        _fail("delta zoom not required")
    if report.get("paper_performance_claim") or report.get("go2_velocity_truth_claim"):
        _fail("forbidden claim flag true")
    if report.get("trace_solver_input") or report.get("final_v23_output_solver_input"):
        _fail("forbidden solver input flag true")
    print("audit_n7c_visual_overlap_explained passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
