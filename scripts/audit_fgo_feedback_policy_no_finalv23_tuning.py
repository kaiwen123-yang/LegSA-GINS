#!/usr/bin/env python3
"""Audit that N8I feedback policy does not tune from final_v23 outputs.

中文说明：final_v23 只能 evaluation-only，不可作为 feedback gate/covariance 调参输入。
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
    raise SystemExit(f"audit_fgo_feedback_policy_no_finalv23_tuning failed: {message}")


def _audit(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("final_v23_output_solver_input") is not False:
            _fail(f"{name} final_v23_output_solver_input is not false")
        if payload.get("no_finalv23_tuning") is False:
            _fail(f"{name} explicitly disables no_finalv23_tuning")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8i"
            make_toy_n8i_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_fgo_feedback_policy_no_finalv23_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
