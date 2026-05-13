"""N7C no-truth audit test.

中文说明：测试只执行审计脚本，确认 Go2 velocity 不是 truth 的边界存在。
"""

import subprocess
import sys


def test_go2_horizontal_velocity_no_truth_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_horizontal_velocity_no_truth.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
