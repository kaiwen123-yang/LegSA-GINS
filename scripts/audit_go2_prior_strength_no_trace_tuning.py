#!/usr/bin/env python3
"""Audit N7C4 strength calibration has no trace/final_v23 tuning path.

中文说明：本审计允许读取 solver 产生的 residual/source-aware diagnostic trace
做 NIS 报告，但禁止把 trace 或 final_v23 输出作为 solver input 或 std 调参来源。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

N7C4_FILES = [
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_calibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_confidence_recalibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_nis_diagnostics.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_ablation.py",
    "src/legsa_gins/go2_prior/go2_n7c4_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c4_decision.py",
    "scripts/experiments/run_n7c4_go2_horizontal_velocity_strength_calibration.py",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_prior_strength_no_trace_tuning failed: {message}")


def main() -> int:
    for rel in N7C4_FILES:
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
        ]
        for token in forbidden:
            if token in text:
                _fail(f"forbidden token {token} in {rel}")
    print("audit_go2_prior_strength_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
