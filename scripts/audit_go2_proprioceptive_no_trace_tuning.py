#!/usr/bin/env python3
"""Audit N7C5 proprioceptive mining has no trace/final_v23 tuning path.

中文说明：N7C5 只能使用 Go2-visible / solver-visible cross-source consistency
做候选挖掘，不允许把 trace 或 final_v23 输出作为 solver input 或调因子依据。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

N7C5_FILES = [
    "src/legsa_gins/go2_prior/go2_full_field_inventory.py",
    "src/legsa_gins/go2_prior/go2_contact_probability_factor_review.py",
    "src/legsa_gins/go2_prior/go2_foot_kinematic_velocity_candidate.py",
    "src/legsa_gins/go2_prior/go2_mode_gait_phase_model.py",
    "src/legsa_gins/go2_prior/go2_yawrate_consistency_candidate.py",
    "src/legsa_gins/go2_prior/go2_relative_odometry_candidate.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_factor_ranking.py",
    "src/legsa_gins/go2_prior/go2_n7c5_decision.py",
    "scripts/experiments/run_n7c5_go2_full_proprioceptive_factor_mining.py",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_proprioceptive_no_trace_tuning failed: {message}")


def main() -> int:
    for rel in N7C5_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        trace_key = "trace_" + "solver_input"
        final_key = "final_v23_" + "output_solver_input"
        forbidden = [
            f"{trace_key}\": True",
            trace_key + ": " + "true",
            f"{final_key}\": True",
            final_key + ": " + "true",
            "navigation_metric_feedback_tuning\": True",
            "uses_absolute_error\": True",
            "paper_performance_claim\": True",
        ]
        for token in forbidden:
            if token in text:
                _fail(f"forbidden token {token} in {rel}")
    print("audit_go2_proprioceptive_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
