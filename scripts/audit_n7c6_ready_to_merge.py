#!/usr/bin/env python3
"""Audit N7C6A ready-to-merge decision logic.

中文说明：只验证 ready-to-merge 门禁逻辑，不执行 merge/tag。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_final_decision import make_n7c6a_final_decision


def main() -> int:
    decision = make_n7c6a_final_decision(
        input_manifest={"n7c6_reports_all_found": True},
        semantic_report={"metric_semantic_status": "passed_with_runtime_replacements"},
        readability_report={"plot_label_readability_status": "passed_with_runtime_replacements"},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
        n7c6_decision={"status": "stronger_go2_proprioceptive_joint_factor_ready", "recommended_default": "joint_rp1deg_hv1p0"},
        nis_report={"any_overconfidence": False, "any_stuck_at_cap": False},
    )
    if decision.get("status") != "ready_to_merge_PR38_and_start_N8A":
        raise SystemExit(f"unexpected decision: {decision.get('status')}")
    if decision.get("fgo") or decision.get("paper_performance_claim"):
        raise SystemExit("N7C6A boundary failed")
    print("audit_n7c6_ready_to_merge passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
