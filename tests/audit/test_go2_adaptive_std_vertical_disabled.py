"""中文说明：测试 N7C3 继续禁用 Go2 垂向速度、航向和位置先验。"""

import subprocess
import sys


def test_go2_adaptive_std_vertical_disabled_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_adaptive_std_vertical_disabled.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
