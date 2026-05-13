"""中文说明：审计测试运行 N7C4 Go2 水平速度 prior 强度校准 workflow。"""

import subprocess
import sys


def test_n7c4_go2_horizontal_velocity_strength_calibration_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c4_go2_horizontal_velocity_strength_calibration.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
