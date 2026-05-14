#!/usr/bin/env python3
"""Audit that N8G feedback is not output substitution.

中文说明：审计 C++ hook 必须走 EKFUpdate，不能直接写 pvacur_ 作为后处理。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_not_output_substitution failed: {message}")


def main() -> int:
    root = Path(os.environ["N8G_REPORT_OUTPUT_DIR"]) if os.environ.get("N8G_REPORT_OUTPUT_DIR") else None
    if root and (root / "RUN_MANIFEST.json").exists():
        manifest = json.loads((root / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if manifest.get("fgo_feedback_output_substitution") is not False:
            _fail("manifest allows output substitution")
        if manifest.get("fgo_feedback_direct_nav_override") is not False:
            _fail("manifest allows direct NAV override")
    cpp = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    hook_start = cpp.find("void GIEngine::applyFgoFeedbackForTime")
    hook_end = cpp.find("source_aware::SourceWeightResult", hook_start)
    hook = cpp[hook_start:hook_end]
    if "EKFUpdate(dz, H, R)" not in hook:
        _fail("feedback hook does not call EKFUpdate")
    forbidden = ["pvacur_.vel_ned_mps =", "pvacur_.euler_rad =", "pvacur_.pos_blh_rad_m ="]
    for token in forbidden:
        if token in hook:
            _fail(f"direct state overwrite in feedback hook: {token}")
    print("audit_fgo_feedback_not_output_substitution passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
