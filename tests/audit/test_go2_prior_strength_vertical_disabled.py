"""中文说明：审计测试确认 N7C4 prior 强度扫描继续禁用 Go2 垂向/yaw/position。"""

import subprocess
import sys


def test_go2_prior_strength_vertical_disabled_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_prior_strength_vertical_disabled.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
