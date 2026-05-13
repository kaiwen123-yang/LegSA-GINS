"""Integration toy test for N7C6 joint factor workflow.

中文说明：用 fake demo 验证 N7C6 joint factor runner。
"""

import json
import subprocess
import sys

from scripts.audit_n7c6_go2_proprioceptive_joint_factor import _prepare_runtime


def test_n7c6_joint_factor_toy(tmp_path):
    n7a, n7c, n7c2, n7c4, n7c5, n7c5a, n7b5, n5b, n6b, clean, dual, exe = _prepare_runtime(tmp_path)
    out = tmp_path / "out"
    figs = tmp_path / "figs"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py",
            "--n7a-root",
            str(n7a),
            "--n7c-root",
            str(n7c),
            "--n7c2-root",
            str(n7c2),
            "--n7c4-root",
            str(n7c4),
            "--n7c5-root",
            str(n7c5),
            "--n7c5a-root",
            str(n7c5a),
            "--n7b5-root",
            str(n7b5),
            "--n5b-root",
            str(n5b),
            "--n6b-root",
            str(n6b),
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--build-dir",
            str(tmp_path / "build"),
            "--exe",
            str(exe),
            "--allow-run",
            "--run-stress",
            "true",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    decision = json.loads((out / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["go2_position_prior_enabled"] is False
