#!/usr/bin/env python3
"""Audit N7C3 adaptive std keeps Go2 vertical/yaw/position disabled.

中文说明：本审计确认 Go2 垂向速度、航向和位置先验在 N7C3 中继续禁用。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_bounded_adaptive_std import (
    STD_VD_DISABLED,
    build_bounded_adaptive_go2_horizontal_velocity_priors,
)
from legsa_gins.go2_prior.go2_n7c3_decision import make_n7c3_decision


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_adaptive_std_vertical_disabled failed: {message}")


def main() -> int:
    source = [{"time": 0.0, "vn": 1.0, "ve": 0.0, "vd": 3.0}]
    confidence = [{"time": 0.0, "confidence": 0.9, "confidence_level": "high", "reason_codes": "toy"}]
    rows, report = build_bounded_adaptive_go2_horizontal_velocity_priors(source_prior_rows=source, confidence_rows=confidence)
    if rows[0]["vd"] != 0.0 or rows[0]["std_vd"] != STD_VD_DISABLED:
        _fail("vertical component not disabled in prior row")
    if not report.get("vertical_disabled"):
        _fail("vertical_disabled report flag false")
    decision = make_n7c3_decision(
        std_report=report,
        soft_gating_report={"update_count_expected": 1, "skip_count": 0},
        comparison_report={"bounded_adaptive_manifest": {}, "comparisons": {}},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    if decision.get("go2_vertical_velocity_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_position_prior_enabled"):
        _fail("forbidden Go2 prior enabled in decision")
    print("audit_go2_adaptive_std_vertical_disabled passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
