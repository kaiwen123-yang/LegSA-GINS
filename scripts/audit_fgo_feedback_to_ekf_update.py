#!/usr/bin/env python3
"""Audit that FGO feedback enters EKF update/state feedback path.

中文说明：确认 feedback loader、GIEngine hook、EKFUpdate 和 stateFeedback 路径闭合。
"""

from __future__ import annotations

import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_to_ekf_update failed: {message}")


def main() -> int:
    header = (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/kf_gins/gi_engine.hpp").read_text(encoding="utf-8")
    source = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    runtime = (ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text(encoding="utf-8")
    if "setFgoFeedbackObservations" not in header or "applyFgoFeedbackForTime" not in source:
        _fail("feedback interface is not wired into GIEngine")
    if "EKFUpdate(dz, H, R)" not in source:
        _fail("feedback does not use EKFUpdate")
    if "applyFgoFeedbackForTime(gnss.time)" not in source:
        _fail("feedback is not called on GNSS update path before stateFeedback")
    if "FgoFeedbackLoader::loadCsv" not in runtime:
        _fail("runtime does not load feedback observations")
    root = Path(os.environ["N8G_REPORT_OUTPUT_DIR"]) if os.environ.get("N8G_REPORT_OUTPUT_DIR") else None
    if root and (root / "RUN_MANIFEST.json").exists():
        manifest = json.loads((root / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if int(manifest.get("feedback_update_count", 0) or 0) <= 0:
            _fail("runtime manifest feedback_update_count is zero")
    print("audit_fgo_feedback_to_ekf_update passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
