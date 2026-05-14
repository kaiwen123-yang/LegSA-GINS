"""中文说明：测试 yaw wrap residual 审计入口。"""

import subprocess
import sys


def test_audit_fgo_yaw_wrap_residuals() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_yaw_wrap_residuals.py"], check=True)
