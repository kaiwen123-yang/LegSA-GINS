#!/usr/bin/env python3
"""Audit that N8I policy reports do not tune from trace.

中文说明：N8I feedback policy 只能用 solver-visible diagnostics，不能用 trace 调参。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8i_feedback_ablation_gate_covariance import REQUIRED_REPORTS, make_toy_n8i_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_policy_no_trace_tuning failed: {message}")


def _audit(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("trace_solver_input") is not False:
            _fail(f"{name} trace_solver_input is not false")
        if payload.get("paper_performance_claim") is not False:
            _fail(f"{name} allows paper claim")
        if payload.get("no_trace_tuning") is False:
            _fail(f"{name} explicitly disables no_trace_tuning")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8i"
            make_toy_n8i_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_fgo_feedback_policy_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
