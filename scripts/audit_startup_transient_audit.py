#!/usr/bin/env python3
"""Audit N4H2F startup transient module.

中文说明：toy audit 检查开头凸起识别与禁止裁剪指标边界。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legsa_gins.visualization.startup_transient_audit import analyze_startup_transient  # noqa: E402


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/visualization/startup_transient_audit.py",
        ROOT / "scripts/experiments/run_startup_transient_audit.py",
    ]
    for path in required:
        if not path.exists():
            raise AssertionError(f"missing required file: {path}")
    with tempfile.TemporaryDirectory(prefix="legsa_startup_audit_") as temp:
        base = Path(temp)
        error = base / "FRESH_REPLAY_ERROR_SERIES.csv"
        with error.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "horizontal_error_m",
                    "up_error_m",
                    "yaw_error_deg",
                    "roll_error_deg",
                    "pitch_error_deg",
                ],
            )
            writer.writeheader()
            for index in range(20):
                writer.writerow(
                    {
                        "timestamp": float(index),
                        "horizontal_error_m": 0.2,
                        "up_error_m": 2.0 if index < 10 else 0.2,
                        "yaw_error_deg": 1.0,
                        "roll_error_deg": 3.2 if index < 10 else 0.4,
                        "pitch_error_deg": 0.5,
                    }
                )
        summary = base / "FRESH_REPLAY_SUMMARY.json"
        summary.write_text(json.dumps({"count": 20}), encoding="utf-8")
        report = analyze_startup_transient(error, summary)
        if not report["startup_transient_visible"]:
            raise AssertionError("startup transient should be visible")
        if not report["startup_transient_within_gate"]:
            raise AssertionError("startup transient should remain within gate")
        if report["deletion_or_crop_allowed"]:
            raise AssertionError("deletion/crop must be forbidden")
        if report["numerical_performance_claim"]:
            raise AssertionError("no performance claim")
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
