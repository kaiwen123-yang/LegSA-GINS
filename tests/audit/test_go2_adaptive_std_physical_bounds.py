"""中文说明：测试 N7C3 自适应标准差满足不超过 5 m/s 的物理边界。"""

import subprocess
import sys


def test_go2_adaptive_std_physical_bounds_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_adaptive_std_physical_bounds.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
