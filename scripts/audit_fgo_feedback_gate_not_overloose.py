#!/usr/bin/env python3
"""Audit N8I gate policy is not left over-loose after spike review.

中文说明：若 default gate 全接受且有 attitude spike，N8I 必须给出保守 gate 或
后续 debug 决策。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8i_feedback_ablation_gate_covariance import make_toy_n8i_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_gate_not_overloose failed: {message}")


def _audit(root: Path) -> None:
    gate = json.loads((root / "FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json").read_text(encoding="utf-8"))
    decision = json.loads((root / "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json").read_text(encoding="utf-8"))
    classification = gate.get("classification")
    selected = gate.get("selected_gate_policy")
    if classification == "gate_too_loose_needs_tightening" and decision.get("status") not in {
        "feedback_policy_not_ready",
        "conservative_feedback_gate_ready",
    }:
        _fail("gate too loose but decision does not block or select conservative gate")
    if classification == "conservative_gate_recommended" and selected not in {"combined_conservative_gate", "attitude_max_4deg"}:
        _fail("conservative classification without conservative selected gate")
    if decision.get("trace_solver_input") is not False or decision.get("final_v23_output_solver_input") is not False:
        _fail("decision has forbidden solver input")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8i"
            make_toy_n8i_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_fgo_feedback_gate_not_overloose passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
