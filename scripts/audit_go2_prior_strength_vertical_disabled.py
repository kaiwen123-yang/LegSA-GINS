#!/usr/bin/env python3
"""Audit N7C4 strength policies keep Go2 vertical/yaw/position disabled.

中文说明：本审计用 toy prior 检查所有 N7C4 强度策略都保持 std_vd=999，
且不启用 Go2 垂向速度、航向或位置先验。
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_strength_calibration import build_and_write_strength_priors


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_prior_strength_vertical_disabled failed: {message}")


def main() -> int:
    source = [{"time": i * 0.1, "vn": 0.5, "ve": 0.1, "vd": 0.0} for i in range(6)]
    confidence = [
        {"time": i * 0.1, "confidence": 0.8 if i < 3 else 0.2, "confidence_level": "high" if i < 3 else "low"}
        for i in range(6)
    ]
    with tempfile.TemporaryDirectory(prefix="legsa_n7c4_vertical_") as tmp_value:
        paths, report = build_and_write_strength_priors(output_dir=tmp_value, source_prior_rows=source, confidence_rows=confidence)
        if report.get("go2_vertical_velocity_prior_enabled") or report.get("go2_yaw_prior_enabled") or report.get("go2_position_prior_enabled"):
            _fail("forbidden Go2 prior enabled in report")
        for path in paths.values():
            with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if float(row["std_vd"]) < 999.0:
                        _fail(f"std_vd not disabled in {path.name}")
    print("audit_go2_prior_strength_vertical_disabled passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
