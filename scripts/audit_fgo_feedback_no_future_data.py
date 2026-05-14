#!/usr/bin/env python3
"""Audit no-future-data feedback policy.

中文说明：审计 feedback window end 不超过当前 update time。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_no_future_data failed: {message}")


def main() -> int:
    root = Path(os.environ["N8G_REPORT_OUTPUT_DIR"]) if os.environ.get("N8G_REPORT_OUTPUT_DIR") else None
    if root and (root / "SLIDING_WINDOW_MANAGER_REPORT.json").exists():
        report = json.loads((root / "SLIDING_WINDOW_MANAGER_REPORT.json").read_text(encoding="utf-8"))
        if report.get("no_future_data_verified") is not True:
            _fail("runtime report no_future_data_verified is false")
    cpp = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "source_window_end > update_time" not in cpp:
        _fail("C++ feedback hook does not guard source_window_end")
    print("audit_fgo_feedback_no_future_data passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
