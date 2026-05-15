#!/usr/bin/env python3
"""Audit N8H feedback variant ablation report.

中文说明：确认七个 variant 和 reject-all sanity 边界。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8h_fgo_feedback_visual_validation import audit_toy


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_variant_ablation failed: {message}")


def main() -> int:
    root_value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not root_value:
        audit_toy()
        print("audit_fgo_feedback_variant_ablation passed")
        return 0
    path = Path(root_value) / "N8H_FEEDBACK_VARIANT_ABLATION_REVIEW.json"
    if not path.exists():
        _fail("missing variant ablation report")
    report = json.loads(path.read_text(encoding="utf-8"))
    variants = {item.get("variant_id"): item for item in report.get("variants", [])}
    required = {
        "ekf_baseline_no_fgo_feedback",
        "fgo_feedback_velocity_attitude",
        "fgo_feedback_horizontal_velocity_attitude",
        "fgo_feedback_position_velocity_attitude_diagnostic",
        "fgo_feedback_velocity_only",
        "fgo_feedback_attitude_only",
        "fgo_feedback_reject_all_sanity",
    }
    missing = required - set(variants)
    if missing:
        _fail(f"missing variants {sorted(missing)}")
    if report.get("reject_all_sanity_passed") is not True:
        _fail("reject-all sanity did not pass")
    if report.get("no_output_substitution") is not True or report.get("no_direct_nav_override") is not True:
        _fail("variant report allows substitution or direct override")
    print("audit_fgo_feedback_variant_ablation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
