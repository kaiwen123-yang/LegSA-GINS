#!/usr/bin/env python3
"""Audit N8C no-feedback visual boundary.

中文说明：N8C 可视化不能反馈 EKF、替换 NAV 或使用 trace/final_v23 输入。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_n8c_decision import make_n8c_decision


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_no_feedback_visual_boundary failed: {message}")


def main() -> int:
    decision = make_n8c_decision(
        plot_coverage={"all_mandatory_figures_present": True, "all_mandatory_figures_nonempty": True},
        visual_sanity={"visual_sanity_passed": True, "yaw_delta_reasonable_after_n8a2": True},
        factor_contribution={"suspicious_no_effect_factors": [], "influential_factors": ["SmoothnessFactor"]},
        candidate_review={"candidate_factor_reviews": [{"status": "candidate_needs_data_review"}]},
    )
    for key in ["paper_performance_claim", "fgo_output_feedback_to_ekf", "output_substitution", "fgo_output_replaces_ekf_nav", "trace_solver_input", "final_v23_solver_input"]:
        if decision.get(key):
            _fail(f"boundary flag true: {key}")
    print("audit_fgo_no_feedback_visual_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
