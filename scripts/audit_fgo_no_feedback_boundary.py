#!/usr/bin/env python3
"""Audit N8A no-feedback boundary.

中文说明：验证 FGO 输出不反馈 EKF，也不替换 EKF NAV。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry
from legsa_gins.fgo.fgo_no_feedback_smoother import run_no_feedback_smoother
from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


def main() -> int:
    registry = build_default_factor_registry()
    if not registry.get("no_feedback") or registry.get("fgo_output_replaces_ekf_nav"):
        raise SystemExit("FGO registry feedback boundary failed")
    _rows, report = run_no_feedback_smoother(FGOStateDataset([FGOState(index=0, time=0.0), FGOState(index=1, time=1.0)]))
    if report.get("fgo_output_feedback_to_ekf") or report.get("fgo_output_replaces_ekf_nav"):
        raise SystemExit("FGO smoother feedback boundary failed")
    print("audit_fgo_no_feedback_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
