#!/usr/bin/env python3
"""Audit N7C5A required figures are generated and nonempty.

中文说明：确认 N7C5A 必需图像都生成且不是空文件。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n7c5a_go2_full_proprioceptive_visual_review import _prepare_n7c5_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c5a_required_figures_nonempty failed: {message}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c5a_figures_") as tmp_value:
        tmp = Path(tmp_value)
        n7c5 = _prepare_n7c5_root(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n7c5a_go2_full_proprioceptive_visual_review.py"),
                "--n7c5-root",
                str(n7c5),
                "--output-dir",
                str(out),
                "--figure-output-dir",
                str(figs),
                "--allow-run",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            _fail(proc.stdout + proc.stderr)
        manifest = json.loads((out / "N7C5A_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        missing = [rel for rel in manifest.get("required_figures", []) if not (figs / rel).exists()]
        empty = [rel for rel in manifest.get("required_figures", []) if (figs / rel).exists() and (figs / rel).stat().st_size <= 0]
        if missing or empty:
            _fail(f"missing={missing[:3]} empty={empty[:3]}")
        if manifest.get("figure_count_total") != 18 or not manifest.get("required_figures_nonempty"):
            _fail("manifest does not confirm 18 nonempty figures")
    print("audit_n7c5a_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
