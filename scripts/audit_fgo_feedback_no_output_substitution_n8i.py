#!/usr/bin/env python3
"""Audit N8I feedback is not output substitution.

中文说明：N8I 仍然是 EKF update feedback，不允许直接替换 NAV 或 output-only correction。
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
    raise SystemExit(f"audit_fgo_feedback_no_output_substitution_n8i failed: {message}")


def _audit(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("fgo_feedback_output_substitution") is True or payload.get("output_substitution") is True:
            _fail(f"{name} allows output substitution")
        if payload.get("fgo_feedback_direct_nav_override") is True or payload.get("direct_nav_override") is True:
            _fail(f"{name} allows direct NAV overwrite")
        if payload.get("no_output_substitution") is False or payload.get("no_direct_nav_override") is False:
            _fail(f"{name} disables no-substitution boundary")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8i"
            make_toy_n8i_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_fgo_feedback_no_output_substitution_n8i passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
