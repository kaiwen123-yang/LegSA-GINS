"""中文说明：N4H0 audit 测试调用独立 audit 脚本。"""

import subprocess
import sys


def test_measurement_floor_sanity_audit_script_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/audit_measurement_floor_sanity.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
