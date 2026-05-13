"""N7C disabled vertical/yaw/position audit test.

中文说明：测试确认 vertical/yaw/position Go2 prior 均保持关闭。
"""

import subprocess
import sys


def test_go2_vertical_yaw_position_disabled_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_vertical_yaw_position_disabled.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
