#!/usr/bin/env python3
"""Audit Go2 velocity/yaw activation remains diagnostic-only.

中文说明：N7B4 可以尝试 diagnostic velocity prior，但正式 Go2 velocity/yaw
prior 必须保持关闭，且不得引入 FGO 或 output-only correction。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/legsa_gins/go2_prior/go2_n7b4_diagnostic_activation.py",
    "src/legsa_gins/go2_prior/go2_n7b4_decision.py",
    "scripts/experiments/run_n7b4_go2_literature_contact_velocity.py",
    "docs/experiments/n7b4_diagnostic_activation_boundary.md",
]


def main() -> int:
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"audit_go2_diagnostic_activation_only failed: missing {rel}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in [
            '"diagnostic_only": True',
            '"paper_performance_claim": False',
            '"trace_solver_input": False',
            '"final_v23_output_solver_input": False',
            '"fgo": False',
        ]:
            if token not in text:
                raise SystemExit(f"audit_go2_diagnostic_activation_only failed: missing {token} in {rel}")
        if "formal_go2_velocity_prior" in text and "False" not in text:
            raise SystemExit(f"audit_go2_diagnostic_activation_only failed: formal prior boundary suspicious in {rel}")
    print("audit_go2_diagnostic_activation_only passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
