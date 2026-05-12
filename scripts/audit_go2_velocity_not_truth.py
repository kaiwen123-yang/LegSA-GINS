#!/usr/bin/env python3
"""Audit that N7B never treats Go2 velocity as truth.

中文说明：Go2 velocity 只能作为一致性诊断来源，不能写成 truth 或 N7B prior。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_velocity_not_truth failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_velocity_quality.py",
        ROOT / "src/legsa_gins/go2_prior/go2_n7b_decision.py",
        ROOT / "docs/experiments/n7b_go2_velocity_quality.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "Go2 velocity is not truth",
        "cross-source consistency",
        "not truth error",
        "go2_velocity_truth_claim",
        "go2_velocity_prior_enabled",
    ]:
        if token not in text:
            _fail(f"not-truth token missing: {token}")
    forbidden = [
        "Go2 velocity is truth",
        "go2_velocity_truth_claim\": True",
        "go2_velocity_truth_claim = True",
        "go2_velocity_prior_enabled\": True",
        "go2_velocity_prior_enabled = True",
    ]
    for token in forbidden:
        if token in text:
            _fail(f"forbidden truth/prior token present: {token}")
    print("audit_go2_velocity_not_truth passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
