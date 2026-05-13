#!/usr/bin/env python3
"""Audit N7C6A metric semantic guard.

中文说明：审计图名和 metric namespace，防止 raw series 被误写成 truth error。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import write_json
from legsa_gins.go2_prior.go2_n7c6_metric_semantic_guard import build_metric_semantic_guard_report


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(
            root / "N7C6_FIGURE_MANIFEST.json",
            {"required_figures": ["clean_roll_pitch_error_baseline_vs_joint.png", "joint_minus_horizontal_only_delta.png"]},
        )
        report = build_metric_semantic_guard_report(root)
        if report.get("metric_semantic_status") != "passed_with_runtime_replacements":
            raise SystemExit("metric semantic guard did not request runtime replacements")
        if not report.get("velocity_plots_not_truth_error") or report.get("paper_performance_claim"):
            raise SystemExit("metric semantic guard boundary failed")
    print("audit_n7c6_metric_semantics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
