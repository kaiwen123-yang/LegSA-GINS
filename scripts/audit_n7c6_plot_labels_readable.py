#!/usr/bin/env python3
"""Audit N7C6A plot label readability policy.

中文说明：审计长 variant label 的缩写规则和 runtime replacement figure 边界。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import write_json
from legsa_gins.go2_prior.go2_n7c6_plot_label_readability import build_plot_label_readability_report, shorten_variant_label


def main() -> int:
    if shorten_variant_label("joint_rp1p6deg_hv1p0") != "rp1.6/hv1.0":
        raise SystemExit("short label mapping failed")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(
            root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json",
            {"matrix": [{"variant_id": "joint_rp1p6deg_hv1p0_sourceaware_off"}]},
        )
        report = build_plot_label_readability_report(root)
        if not report.get("long_label_truncation_risk"):
            raise SystemExit("long label risk was not detected")
        if report.get("paper_performance_claim"):
            raise SystemExit("paper claim boundary failed")
    print("audit_n7c6_plot_labels_readable passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
