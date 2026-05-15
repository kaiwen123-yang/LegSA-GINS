#!/usr/bin/env python3
"""Audit N8H visual validation does not relabel feedback as substitution.

中文说明：确认图像语义和 C++ hook 都不是 output substitution。
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
    raise SystemExit(f"audit_fgo_feedback_visual_no_substitution failed: {message}")


def main() -> int:
    root_value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not root_value:
        audit_toy()
    else:
        root = Path(root_value)
        decision = json.loads((root / "N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
        guard = json.loads((root / "N8H_PLOT_SEMANTIC_GUARD_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("fgo_feedback_output_substitution") is not False:
            _fail("decision output substitution flag is not false")
        if decision.get("fgo_feedback_direct_nav_override") is not False:
            _fail("decision direct NAV override flag is not false")
        if guard.get("checks", {}).get("feedback_not_labeled_output_substitution") is not True:
            _fail("semantic guard did not protect substitution label")
    cpp = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    hook_start = cpp.find("void GIEngine::applyFgoFeedbackForTime")
    hook_end = cpp.find("source_aware::SourceWeightResult", hook_start)
    hook = cpp[hook_start:hook_end]
    if "EKFUpdate(dz, H, R)" not in hook:
        _fail("feedback hook does not call EKFUpdate")
    for token in ["pvacur_.vel_ned_mps =", "pvacur_.euler_rad =", "pvacur_.pos_blh_rad_m ="]:
        if token in hook:
            _fail(f"direct NAV/state overwrite token found: {token}")
    print("audit_fgo_feedback_visual_no_substitution passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
