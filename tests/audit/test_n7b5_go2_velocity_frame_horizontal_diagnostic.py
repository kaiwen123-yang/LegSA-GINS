"""N7B5 audit 测试：验证 horizontal frame diagnostic runner。"""

import subprocess
import sys


def test_n7b5_go2_velocity_frame_horizontal_diagnostic_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7b5_go2_velocity_frame_horizontal_diagnostic.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
