#!/usr/bin/env python3
"""Audit N8H gate visual review classification.

中文说明：确认 gate review 未判定为过宽且不使用禁止输入。
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
    raise SystemExit(f"audit_fgo_feedback_gate_reasonable failed: {message}")


def main() -> int:
    root_value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not root_value:
        audit_toy()
        print("audit_fgo_feedback_gate_reasonable passed")
        return 0
    path = Path(root_value) / "FGO_FEEDBACK_GATE_VISUAL_REVIEW_REPORT.json"
    if not path.exists():
        _fail("missing gate review report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("classification") not in {"gate_reasonable", "gate_needs_N8H2_policy_review"}:
        _fail(f"unexpected gate classification {report.get('classification')}")
    if report.get("classification") == "gate_too_loose_suspect":
        _fail("gate is too loose suspect")
    if report.get("trace_solver_input") is not False or report.get("final_v23_output_solver_input") is not False:
        _fail("gate review allows forbidden solver input")
    print("audit_fgo_feedback_gate_reasonable passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
