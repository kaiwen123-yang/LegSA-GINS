"""中文说明：审计测试验证 N7C5 foot kinematic candidate 不越界激活。"""

import subprocess
import sys


def test_go2_foot_kinematic_factor_boundary_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_foot_kinematic_factor_boundary.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
