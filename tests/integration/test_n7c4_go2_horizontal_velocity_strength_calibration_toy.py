"""中文说明：集成测试复用 N7C4 toy audit 验证强度校准 runner 可完整产物化。"""

import subprocess
import sys


def test_n7c4_go2_horizontal_velocity_strength_calibration_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c4_go2_horizontal_velocity_strength_calibration.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
