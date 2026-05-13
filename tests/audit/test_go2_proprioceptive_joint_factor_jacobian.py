"""Audit test wrapper for N7C6 Jacobian contract.

中文说明：pytest 包装 N7C6 Jacobian 合同审计。
"""

import subprocess
import sys


def test_go2_proprioceptive_joint_factor_jacobian_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_proprioceptive_joint_factor_jacobian.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
