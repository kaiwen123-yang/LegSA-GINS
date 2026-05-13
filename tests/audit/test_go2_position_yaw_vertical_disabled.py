"""Audit test wrapper for forbidden Go2 priors.

中文说明：pytest 包装 Go2 position/yaw/vertical 禁用审计。
"""

import subprocess
import sys


def test_go2_position_yaw_vertical_disabled_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_position_yaw_vertical_disabled.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
