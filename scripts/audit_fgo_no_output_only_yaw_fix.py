#!/usr/bin/env python3
"""Audit N8A2 yaw fix is solver/residual-level, not output-only correction.

中文说明：确认 N8A2 不是输出后处理式 yaw 修正。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_no_feedback_smoother import run_no_feedback_smoother
from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


def main() -> int:
    dataset = FGOStateDataset(
        [
            FGOState(0, 0.0, yaw_deg=359.0),
            FGOState(1, 1.0, yaw_deg=1.0),
            FGOState(2, 2.0, yaw_deg=2.0),
        ]
    )
    rows, report = run_no_feedback_smoother(dataset, stage="N8A2_audit", variant="toy")
    if not report.get("yaw_wrap_residuals_enabled"):
        raise SystemExit("yaw wrap not enabled in smoother")
    if report.get("output_only_yaw_correction") or report.get("output_only_correction"):
        raise SystemExit("output-only correction flag set")
    if report.get("smoothness_factor_deleted"):
        raise SystemExit("smoothness factor was deleted")
    if rows[0]["yaw_deg"] > 90.0 and rows[0]["yaw_deg"] < 270.0:
        raise SystemExit("yaw appears arithmetic-averaged after output-only correction")
    print("audit_fgo_no_output_only_yaw_fix passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
