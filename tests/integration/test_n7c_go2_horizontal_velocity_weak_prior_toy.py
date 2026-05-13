"""N7C toy integration test delegates to the workflow audit.

中文说明：integration toy 只使用临时 fake runtime，不依赖真实 BY2 输出。
"""

import subprocess
import sys


def test_n7c_go2_horizontal_velocity_weak_prior_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c_go2_horizontal_velocity_weak_prior.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
