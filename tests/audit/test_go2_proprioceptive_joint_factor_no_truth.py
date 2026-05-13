"""Audit test wrapper for N7C6 no-truth boundary.

中文说明：pytest 包装 Go2 本体观测非 truth 审计。
"""

import subprocess
import sys


def test_go2_proprioceptive_joint_factor_no_truth_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_proprioceptive_joint_factor_no_truth.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
