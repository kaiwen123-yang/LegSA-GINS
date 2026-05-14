#!/usr/bin/env python3
"""Audit N8C factor contribution review logic.

中文说明：确认 active factor、diagnostic candidate 和 suspicious_no_effect
分类可被报告，不把候选 factor 正式化。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_contribution_review import review_factor_contributions


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_factor_contribution_review failed: {message}")


def main() -> int:
    ablations = {
        "variants": [
            {"variant": "default_active_stack_n8a2", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
            {"variant": "weak_yaw_smoothness", "yaw_delta_wrapped_rmse_deg": 0.4, "horizontal_delta_rmse_m": 0.1},
            {"variant": "go2_joint_off", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
            {"variant": "raw_doppler_off", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
        ]
    }
    weights = {
        "per_factor_residual_p95": {
            "ReceiverPositionFactor": 0.2,
            "ReceiverVelocityFactor": 0.3,
            "DualYawFactor": 1.0,
            "Go2ProprioceptiveJointFactor": 1.5,
            "SmoothnessFactor": 5.0,
        }
    }
    candidates = {"candidate_factor_reviews": [{"factor_type": "Go2FootKinematicVelocityFactor", "status": "candidate_needs_data_review"}]}
    report = review_factor_contributions(ablation_summary=ablations, factor_weight_review=weights, candidate_review=candidates)
    if not report.get("review_complete"):
        _fail("review not complete")
    if "SmoothnessFactor" not in report.get("influential_factors", []):
        _fail("smoothness influence missing")
    if "RawDopplerVelocityFactor" not in report.get("suspicious_no_effect_factors", []):
        _fail("raw doppler suspicious_no_effect missing")
    if not report.get("candidate_factors_diagnostic_only"):
        _fail("candidate boundary failed")
    print("audit_fgo_factor_contribution_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
