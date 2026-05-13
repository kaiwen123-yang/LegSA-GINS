"""N7C real EKF activation audit test.

中文说明：测试确认 N7C horizontal velocity 有真实 EKF 激活入口。
"""

import subprocess
import sys


def test_go2_horizontal_velocity_real_ekf_activation_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_horizontal_velocity_real_ekf_activation.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
