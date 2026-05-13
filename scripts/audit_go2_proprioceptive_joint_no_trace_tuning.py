#!/usr/bin/env python3
"""Audit N7C6 joint factor has no trace/final_v23 tuning path.

中文说明：确认 N7C6 不把 trace 或 final_v23 输出用于 solver input 或调参。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/legsa_gins/go2_prior/go2_attitude_strength_calibration.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_builder.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_policy.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_jacobian.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_ablation.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_nis.py",
    "src/legsa_gins/go2_prior/go2_n7c6_decision.py",
    "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_proprioceptive_joint_no_trace_tuning failed: {message}")


def main() -> int:
    trace_key = "trace_" + "solver_input"
    final_key = "final_v23_" + "output_solver_input"
    for rel in FILES:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        forbidden = [
            f"{trace_key}\": True",
            trace_key + ": " + "true",
            f"{final_key}\": True",
            final_key + ": " + "true",
            "paper_performance_claim\": True",
            "go2_truth_claim\": True",
            "go2_velocity_truth_claim\": True",
            "go2_roll_pitch_truth_claim\": True",
        ]
        for token in forbidden:
            if token in text:
                _fail(f"forbidden token {token} in {rel}")
    print("audit_go2_proprioceptive_joint_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
