"""Integration toy test for N7C5A visual review.

中文说明：用 toy N7C5 产物验证 N7C5A runner。
"""

import json
import subprocess
import sys

from scripts.audit_n7c5a_go2_full_proprioceptive_visual_review import _prepare_n7c5_root


def test_n7c5a_visual_review_toy(tmp_path):
    n7c5 = _prepare_n7c5_root(tmp_path)
    out = tmp_path / "out"
    figs = tmp_path / "figs"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n7c5a_go2_full_proprioceptive_visual_review.py",
            "--n7c5-root",
            str(n7c5),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    decision = json.loads((out / "N7C5A_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] == "n7c5_visual_review_passed"
