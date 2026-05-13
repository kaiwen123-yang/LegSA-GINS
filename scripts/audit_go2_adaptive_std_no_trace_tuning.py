#!/usr/bin/env python3
"""Audit that N7C3 adaptive std policy does not tune from trace/final_v23.

中文说明：本审计只确认自适应标准差策略没有从 trace 或 final_v23 输出调参。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

N7C3_FILES = [
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_confidence.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_bounded_adaptive_std.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_soft_gating.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_adaptive_ablation.py",
    "src/legsa_gins/go2_prior/go2_n7c3_decision.py",
    "scripts/experiments/run_n7c3_go2_horizontal_velocity_bounded_adaptive_std.py",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_adaptive_std_no_trace_tuning failed: {message}")


def main() -> int:
    for rel in N7C3_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "trace_solver_input\": True" in text or "final_v23_output_solver_input\": True" in text:
            _fail(f"forbidden true solver-input flag in {rel}")
        if "navigation_metric_feedback_tuning\": True" in text:
            _fail(f"navigation metric feedback tuning enabled in {rel}")
    docs = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in [
        "docs/experiments/n7c3_confidence_policy.md",
        "docs/experiments/n7c3_literature_informed_policy.md",
        "docs/experiments/n7c3_go2_horizontal_velocity_bounded_adaptive_std.md",
    ])
    for phrase in [
        "No trace/final_v23 tuning",
        "Go2 velocity is not truth",
        "No paper performance claim",
    ]:
        if phrase not in docs:
            _fail(f"missing doc boundary phrase: {phrase}")
    print("audit_go2_adaptive_std_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
