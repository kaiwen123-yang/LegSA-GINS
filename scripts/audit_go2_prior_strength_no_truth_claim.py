#!/usr/bin/env python3
"""Audit N7C4 strength calibration does not claim Go2 velocity as truth.

中文说明：本审计检查新增 N7C4 文件和 toy 输出中的 Go2 velocity truth claim
都保持 false。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_strength_calibration import build_and_write_strength_priors


N7C4_FILES = [
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_calibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_confidence_recalibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_ablation.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_nis_diagnostics.py",
    "src/legsa_gins/go2_prior/go2_n7c4_decision.py",
    "scripts/experiments/run_n7c4_go2_horizontal_velocity_strength_calibration.py",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_prior_strength_no_truth_claim failed: {message}")


def main() -> int:
    for rel in N7C4_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        if "go2_velocity_truth_claim\": True" in text or "go2_velocity_truth_claim: true" in text:
            _fail(f"truth claim true in {rel}")
    source = [{"time": 0.0, "vn": 1.0, "ve": 0.0, "vd": 0.0}]
    confidence = [{"time": 0.0, "confidence": 0.9, "confidence_level": "high"}]
    with tempfile.TemporaryDirectory(prefix="legsa_n7c4_truth_") as tmp_value:
        _paths, report = build_and_write_strength_priors(output_dir=tmp_value, source_prior_rows=source, confidence_rows=confidence)
        if report.get("go2_velocity_truth_claim"):
            _fail("truth claim true in report")
    print("audit_go2_prior_strength_no_truth_claim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
