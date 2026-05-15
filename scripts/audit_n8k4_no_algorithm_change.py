#!/usr/bin/env python3
"""Audit N8K4 reports no algorithm change."""

# 中文说明：N8K4 是绘图语义修复，不改 solver 或 feedback policy。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k4_semantic_filename_alignment import REQUIRED_REPORTS, make_toy_n8k4_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k4"
            make_toy_n8k4_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("algorithm_changes") is not False:
            raise SystemExit(f"audit_n8k4_no_algorithm_change failed: {name}")
    print("audit_n8k4_no_algorithm_change passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
