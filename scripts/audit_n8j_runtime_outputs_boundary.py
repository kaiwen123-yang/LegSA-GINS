#!/usr/bin/env python3
"""Audit N8J runtime outputs are generated but not committed.

中文说明：NAV/STD/EVAL/RUN_MANIFEST 是 runtime-only，不进入 git。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8j_runtime_outputs_boundary failed: {message}")


def _audit(root: Path) -> None:
    manifest = json.loads((root / "N8J_FINAL_FEEDBACK_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("runtime_outputs_generated") is not True:
        _fail("runtime outputs not generated")
    if manifest.get("runtime_artifacts_committed") is not False:
        _fail("manifest says runtime artifacts committed")
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    forbidden = ["NAV.nav", "STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json", ".png"]
    for item in forbidden:
        if item in tracked:
            _fail(f"forbidden tracked artifact pattern: {item}")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8j"
            make_toy_n8j_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_n8j_runtime_outputs_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
