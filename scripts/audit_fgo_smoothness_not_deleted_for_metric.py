#!/usr/bin/env python3
"""Audit N8B keeps smoothness deletion diagnostic-only.

中文说明：删除 smoothness 只能是诊断项，不能作为最终过关捷径。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_n8b_decision import make_n8b_decision
from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid
from legsa_gins.fgo.fgo_smoothness_policy_review import review_smoothness_policy


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_smoothness_not_deleted_for_metric failed: {message}")


def _toy_rows() -> list[dict]:
    rows = []
    for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0]):
        rows.append({"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0})
    return rows


def main() -> int:
    ablations, _rows = run_n8b_policy_ablations(ekf_rows=_toy_rows(), policy_grid=build_n8b_policy_grid())
    variants = {row["variant"]: row for row in ablations["variants"]}
    for name in ["default_active_stack_n8a2", "weak_yaw_smoothness", "position_velocity_only_smoothness"]:
        if variants[name].get("smoothness_factor_deleted_for_metric"):
            _fail(f"{name} deletes smoothness")
    for name in ["no_yaw_smoothness_diagnostic", "no_smoothness_diagnostic"]:
        if not variants[name].get("diagnostic_only"):
            _fail(f"{name} is not diagnostic-only")
    smoothness = review_smoothness_policy(ablations)
    decision = make_n8b_decision(ablation_summary=ablations, smoothness_review=smoothness, factor_weight_review={"suspect_factors": []}, candidate_review={"candidate_factor_reviews": []})
    if decision.get("smoothness_deletion_final_shortcut") or decision.get("smoothness_factor_deleted_for_metric"):
        _fail("decision uses smoothness deletion as shortcut")
    print("audit_fgo_smoothness_not_deleted_for_metric passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
