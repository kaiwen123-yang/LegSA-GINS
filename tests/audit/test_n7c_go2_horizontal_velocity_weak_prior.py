"""N7C audit test.

中文说明：测试 N7C workflow 审计脚本能生成 toy 报告并通过边界检查。
"""

import subprocess
import sys


def test_n7c_go2_horizontal_velocity_weak_prior_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c_go2_horizontal_velocity_weak_prior.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
