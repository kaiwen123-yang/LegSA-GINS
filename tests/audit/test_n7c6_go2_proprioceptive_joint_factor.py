"""Audit test wrapper for N7C6 joint factor.

中文说明：pytest 包装 N7C6 joint factor 主审计。
"""

import subprocess
import sys


def test_n7c6_go2_proprioceptive_joint_factor_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c6_go2_proprioceptive_joint_factor.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
