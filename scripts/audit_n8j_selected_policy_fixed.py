#!/usr/bin/env python3
"""Audit N8J selected policy is fixed from N8I.

中文说明：N8J 不允许 hidden policy change。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8j_selected_policy_fixed failed: {message}")


def _audit(root: Path) -> None:
    policy = json.loads((root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json").read_text(encoding="utf-8"))
    expected = {
        "policy_name": "n8i_selected_conservative_feedback",
        "feedback_mode": "horizontal_velocity_attitude_feedback",
        "position_feedback_enabled": False,
        "horizontal_velocity_feedback_enabled": True,
        "attitude_feedback_enabled": True,
        "gate_policy": "combined_conservative_gate",
        "covariance_policy": "inflation_auto_from_residual_proxy",
        "window_duration_s": 5.0,
        "stride_s": 1.0,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            _fail(f"{key} mismatch: {policy.get(key)}")
    if policy.get("n8i_selected_policy_match") is not True or policy.get("hidden_policy_change") is True:
        _fail("selected policy is not locked from N8I")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8j"
            make_toy_n8j_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_n8j_selected_policy_fixed passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
