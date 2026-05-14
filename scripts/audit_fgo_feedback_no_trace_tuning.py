#!/usr/bin/env python3
"""Audit no trace/final_v23 tuning for N8G feedback.

中文说明：审计 tracked N8G 代码不写本地绝对 runtime 路径，也不开放 reference 调参。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_no_trace_tuning failed: {message}")


def main() -> int:
    root = Path(os.environ["N8G_REPORT_OUTPUT_DIR"]) if os.environ.get("N8G_REPORT_OUTPUT_DIR") else None
    for name in [
        "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json",
        "FGO_FEEDBACK_GATE_REPORT.json",
        "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json",
    ]:
        if root and (root / name).exists():
            report = json.loads((root / name).read_text(encoding="utf-8"))
            if report.get("trace_solver_input") is not False:
                _fail(f"{name} trace_solver_input not false")
            if report.get("final_v23_output_solver_input") is not False:
                _fail(f"{name} final_v23_output_solver_input not false")
            if report.get("paper_performance_claim") is not False:
                _fail(f"{name} paper_performance_claim not false")
    tracked_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in list((ROOT / "src/legsa_gins/fgo_feedback").glob("*.py")) + list((ROOT / "scripts").glob("audit_fgo_feedback*.py"))
    )
    forbidden_runtime_tokens = ["/mnt/c/" + "Users/", "C:" + "\\\\Users"]
    for token in forbidden_runtime_tokens:
        if token in tracked_text:
            _fail(f"tracked N8G code contains runtime absolute path token {token}")
    print("audit_fgo_feedback_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
