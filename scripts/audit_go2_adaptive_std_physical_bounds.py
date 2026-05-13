#!/usr/bin/env python3
"""Audit N7C3 bounded adaptive std physical limits.

中文说明：本审计检查 N7C3 自适应水平速度标准差是否满足有界物理上限。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_bounded_adaptive_std import (
    DIAGNOSTIC_EXTREME_MAX_STD_MPS,
    bounded_std_for_confidence,
    build_bounded_adaptive_go2_horizontal_velocity_priors,
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_adaptive_std_physical_bounds failed: {message}")


def main() -> int:
    expected = [
        (0.95, 1.0, True),
        (0.70, 1.5, True),
        (0.45, 2.5, True),
        (0.20, 4.0, True),
        (0.05, 5.0, False),
    ]
    for confidence, std, update in expected:
        got_std, got_update, _reason = bounded_std_for_confidence(confidence)
        if got_std != std or got_update is not update:
            _fail(f"unexpected policy row for confidence {confidence}: {got_std}, {got_update}")
    source = [{"time": index, "vn": 0.1, "ve": 0.2, "vd": 0.0, "contact_model": "toy"} for index in range(5)]
    confidence_rows = [
        {"time": index, "confidence": confidence, "confidence_level": level, "reason_codes": "toy"}
        for index, (confidence, level) in enumerate([(0.95, "high"), (0.70, "medium"), (0.45, "low"), (0.20, "low"), (0.05, "invalid")])
    ]
    rows, report = build_bounded_adaptive_go2_horizontal_velocity_priors(source_prior_rows=source, confidence_rows=confidence_rows)
    values = [float(row["std_vn"]) for row in rows] + [float(row["std_ve"]) for row in rows]
    if max(values) > DIAGNOSTIC_EXTREME_MAX_STD_MPS:
        _fail("std exceeds 5 m/s")
    if any(value in {8.0, 10.0} for value in values):
        _fail("forbidden 8/10 mps std present")
    if not report.get("max_std_le_5") or report.get("contains_8_or_10_mps_std"):
        _fail("report physical bound flags failed")
    print("audit_go2_adaptive_std_physical_bounds passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
