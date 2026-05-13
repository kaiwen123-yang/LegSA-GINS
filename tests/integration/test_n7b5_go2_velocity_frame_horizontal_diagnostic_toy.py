"""N7B5 integration toy 测试：用合成数据跑完整 horizontal diagnostic 流程。"""

import subprocess
import sys


def test_n7b5_go2_velocity_frame_horizontal_diagnostic_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7b5_go2_velocity_frame_horizontal_diagnostic.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
