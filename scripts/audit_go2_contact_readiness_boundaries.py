#!/usr/bin/env python3
"""Audit N7B contact-readiness boundaries.

中文说明：contact threshold 必须保持诊断默认值，不使用 trace/final_v23 输出调参。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_contact_readiness_boundaries failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_contact_state.py",
        ROOT / "src/legsa_gins/go2_prior/go2_contact_velocity_readiness.py",
        ROOT / "docs/experiments/n7b_go2_contact_state_definition.md",
        ROOT / "docs/experiments/n7b_go2_velocity_contact_readiness.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "diagnostic default",
        "not trace",
        "final_v23 output",
        "go2_contact_prior_enabled",
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "paper performance claim",
        "FGO",
    ]:
        if token not in text:
            _fail(f"boundary token missing: {token}")
    forbidden = [
        "trace-tuned threshold",
        "go2_contact_prior_enabled\": True",
        "go2_velocity_prior_enabled\": True",
        "go2_yaw_prior_enabled\": True",
        "fgo\": True",
    ]
    for token in forbidden:
        if token in text:
            _fail(f"forbidden boundary token present: {token}")
    print("audit_go2_contact_readiness_boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
