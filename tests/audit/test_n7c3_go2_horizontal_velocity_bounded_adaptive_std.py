"""中文说明：测试 N7C3 有界自适应水平速度先验的总审计脚本。"""

import subprocess
import sys


def test_n7c3_go2_horizontal_velocity_bounded_adaptive_std_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c3_go2_horizontal_velocity_bounded_adaptive_std.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
